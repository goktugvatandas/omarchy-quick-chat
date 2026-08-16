"""Persistent Agent Client Protocol version-one transport."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..adapters.base import AdapterEvent


class AcpError(RuntimeError):
    pass


class AcpDisconnected(AcpError):
    pass


class AcpProtocolError(AcpError):
    pass


@dataclass(frozen=True)
class AcpSession:
    id: str
    cwd: Path


@dataclass(frozen=True)
class AcpPromptResult:
    stop_reason: str


def text_block(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def image_block(path: Path, mime_type: str = "image/png") -> dict[str, object]:
    return {"type": "image", "path": str(path), "mimeType": mime_type}


class AcpTransport:
    def __init__(
        self,
        argv: tuple[str, ...],
        permission_handler: Callable[[dict[str, object]], bool] | None = None,
        idle_seconds: float = 10 * 60,
        request_timeout: float = 30,
    ) -> None:
        if not argv or not all(isinstance(value, str) and value for value in argv):
            raise ValueError("ACP argv must contain non-empty strings")
        self.argv = argv
        self.permission_handler = permission_handler or (lambda request: False)
        self.idle_seconds = idle_seconds
        self.request_timeout = request_timeout
        self.protocol_version: int | None = None
        self.loaded_session_id: str | None = None
        self.permission_responses: list[bool] = []
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int, queue.Queue[object]] = {}
        self._sessions: dict[str, AcpSession] = {}
        self._update_callback: Callable[[AdapterEvent], None] | None = None
        self._active_session_id: str | None = None
        self._idle_timer: threading.Timer | None = None

    @property
    def running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def _touch_idle(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(self.idle_seconds, self.close)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _start(self) -> None:
        if self.running:
            return
        self._process = subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        result = self._send_request("initialize", {
            "protocolVersion": 1,
            "clientInfo": {"name": "omarchy-quick-chat", "version": "0.1.0"},
            "clientCapabilities": {
                "fs": {"readTextFile": False, "writeTextFile": False},
                "terminal": False,
            },
        })
        version = result.get("protocolVersion") if isinstance(result, dict) else None
        if version != 1:
            self.close()
            raise AcpProtocolError(f"ACP protocol version {version!r} is incompatible")
        self.protocol_version = 1
        self._touch_idle()

    def _write(self, value: dict[str, object]) -> None:
        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            raise AcpDisconnected("ACP agent is not running")
        encoded = json.dumps(value, separators=(",", ":")) + "\n"
        with self._write_lock:
            try:
                process.stdin.write(encoded)
                process.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                raise AcpDisconnected("ACP agent disconnected") from error

    def _send_request(self, method: str, params: dict[str, object]) -> object:
        with self._state_lock:
            request_id = self._next_id
            self._next_id += 1
            response_queue: queue.Queue[object] = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
        try:
            self._write({
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            })
            try:
                response = response_queue.get(timeout=self.request_timeout)
            except queue.Empty as error:
                raise AcpError(f"ACP request timed out: {method}") from error
            if isinstance(response, Exception):
                raise response
            if not isinstance(response, dict):
                raise AcpProtocolError("ACP response is not an object")
            if "error" in response:
                raise AcpError(str(response["error"]))
            return response.get("result", {})
        finally:
            with self._state_lock:
                self._pending.pop(request_id, None)

    def _read_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(value, dict):
                    continue
                message_id = value.get("id")
                method = value.get("method")
                if isinstance(message_id, int) and method is None:
                    with self._state_lock:
                        pending = self._pending.get(message_id)
                    if pending is not None:
                        pending.put(value)
                elif isinstance(message_id, int) and isinstance(method, str):
                    self._handle_agent_request(message_id, method, value.get("params"))
                elif method == "session/update":
                    self._handle_update(value.get("params"))
        finally:
            error = AcpDisconnected("ACP agent disconnected")
            with self._state_lock:
                pending = list(self._pending.values())
            for response_queue in pending:
                try:
                    response_queue.put_nowait(error)
                except queue.Full:
                    pass

    def _handle_agent_request(self, request_id: int, method: str, params: object) -> None:
        if method != "session/request_permission" or not isinstance(params, dict):
            self._write({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "Method not supported"},
            })
            return
        approved = bool(self.permission_handler(dict(params)))
        self.permission_responses.append(approved)
        self._write({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"approved": approved},
        })

    def _handle_update(self, params: object) -> None:
        if not isinstance(params, dict) or self._update_callback is None:
            return
        update = params.get("update")
        if not isinstance(update, dict):
            return
        update_type = update.get("sessionUpdate")
        if update_type == "agent_message_chunk":
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text")
                if isinstance(text, str):
                    self._update_callback(AdapterEvent("text_delta", {"text": text}))
        elif update_type in {"tool_call", "tool_call_update", "plan"}:
            self._update_callback(AdapterEvent("status", {
                "status": str(update_type),
                "details": update,
            }))

    def open_session(self, cwd: Path, existing_id: str | None) -> AcpSession:
        if not cwd.is_absolute() or not cwd.is_dir():
            raise ValueError("ACP session cwd must be an existing absolute directory")
        self._start()
        if existing_id:
            result = self._send_request("session/load", {
                "sessionId": existing_id,
                "cwd": str(cwd),
                "mcpServers": [],
            })
            session_id = existing_id
            if isinstance(result, dict) and isinstance(result.get("sessionId"), str):
                session_id = result["sessionId"]
            self.loaded_session_id = session_id
        else:
            result = self._send_request("session/new", {
                "cwd": str(cwd),
                "mcpServers": [],
            })
            session_id = result.get("sessionId") if isinstance(result, dict) else None
            if not isinstance(session_id, str) or not session_id:
                raise AcpProtocolError("ACP session/new returned no sessionId")
        session = AcpSession(session_id, cwd)
        self._sessions[session.id] = session
        self._touch_idle()
        return session

    def prompt(
        self,
        session_id: str,
        content: list[dict[str, object]],
        emit: Callable[[AdapterEvent], None],
    ) -> AcpPromptResult:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("unknown ACP session")
        if not self.running:
            self._start()
            self.open_session(session.cwd, session_id)
        self._update_callback = emit
        self._active_session_id = session_id
        try:
            result = self._send_request("session/prompt", {
                "sessionId": session_id,
                "prompt": content,
            })
        finally:
            self._update_callback = None
            self._active_session_id = None
            self._touch_idle()
        stop_reason = result.get("stopReason") if isinstance(result, dict) else None
        return AcpPromptResult(str(stop_reason or "end_turn"))

    def cancel(self, session_id: str) -> bool:
        if not self.running or session_id not in self._sessions:
            return False
        self._send_request("session/cancel", {"sessionId": session_id})
        self._touch_idle()
        return True

    def disconnect(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if self._reader is not None:
            self._reader.join(timeout=1)
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        self._process = None
        self._reader = None
        self.protocol_version = None

    def close(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        self.disconnect()
