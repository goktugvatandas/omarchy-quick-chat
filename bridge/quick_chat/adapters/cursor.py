"""Read-only Cursor agent CLI adapter."""

from __future__ import annotations

from pathlib import Path

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation
from .json_process import JsonProcessAdapter
from ..model_discovery import discover_command_models


class CursorAdapter(JsonProcessAdapter):
    id = "cursor"
    executable = "cursor-agent"
    _capabilities = Capabilities(True, True, True, False, True, False)

    def discover_models(self, cwd: Path | None = None):
        return discover_command_models(("cursor-agent", "models"), "cursor", cwd)

    def start(self, context: AdapterContext) -> Invocation:
        prompt = context.prompt
        if context.system_instructions:
            prompt = f"{context.system_instructions}\n\nUser question:\n{context.prompt}"
        arguments = ["cursor-agent", "-p", prompt]
        if not self._degraded:
            arguments.extend(("--output-format", "stream-json"))
        if context.model:
            arguments.extend(("--model", context.model))
        if context.session_id and not self._degraded:
            arguments.append(f"--resume={context.session_id}")
        return Invocation(tuple(arguments), context.cwd, self.environment(), None)

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        value = self.decode(event)
        if value is None:
            return []
        plain = self.plain_event(value)
        if plain is not None:
            return plain
        event_type = value.get("type")
        if event_type in {"system", "session"}:
            session_id = value.get("session_id")
            if isinstance(session_id, str):
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type in {"assistant", "text_delta"}:
            delta = value.get("delta")
            text = value.get("text")
            if isinstance(delta, dict):
                text = delta.get("text")
            if isinstance(text, str):
                return [AdapterEvent("text_delta", {"text": text})]
        if event_type == "result":
            if value.get("is_error"):
                return [AdapterEvent("error", {"message": str(value.get("result", "Cursor failed"))})]
            return [AdapterEvent("complete", {})]
        return []
