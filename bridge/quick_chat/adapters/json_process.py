"""Small helpers shared by JSONL process adapters."""

from __future__ import annotations

import json
import os

from .base import AdapterEvent
from .process_base import ProcessAdapterBase


class JsonProcessAdapter(ProcessAdapterBase):
    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        return environment

    def decode(self, event: AdapterEvent) -> dict[str, object] | None:
        if event.type != "stdout":
            return None
        text = str(event.data.get("text", ""))
        if self._degraded:
            return {"__plain_text": text + "\n"}
        if self.is_launcher_preamble(text):
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            self.degrade()
            return {"__plain_text": text + "\n"}
        if not isinstance(value, dict):
            self.degrade()
            return {"__plain_text": text + "\n"}
        return value

    @staticmethod
    def plain_event(value: dict[str, object]) -> list[AdapterEvent] | None:
        text = value.get("__plain_text")
        if isinstance(text, str):
            return [AdapterEvent("text_delta", {"text": text})]
        return None
