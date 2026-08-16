"""Conversation retention with strict private-mode no-write behavior."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .models import Config, Conversation
from .paths import PathSet
from .storage import atomic_write_json, quarantine, recovery_diagnostic


class HistoryStore:
    def __init__(self, paths: PathSet, config: Config) -> None:
        self.paths = paths
        self.config = config
        self.last_diagnostic: dict[str, str] | None = None

    @staticmethod
    def _sort(conversations: list[Conversation]) -> list[Conversation]:
        return sorted(
            conversations,
            key=lambda conversation: datetime.fromisoformat(conversation.updated_at),
            reverse=True,
        )

    def _load(self) -> list[Conversation]:
        self.last_diagnostic = None
        if not self.paths.history_file.exists():
            return []
        try:
            with self.paths.history_file.open(encoding="utf-8") as stream:
                value: Any = json.load(stream)
            if not isinstance(value, dict) or value.get("schemaVersion") != 1:
                raise ValueError("unsupported history schema version")
            raw_conversations = value.get("conversations")
            if not isinstance(raw_conversations, list):
                raise ValueError("conversations must be an array")
            return self._sort([
                Conversation.from_dict(conversation)
                for conversation in raw_conversations
            ])
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            quarantined = quarantine(self.paths.history_file)
            self.last_diagnostic = recovery_diagnostic(quarantined, error)
            return []

    def list(self) -> list[Conversation]:
        return self._load()

    def upsert(self, conversation: Conversation, private: bool) -> None:
        if not isinstance(private, bool):
            raise ValueError("private must be a boolean")
        if private:
            return
        if not isinstance(conversation, Conversation):
            raise ValueError("conversation must be a Conversation record")

        conversations = [
            current for current in self._load() if current.id != conversation.id
        ]
        conversations.append(conversation)
        conversations = self._sort(conversations)

        profile = self.config.profile(conversation.profile_id)
        limit = (
            profile.history_limit
            if profile is not None and profile.history_limit is not None
            else self.config.history_limit
        )
        if limit is not None:
            conversations = conversations[:limit]

        atomic_write_json(
            self.paths.history_file,
            {
                "schemaVersion": 1,
                "conversations": [item.to_dict() for item in conversations],
            },
        )

    def clear(self) -> None:
        self.paths.history_file.unlink(missing_ok=True)
        self.last_diagnostic = None
