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
    ) -> None:
        self.registry = registry
        self.transport = transport
        self.config = config
        self.session_resolver = session_resolver
        self._lock = threading.Lock()
        self._active_request_id: str | None = None

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
            adapter = self.registry.get(profile.adapter_id)
            cwd = (
                Path(profile.working_directory)
                if profile.working_directory_strategy == "fixed"
                else Path.home()
            )
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
            while not transport_done.is_set() or not normalized.empty():
                try:
                    adapter_event = normalized.get(timeout=0.05)
                except queue.Empty:
                    continue
                if adapter_event.type in {"complete", "error"}:
                    terminal_data.update(adapter_event.data)
                    adapter_error = adapter_error or adapter_event.type == "error"
                    continue
                if adapter_event.type in {
                    "status", "text_delta", "tool_request", "session"
                }:
                    yield Event(adapter_event.type, request.request_id, adapter_event.data)
            worker.join()

            if transport_errors:
                yield Event("error", request.request_id, {
                    "code": "transport_failed",
                    "message": str(transport_errors[0]),
                })
                return
            result = result_holder[0]

            if result.timed_out:
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
                yield Event("error", request.request_id, {
                    "code": "cli_failed",
                    "message": "The CLI exited with an error.",
                    "exitCode": result.exit_code,
                    "diagnostic": result.stderr,
                })
            elif adapter_error:
                yield Event("error", request.request_id, {
                    "code": "adapter_error",
                    **terminal_data,
                })
            else:
                yield Event("complete", request.request_id, terminal_data)
        finally:
            self._release(request.request_id)
