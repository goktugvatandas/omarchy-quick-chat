"""Read-only OpenCode non-interactive adapter."""

from __future__ import annotations

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation
from .json_process import JsonProcessAdapter


class OpenCodeAdapter(JsonProcessAdapter):
    id = "opencode"
    executable = "opencode"
    _capabilities = Capabilities(True, True, True, True, True, False)

    def start(self, context: AdapterContext) -> Invocation:
        arguments = [
            "opencode",
            "run",
            "--format",
            "json" if not self._degraded else "text",
            "--dir",
            str(context.cwd),
        ]
        if context.model:
            arguments.extend(("--model", context.model))
        if context.session_id and not self._degraded:
            arguments.extend(("--session", context.session_id))
        for attachment in context.attachments:
            if attachment.path:
                arguments.extend(("--file", attachment.path))
        prompt = context.prompt
        if context.system_instructions:
            prompt = f"{context.system_instructions}\n\nUser question:\n{context.prompt}"
        arguments.append(prompt)
        return Invocation(tuple(arguments), context.cwd, self.environment(), None)

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        value = self.decode(event)
        if value is None:
            return []
        plain = self.plain_event(value)
        if plain is not None:
            return plain
        event_type = value.get("type")
        if event_type in {"session", "session.created"}:
            session_id = value.get("sessionID") or value.get("session_id")
            if isinstance(session_id, str):
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type in {"text", "message.part.updated"}:
            text = value.get("text")
            part = value.get("part")
            if text is None and isinstance(part, dict):
                text = part.get("text")
            if isinstance(text, str) and text:
                return [AdapterEvent("text_delta", {"text": text})]
        if event_type in {"step_finish", "session.idle", "complete"}:
            return [AdapterEvent("complete", {"stopReason": value.get("reason", "stop")})]
        if event_type in {"error", "session.error"}:
            return [AdapterEvent("error", {"message": str(value.get("message", "OpenCode failed"))})]
        return []
