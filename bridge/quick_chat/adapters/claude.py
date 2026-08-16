"""Read-only Claude Code CLI adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation, ModelOption
from .process_base import ProcessAdapterBase
from ..model_discovery import ModelDiscoveryError, discover_help_efforts


class ClaudeAdapter(ProcessAdapterBase):
    id = "claude"
    executable = "claude"
    _capabilities = Capabilities(
        streaming=True,
        resume=True,
        model=True,
        native_images=False,
        read_only_enforced=True,
        relayable_approvals=False,
        thinking_effort=True,
    )

    def __init__(self) -> None:
        super().__init__()
        self._saw_stream_delta = False

    def discover_models(self, cwd: Path | None = None) -> tuple[ModelOption, ...]:
        return (
            ModelOption("sonnet", "Sonnet", "Claude Code model alias"),
            ModelOption("opus", "Opus", "Claude Code model alias"),
            ModelOption("haiku", "Haiku", "Claude Code model alias"),
        )

    def effort_options(self, cwd: Path | None = None):
        try:
            return discover_help_efforts(("claude", "--help"), "--effort", cwd)
        except ModelDiscoveryError:
            return ()

    def start(self, context: AdapterContext) -> Invocation:
        arguments = ["claude", "-p"]
        if not self._degraded:
            arguments.extend(("--verbose", "--output-format", "stream-json"))
        else:
            arguments.extend(("--output-format", "text"))
        arguments.extend((
            "--permission-mode",
            "plan",
            "--disallowedTools",
            "Bash",
            "Edit",
            "Write",
            "NotebookEdit",
        ))
        if context.model:
            arguments.extend(("--model", context.model))
        if context.thinking_effort:
            arguments.extend(("--effort", context.thinking_effort))
        if context.session_id and not self._degraded:
            arguments.extend(("--resume", context.session_id))
        if context.system_instructions:
            arguments.extend(("--append-system-prompt", context.system_instructions))
        arguments.append(context.prompt)
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        return Invocation(tuple(arguments), context.cwd, environment, None)

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        if event.type != "stdout":
            return []
        text = str(event.data.get("text", ""))
        if self._degraded:
            return [AdapterEvent("text_delta", {"text": text + "\n"})]
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            self.degrade()
            return [AdapterEvent("text_delta", {"text": text + "\n"})]
        if not isinstance(value, dict):
            self.degrade()
            return [AdapterEvent("text_delta", {"text": text + "\n"})]

        event_type = value.get("type")
        if event_type == "system" and value.get("subtype") == "init":
            session_id = value.get("session_id")
            if isinstance(session_id, str) and session_id:
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type == "stream_event":
            stream_event = value.get("event", {})
            if isinstance(stream_event, dict) and stream_event.get("type") == "content_block_delta":
                delta = stream_event.get("delta", {})
                if isinstance(delta, dict) and delta.get("type") == "text_delta":
                    delta_text = delta.get("text")
                    if isinstance(delta_text, str) and delta_text:
                        self._saw_stream_delta = True
                        return [AdapterEvent("text_delta", {"text": delta_text})]
        if event_type == "assistant" and not self._saw_stream_delta:
            message = value.get("message", {})
            content = message.get("content", []) if isinstance(message, dict) else []
            if isinstance(content, list):
                text_parts = [
                    item.get("text")
                    for item in content
                    if isinstance(item, dict)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ]
                if text_parts:
                    return [AdapterEvent("text_delta", {"text": "".join(text_parts)})]
        if event_type == "result":
            if value.get("is_error") or value.get("subtype") in {"error", "failure"}:
                message = value.get("result") or value.get("error") or "Claude failed"
                return [AdapterEvent("error", {"message": str(message)})]
            return [AdapterEvent("complete", {
                "sessionId": value.get("session_id"),
            })]
        return []
