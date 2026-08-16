"""Pi CLI adapter restricted to read-only tools."""

from __future__ import annotations

import uuid
from pathlib import Path

from ..paths import PathSet
from .base import AdapterContext, AdapterEvent, Capabilities, Invocation
from .json_process import JsonProcessAdapter
from ..model_discovery import (
    ModelDiscoveryError,
    discover_command_models,
    discover_help_efforts,
)


class PiAdapter(JsonProcessAdapter):
    id = "pi"
    executable = "pi"
    _capabilities = Capabilities(True, True, True, True, True, False, True)

    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__()
        self.state_dir = state_dir or PathSet.from_env().state_dir / "pi-sessions"
        self._private_session_path: Path | None = None

    def discover_models(self, cwd: Path | None = None):
        return discover_command_models(("pi", "--list-models"), "pi", cwd)

    def effort_options(self, cwd: Path | None = None):
        try:
            return discover_help_efforts(("pi", "--help"), "--thinking", cwd)
        except ModelDiscoveryError:
            return ()

    def _session_path(self, session_id: str | None, private: bool = False) -> Path:
        if private:
            directory = PathSet.from_env().capture_dir / "pi-sessions"
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
            self._private_session_path = directory / f"{uuid.uuid4()}.jsonl"
            return self._private_session_path
        if session_id:
            candidate = Path(session_id).expanduser().resolve()
            if candidate.is_relative_to(self.state_dir.resolve()):
                return candidate
        return self.state_dir / f"{uuid.uuid4()}.jsonl"

    def start(self, context: AdapterContext) -> Invocation:
        arguments = [
            "pi",
            "-p",
            "--mode",
            "json" if not self._degraded else "text",
            "--tools",
            "read,grep,find,ls",
        ]
        if context.model:
            if "/" in context.model:
                provider, model = context.model.split("/", 1)
                arguments.extend(("--provider", provider, "--model", model))
            else:
                arguments.extend(("--model", context.model))
        if context.thinking_effort:
            arguments.extend(("--thinking", context.thinking_effort))
        session_path = self._session_path(context.session_id, context.private)
        arguments.extend(("--session", str(session_path)))
        for attachment in context.attachments:
            if attachment.kind == "image" and attachment.path:
                arguments.append("@" + attachment.path)
        prompt = context.prompt
        if context.system_instructions:
            prompt = f"{context.system_instructions}\n\nUser question:\n{context.prompt}"
        arguments.append(prompt)
        return Invocation(tuple(arguments), context.cwd, self.environment(), None)

    def cleanup_private_session(self) -> None:
        path = self._private_session_path
        self._private_session_path = None
        if path is None or path.is_symlink():
            return
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        value = self.decode(event)
        if value is None:
            return []
        plain = self.plain_event(value)
        if plain is not None:
            return plain
        event_type = value.get("type")
        if event_type in {"session", "session_start"}:
            session_id = value.get("session_id")
            if isinstance(session_id, str):
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type in {"message_update", "assistant"}:
            if value.get("role", "assistant") == "assistant":
                text = value.get("delta") or value.get("text")
                if isinstance(text, str):
                    return [AdapterEvent("text_delta", {"text": text})]
        if event_type in {"agent_end", "complete"}:
            return [AdapterEvent("complete", {"stopReason": value.get("reason", "stop")})]
        if event_type == "error":
            return [AdapterEvent("error", {"message": str(value.get("message", "Pi failed"))})]
        return []
