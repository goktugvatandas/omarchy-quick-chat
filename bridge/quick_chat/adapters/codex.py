"""Read-only Codex CLI adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation
from .process_base import ProcessAdapterBase
from ..model_discovery import discover_codex_models


class CodexAdapter(ProcessAdapterBase):
    id = "codex"
    executable = "codex"
    _capabilities = Capabilities(
        streaming=True,
        resume=True,
        model=True,
        native_images=True,
        read_only_enforced=True,
        relayable_approvals=False,
    )

    def discover_models(self, cwd: Path | None = None):
        return discover_codex_models(cwd)

    def start(self, context: AdapterContext) -> Invocation:
        arguments = ["codex", "exec"]
        if not self._degraded:
            arguments.append("--json")
        arguments.extend((
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--cd",
            str(context.cwd),
        ))
        if context.model:
            arguments.extend(("--model", context.model))
        for attachment in context.attachments:
            if attachment.kind == "image" and attachment.path:
                arguments.extend(("--image", attachment.path))
        if context.session_id and not self._degraded:
            arguments.extend(("resume", context.session_id, "-"))
        else:
            arguments.append("-")

        prompt = context.prompt
        if context.system_instructions:
            prompt = f"{context.system_instructions}\n\nUser question:\n{context.prompt}"
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        return Invocation(tuple(arguments), context.cwd, environment, prompt)

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
        if event_type in {"thread.started", "session.started"}:
            session_id = value.get("thread_id") or value.get("session_id")
            if isinstance(session_id, str) and session_id:
                return [AdapterEvent("session", {"sessionId": session_id})]
        if event_type in {
            "item.updated",
            "item.completed",
            "response.output_text.delta",
        }:
            item = value.get("item", {})
            delta = value.get("delta")
            assistant_text = None
            if isinstance(item, dict) and item.get("type") in {
                "agent_message",
                "assistant_message",
            }:
                assistant_text = item.get("text")
            if assistant_text is None and isinstance(delta, str):
                assistant_text = delta
            if isinstance(assistant_text, str) and assistant_text:
                return [AdapterEvent("text_delta", {"text": assistant_text})]
        if event_type in {"turn.completed", "response.completed"}:
            data: dict[str, object] = {}
            if isinstance(value.get("usage"), dict):
                data["usage"] = value["usage"]
            return [AdapterEvent("complete", data)]
        if event_type in {"turn.failed", "error"}:
            message = value.get("message") or value.get("error") or "Codex failed"
            return [AdapterEvent("error", {"message": str(message)})]
        return []
