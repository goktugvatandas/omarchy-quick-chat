"""Single-turn orchestration across profiles, adapters, and transports."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Iterator

from .adapters.base import AdapterContext, AdapterEvent
from .adapters.registry import AdapterRegistry
from .models import Config
from .protocol import Event, Request
from .transports.base import Transport


class BusyError(RuntimeError):
    pass


class Engine:
    def __init__(self, registry: AdapterRegistry, transport: Transport, config: Config) -> None:
        self.registry = registry
        self.transport = transport
        self.config = config
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
                system_instructions=profile.system_instructions,
            )
            invocation = adapter.start(context)
            yield Event("status", request.request_id, {
                "status": "starting",
                "adapterId": profile.adapter_id,
            })

            normalized: list[AdapterEvent] = []

            def emit(raw_event: AdapterEvent) -> None:
                normalized.extend(adapter.parse_event(raw_event))

            result = self.transport.run(request.request_id, invocation, emit)
            terminal_data: dict[str, object] = {}
            for adapter_event in normalized:
                if adapter_event.type in {"complete", "error"}:
                    terminal_data.update(adapter_event.data)
                    continue
                if adapter_event.type in {
                    "status", "text_delta", "tool_request", "session"
                }:
                    yield Event(adapter_event.type, request.request_id, adapter_event.data)

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
            else:
                yield Event("complete", request.request_id, terminal_data)
        finally:
            self._release(request.request_id)
