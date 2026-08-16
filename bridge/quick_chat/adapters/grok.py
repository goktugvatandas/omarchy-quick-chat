"""Read-only Grok CLI process adapter."""

from __future__ import annotations

from pathlib import Path

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation
from .json_process import JsonProcessAdapter
from ..model_discovery import (
    ModelDiscoveryError,
    discover_command_models,
    discover_help_efforts,
)


class GrokAdapter(JsonProcessAdapter):
    id = "grok"
    executable = "grok"
    _capabilities = Capabilities(True, True, True, False, True, False, True)

    def discover_models(self, cwd: Path | None = None):
        return discover_command_models(
            ("grok", "--no-auto-update", "models"), "grok", cwd
        )

    def effort_options(self, cwd: Path | None = None):
        try:
            return discover_help_efforts(
                ("grok", "--help"), "--reasoning-effort", cwd
            )
        except ModelDiscoveryError:
            return ()

    def acp_argv(self) -> tuple[str, ...]:
        return ("grok", "agent", "stdio")

    def start(self, context: AdapterContext) -> Invocation:
        prompt = context.prompt
        if context.system_instructions:
            prompt = f"{context.system_instructions}\n\nUser question:\n{context.prompt}"
        arguments = [
            "grok",
            "-p",
            prompt,
            "--output-format",
            "streaming-json" if not self._degraded else "text",
            "--cwd",
            str(context.cwd),
            "--tools",
            "read_file,grep,list_dir",
            "--disallowed-tools",
            "Agent",
        ]
        if context.model:
            arguments.extend(("--model", context.model))
        if context.thinking_effort:
            arguments.extend(("--reasoning-effort", context.thinking_effort))
        if context.session_id and not self._degraded:
            arguments.extend(("--session-id", context.session_id))
        return Invocation(tuple(arguments), context.cwd, self.environment(), None)

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        value = self.decode(event)
        if value is None:
            return []
        plain = self.plain_event(value)
        if plain is not None:
            return plain
        event_type = value.get("type")
        if event_type in {"session", "session_start"}:
            session_id = value.get("session_id") or value.get("sessionId")
            if isinstance(session_id, str):
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type == "text":
            text = value.get("content") or value.get("text") or value.get("data")
            if isinstance(text, str):
                return [AdapterEvent("text_delta", {"text": text})]
        if event_type in {"end", "complete"}:
            events: list[AdapterEvent] = []
            session_id = value.get("session_id") or value.get("sessionId")
            if isinstance(session_id, str) and session_id:
                events.append(AdapterEvent("session", {"sessionId": session_id}))
            events.append(AdapterEvent("complete", {
                "stopReason": value.get("reason")
                or value.get("stopReason")
                or "end_turn",
            }))
            return events
        if event_type == "error":
            return [AdapterEvent("error", {"message": str(value.get("message", "Grok failed"))})]
        return []
