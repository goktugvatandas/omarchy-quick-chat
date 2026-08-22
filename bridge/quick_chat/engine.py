"""Single-turn orchestration across profiles, adapters, and transports."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Iterator

from .adapters.base import AdapterContext, AdapterEvent
from .adapters.registry import AdapterRegistry
from .models import Config
from .protocol import Event, Request
from .sanitize import (
    EVENT_COUNT_LIMIT,
    PROCESS_LINE_LIMIT,
    RESPONSE_TEXT_LIMIT,
    TRUNCATION_MARKER,
    bounded_text_prefix,
    bounded_wire_value,
    truncate_text,
)
from .transports.base import RunResult, Transport


class BusyError(RuntimeError):
    pass


class Engine:
    def __init__(
        self,
        registry: AdapterRegistry,
        transport: Transport,
        config: Config,
        session_resolver: Callable[[str, str], str | None] | None = None,
        attachment_cleanup: Callable[[tuple[str, ...]], None] | None = None,
        approval_timeout_seconds: float = 60.0,
    ) -> None:
        self.registry = registry
        self.transport = transport
        self.config = config
        self.session_resolver = session_resolver
        self.attachment_cleanup = attachment_cleanup
        self.approval_timeout_seconds = approval_timeout_seconds
        self._lock = threading.Lock()
        self._active_request_id: str | None = None
        self._active_cancel: Callable[[], bool] | None = None
        self._cancel_requested: set[str] = set()
        self._cancel_dispatched: set[str] = set()
        self._pending_approvals: dict[
            tuple[str, str], tuple[threading.Event, list[bool]]
        ] = {}

    def _claim(self, request_id: str) -> None:
        with self._lock:
            if self._active_request_id is not None:
                raise BusyError(f"request {self._active_request_id} is already running")
            self._active_request_id = request_id
            self._cancel_requested.discard(request_id)
            self._cancel_dispatched.discard(request_id)

    def _release(self, request_id: str) -> None:
        with self._lock:
            if self._active_request_id == request_id:
                self._active_request_id = None
                self._active_cancel = None
                self._cancel_requested.discard(request_id)
                self._cancel_dispatched.discard(request_id)

    def _install_cancel(self, request_id: str, cancel: Callable[[], bool]) -> None:
        with self._lock:
            self._active_cancel = cancel
            dispatch = (
                request_id in self._cancel_requested
                and request_id not in self._cancel_dispatched
            )
            if dispatch:
                self._cancel_dispatched.add(request_id)
        if dispatch:
            cancel()

    def _is_cancel_requested(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._cancel_requested

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            if self._active_request_id != request_id:
                return False
            self._cancel_requested.add(request_id)
            cancel = self._active_cancel
            dispatch = cancel is not None and request_id not in self._cancel_dispatched
            if dispatch:
                self._cancel_dispatched.add(request_id)
            pending_approvals = [
                event
                for (pending_request_id, _), (event, _) in self._pending_approvals.items()
                if pending_request_id == request_id
            ]
        for event in pending_approvals:
            event.set()
        if dispatch and cancel is not None:
            return cancel()
        return True

    def resolve_approval(
        self,
        request_id: str,
        approval_id: str,
        approved: bool,
    ) -> bool:
        with self._lock:
            pending = self._pending_approvals.get((request_id, approval_id))
            if pending is None:
                return False
            event, result = pending
            if result:
                return False
            result.append(approved)
            event.set()
            return True

    def handle(self, request: Request) -> Iterator[Event]:
        if request.type != "run":
            raise ValueError("engine handles only run requests")
        self._claim(request.request_id)
        adapter = None
        try:
            profile = self.config.profile(request.profile_id or "")
            if profile is None:
                yield Event("error", request.request_id, {
                    "code": "profile_not_found",
                    "message": "The selected profile no longer exists.",
                })
                return
            if profile.adapter_id == "custom":
                from .adapters.custom import CustomAdapter

                adapter = CustomAdapter(
                    executable=profile.custom_executable or "",
                    args=profile.custom_args,
                    stdin=profile.custom_stdin,
                    read_only_args=profile.custom_read_only_args,
                    output=profile.custom_output,
                )
            else:
                adapter = self.registry.get(profile.adapter_id)
                detection = self.registry.detect(profile.adapter_id)
                if not detection.get("available", False):
                    yield Event("error", request.request_id, {
                        "code": detection.get("code", "not_installed"),
                        "message": f"{profile.adapter_id} is not available.",
                    })
                    return
            cwd_diagnostic = None
            if profile.working_directory_strategy == "fixed":
                cwd = Path(profile.working_directory or "")
            elif profile.working_directory_strategy == "active-project":
                from .context.app import ActiveAppProvider, ActiveProjectResolver

                try:
                    metadata = ActiveAppProvider().get()
                    resolution = ActiveProjectResolver().resolve(metadata.pid)
                except (OSError, RuntimeError, ValueError):
                    resolution = ActiveProjectResolver().resolve(None)
                cwd = resolution.path
                cwd_diagnostic = resolution.diagnostic
            else:
                cwd = Path.home()
            if profile.thinking_effort is not None:
                if profile.adapter_id == "custom":
                    supported_efforts = ()
                else:
                    supported_efforts = self.registry.efforts(
                        profile.adapter_id,
                        profile.model,
                        cwd,
                    )
                if profile.thinking_effort not in {
                    option.id for option in supported_efforts
                }:
                    yield Event("error", request.request_id, {
                        "code": "unsupported_effort",
                        "message": (
                            f"{profile.thinking_effort} is not supported by "
                            f"{profile.adapter_id}."
                        ),
                        "resetTo": None,
                    })
                    return
            context = AdapterContext(
                prompt=request.prompt or "",
                model=profile.model,
                cwd=cwd,
                attachments=request.attachments,
                session_id=(
                    self.session_resolver(
                        request.conversation_id or "",
                        profile.adapter_id,
                    )
                    if self.session_resolver is not None
                    else None
                ),
                system_instructions=profile.system_instructions,
                private=request.private,
                thinking_effort=profile.thinking_effort,
            )
            invocation = adapter.start(context)
            yield Event("status", request.request_id, {
                "status": "starting",
                "adapterId": profile.adapter_id,
            })
            if cwd_diagnostic:
                yield Event("status", request.request_id, {
                    "status": "working_directory_fallback",
                    "message": cwd_diagnostic,
                })

            normalized: queue.Queue[AdapterEvent] = queue.Queue(maxsize=64)
            result_holder = []
            transport_errors: list[Exception] = []
            transport_done = threading.Event()

            acp_transport = None
            acp_command = getattr(adapter, "acp_argv", None)
            if profile.transport in {"auto", "acp"} and callable(acp_command):
                acp_transport = self.registry.acp_transport(
                    profile.adapter_id,
                    profile.model,
                    acp_command(),
                )
                if acp_transport is None and profile.transport == "acp":
                    yield Event("error", request.request_id, {
                        "code": "acp_failed",
                        "message": "ACP is unavailable for this profile.",
                        "degradedTo": "process",
                        "replayed": False,
                    })
                    return

            def emit(raw_event: AdapterEvent) -> None:
                if acp_transport is not None:
                    parsed_events = [raw_event]
                else:
                    parsed_events = adapter.parse_event(raw_event)
                for adapter_event in parsed_events:
                    bounded = bounded_wire_value(adapter_event.data)
                    data = bounded if isinstance(bounded, dict) else {}
                    if adapter_event.type == "text_delta":
                        data["text"] = truncate_text(
                            adapter_event.data.get("text", ""),
                            PROCESS_LINE_LIMIT,
                        )
                    normalized.put(AdapterEvent(adapter_event.type, data))

            def acp_permission_handler(data: dict[str, object]) -> bool:
                approval_id = str(data.get("approvalId") or uuid.uuid4())
                approval_event = threading.Event()
                approval_result: list[bool] = []
                key = (request.request_id, approval_id)
                with self._lock:
                    if request.request_id in self._cancel_requested:
                        return False
                    self._pending_approvals[key] = (approval_event, approval_result)
                normalized.put(AdapterEvent("tool_request", {
                    "approvalId": approval_id,
                    "title": data.get("title", "Agent operation"),
                    "operation": data.get("operation", "unknown"),
                    "details": data.get("details", ""),
                    "_acpManaged": True,
                }))
                resolved = approval_event.wait(self.approval_timeout_seconds)
                with self._lock:
                    self._pending_approvals.pop(key, None)
                return resolved and bool(approval_result and approval_result[0])

            def run_transport() -> None:
                try:
                    if acp_transport is not None:
                        from .transports.acp import image_block, text_block

                        acp_transport.permission_handler = acp_permission_handler
                        session = acp_transport.open_session(cwd, context.session_id)
                        normalized.put(AdapterEvent("session", {"sessionId": session.id}))
                        active_acp = acp_transport

                        def cancel_acp_session() -> bool:
                            def request_cancel() -> None:
                                try:
                                    active_acp.cancel(session.id)
                                except Exception:
                                    active_acp.disconnect()

                            threading.Thread(target=request_cancel, daemon=True).start()
                            return True

                        self._install_cancel(request.request_id, cancel_acp_session)
                        prompt_text = context.prompt
                        if context.system_instructions:
                            prompt_text = (
                                context.system_instructions
                                + "\n\nUser question:\n"
                                + context.prompt
                            )
                        content = [text_block(prompt_text)]
                        content.extend(
                            image_block(Path(attachment.path), attachment.mime_type)
                            for attachment in context.attachments
                            if attachment.kind == "image" and attachment.path
                        )
                        prompt_result = acp_transport.prompt(session.id, content, emit)
                        normalized.put(AdapterEvent("complete", {
                            "stopReason": prompt_result.stop_reason,
                        }))
                        result_holder.append(RunResult(0, "", False, False))
                    else:
                        def cancel_process_session() -> bool:
                            def request_cancel() -> None:
                                is_running = getattr(self.transport, "is_running", None)
                                deadline = time.monotonic() + 1
                                while (
                                    callable(is_running)
                                    and not is_running(request.request_id)
                                    and time.monotonic() < deadline
                                ):
                                    time.sleep(0.005)
                                self.transport.cancel(request.request_id)

                            threading.Thread(target=request_cancel, daemon=True).start()
                            return True

                        self._install_cancel(
                            request.request_id,
                            cancel_process_session,
                        )
                        result_holder.append(
                            self.transport.run(request.request_id, invocation, emit)
                        )
                except Exception as error:
                    if acp_transport is not None:
                        self.registry.mark_acp_failed(profile.adapter_id, profile.model)
                    transport_errors.append(error)
                finally:
                    transport_done.set()

            worker = threading.Thread(target=run_transport, daemon=True)
            worker.start()
            terminal_data: dict[str, object] = {}
            adapter_error = False
            approval_error: dict[str, object] | None = None
            response_bytes = 0
            response_content_limit = (
                RESPONSE_TEXT_LIMIT - len(TRUNCATION_MARKER.encode("utf-8"))
            )
            response_truncated = False
            provider_events = 0
            event_limit_reached = False
            cancel_started = False
            session_limit_error = False

            def cancel_without_blocking() -> None:
                nonlocal cancel_started
                if cancel_started:
                    return
                cancel_started = True
                threading.Thread(
                    target=self.cancel,
                    args=(request.request_id,),
                    daemon=True,
                ).start()

            def enforce_session_limit() -> None:
                nonlocal session_limit_error
                checker = getattr(adapter, "session_limit_exceeded", None)
                if (
                    not session_limit_error
                    and callable(checker)
                    and checker()
                ):
                    session_limit_error = True
                    cancel_without_blocking()

            while not transport_done.is_set() or not normalized.empty():
                try:
                    adapter_event = normalized.get(timeout=0.05)
                except queue.Empty:
                    enforce_session_limit()
                    continue
                if provider_events % 64 == 0:
                    enforce_session_limit()
                if provider_events >= EVENT_COUNT_LIMIT:
                    if not event_limit_reached:
                        event_limit_reached = True
                        cancel_without_blocking()
                        if not response_truncated:
                            response_truncated = True
                            yield Event("text_delta", request.request_id, {
                                "text": TRUNCATION_MARKER,
                            })
                    continue
                provider_events += 1
                if adapter_event.type in {"complete", "error"}:
                    combined = dict(terminal_data)
                    combined.update(adapter_event.data)
                    bounded_terminal = bounded_wire_value(combined)
                    terminal_data = (
                        bounded_terminal if isinstance(bounded_terminal, dict) else {}
                    )
                    adapter_error = adapter_error or adapter_event.type == "error"
                    continue
                if adapter_event.type == "tool_request":
                    if self._is_cancel_requested(request.request_id):
                        approval_error = {
                            "code": "approval_denied",
                            "message": "The operation was denied because the run was cancelled.",
                        }
                        continue
                    if adapter_event.data.get("_acpManaged"):
                        visible_data = dict(adapter_event.data)
                        visible_data.pop("_acpManaged", None)
                        yield Event("tool_request", request.request_id, visible_data)
                        continue
                    approval_id = adapter_event.data.get("approvalId")
                    if not isinstance(approval_id, str) or not approval_id:
                        approval_error = {
                            "code": "approval_not_relayable",
                            "message": "The CLI requested an invalid approval.",
                            "continueCommand": list(invocation.argv),
                        }
                        self.transport.cancel(request.request_id)
                        continue
                    if not adapter.capabilities.relayable_approvals:
                        approval_error = {
                            "code": "approval_not_relayable",
                            "message": "This CLI cannot relay approvals safely in process mode.",
                            "continueCommand": list(invocation.argv),
                        }
                        self.transport.cancel(request.request_id)
                        continue
                    approval_event = threading.Event()
                    approval_result: list[bool] = []
                    key = (request.request_id, approval_id)
                    with self._lock:
                        cancelled_before_approval = (
                            request.request_id in self._cancel_requested
                        )
                        if not cancelled_before_approval:
                            self._pending_approvals[key] = (
                                approval_event,
                                approval_result,
                            )
                    if cancelled_before_approval:
                        approval_error = {
                            "code": "approval_denied",
                            "message": "The operation was denied because the run was cancelled.",
                        }
                        continue
                    yield Event("tool_request", request.request_id, adapter_event.data)
                    resolved = approval_event.wait(self.approval_timeout_seconds)
                    with self._lock:
                        self._pending_approvals.pop(key, None)
                    approved = resolved and bool(approval_result and approval_result[0])
                    responder = getattr(self.transport, "respond_approval", None)
                    if responder is None:
                        approval_error = {
                            "code": "approval_not_relayable",
                            "message": "The active transport cannot relay this approval.",
                            "continueCommand": list(invocation.argv),
                        }
                        self.transport.cancel(request.request_id)
                    else:
                        responder(request.request_id, approval_id, approved)
                        if not approved:
                            approval_error = {
                                "code": "approval_timeout" if not resolved else "approval_denied",
                                "message": "The operation was denied.",
                            }
                    continue
                if adapter_event.type == "text_delta":
                    text = str(adapter_event.data.get("text", ""))
                    remaining = response_content_limit - response_bytes
                    if remaining <= 0:
                        if not response_truncated:
                            response_truncated = True
                            yield Event("text_delta", request.request_id, {
                                "text": TRUNCATION_MARKER,
                            })
                            response_bytes += len(TRUNCATION_MARKER.encode("utf-8"))
                        continue
                    text, truncated, retained_bytes = bounded_text_prefix(text, remaining)
                    if truncated:
                        text += TRUNCATION_MARKER
                        response_bytes += len(text.encode("utf-8"))
                        response_truncated = True
                    else:
                        response_bytes += retained_bytes
                    yield Event("text_delta", request.request_id, {"text": text})
                    continue
                if adapter_event.type in {
                    "status", "tool_request", "session"
                }:
                    yield Event(adapter_event.type, request.request_id, adapter_event.data)
            worker.join()

            if transport_errors:
                code = (
                    "not_installed"
                    if isinstance(transport_errors[0], FileNotFoundError)
                    else "acp_failed" if acp_transport is not None else "transport_failed"
                )
                yield Event("error", request.request_id, {
                    "code": code,
                    "message": str(transport_errors[0]),
                    **({"degradedTo": "process", "replayed": False}
                       if acp_transport is not None else {}),
                })
                return
            result = result_holder[0]

            if session_limit_error:
                yield Event("error", request.request_id, {
                    "code": "session_too_large",
                    "message": "The provider session exceeded Quick Chat's 4 MiB limit.",
                })
            elif approval_error is not None:
                yield Event("error", request.request_id, approval_error)
            elif result.timed_out:
                yield Event("error", request.request_id, {
                    "code": "timeout",
                    "message": "The CLI did not finish before the timeout.",
                    "diagnostic": result.stderr,
                })
            elif result.cancelled:
                yield Event("complete", request.request_id, {
                    "stopReason": "cancelled",
                })
            elif result.exit_code != 0:
                diagnostic_lower = result.stderr.lower()
                authentication_failure = any(pattern in diagnostic_lower for pattern in (
                    "authentication required",
                    "not authenticated",
                    "not logged in",
                    "login required",
                ))
                yield Event("error", request.request_id, {
                    "code": "authentication_required" if authentication_failure else "cli_failed",
                    "message": "The CLI exited with an error.",
                    "exitCode": result.exit_code,
                    "diagnostic": result.stderr,
                    **({"loginCommand": [invocation.argv[0], "login"]}
                       if authentication_failure else {}),
                })
            elif adapter_error:
                yield Event("error", request.request_id, {
                    "code": "adapter_error",
                    **terminal_data,
                })
            else:
                yield Event("complete", request.request_id, terminal_data)
        finally:
            if request.private and adapter is not None:
                private_cleanup = getattr(adapter, "cleanup_private_session", None)
                if callable(private_cleanup):
                    private_cleanup()
            if adapter is not None:
                finalize_session = getattr(adapter, "finalize_session", None)
                if callable(finalize_session):
                    finalize_session()
            if self.attachment_cleanup is not None:
                self.attachment_cleanup(tuple(
                    attachment.id for attachment in request.attachments
                ))
            self._release(request.request_id)
