"""Single-turn orchestration across profiles, adapters, and transports."""

from __future__ import annotations

import threading
import queue
from pathlib import Path
from typing import Callable, Iterator

from .adapters.base import AdapterContext, AdapterEvent
from .adapters.registry import AdapterRegistry
from .models import Config
from .protocol import Event, Request
from .transports.base import Transport


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
        self._pending_approvals: dict[
            tuple[str, str], tuple[threading.Event, list[bool]]
        ] = {}

    def _claim(self, request_id: str) -> None:
        with self._lock:
            if self._active_request_id is not None:
                raise BusyError(f"request {self._active_request_id} is already running")
            self._active_request_id = request_id

    def _release(self, request_id: str) -> None:
        with self._lock:
            if self._active_request_id == request_id:
                self._active_request_id = None

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            if self._active_request_id != request_id:
                return False
        return self.transport.cancel(request_id)

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

            normalized: queue.Queue[AdapterEvent] = queue.Queue()
            result_holder = []
            transport_errors: list[Exception] = []
            transport_done = threading.Event()

            def emit(raw_event: AdapterEvent) -> None:
                for adapter_event in adapter.parse_event(raw_event):
                    normalized.put(adapter_event)

            def run_transport() -> None:
                try:
                    result_holder.append(
                        self.transport.run(request.request_id, invocation, emit)
                    )
                except Exception as error:
                    transport_errors.append(error)
                finally:
                    transport_done.set()

            worker = threading.Thread(target=run_transport, daemon=True)
            worker.start()
            terminal_data: dict[str, object] = {}
            adapter_error = False
            approval_error: dict[str, object] | None = None
            while not transport_done.is_set() or not normalized.empty():
                try:
                    adapter_event = normalized.get(timeout=0.05)
                except queue.Empty:
                    continue
                if adapter_event.type in {"complete", "error"}:
                    terminal_data.update(adapter_event.data)
                    adapter_error = adapter_error or adapter_event.type == "error"
                    continue
                if adapter_event.type == "tool_request":
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
                        self._pending_approvals[key] = (approval_event, approval_result)
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
                if adapter_event.type in {
                    "status", "text_delta", "tool_request", "session"
                }:
                    yield Event(adapter_event.type, request.request_id, adapter_event.data)
            worker.join()

            if transport_errors:
                code = (
                    "not_installed"
                    if isinstance(transport_errors[0], FileNotFoundError)
                    else "transport_failed"
                )
                yield Event("error", request.request_id, {
                    "code": code,
                    "message": str(transport_errors[0]),
                })
                return
            result = result_holder[0]

            if approval_error is not None:
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
            if self.attachment_cleanup is not None:
                self.attachment_cleanup(tuple(
                    attachment.id for attachment in request.attachments
                ))
            self._release(request.request_id)
