"""Conversation retention with strict private-mode no-write behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from typing import Any

from .models import Config, Conversation
from .paths import PathSet
from .sanitize import (
    HISTORY_CONVERSATION_LIMIT,
    HISTORY_FILE_LIMIT,
    HISTORY_MESSAGE_BYTES,
    HISTORY_MESSAGE_LIMIT,
    truncate_text,
)
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

    @staticmethod
    def _bounded(conversation: Conversation) -> Conversation:
        messages = tuple(
            replace(message, content=truncate_text(message.content, HISTORY_MESSAGE_BYTES))
            for message in conversation.messages[-HISTORY_MESSAGE_LIMIT:]
        )
        return replace(conversation, messages=messages)

    @staticmethod
    def _payload(conversations: list[Conversation]) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "conversations": [item.to_dict() for item in conversations],
        }

    @classmethod
    def _payload_size(cls, conversations: list[Conversation]) -> int:
        serialized = json.dumps(
            cls._payload(conversations),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n"
        return len(serialized.encode("utf-8"))

    def _prune_quarantines(self) -> None:
        quarantines = sorted(
            self.paths.state_dir.glob(f"{self.paths.history_file.name}.corrupt-*"),
            key=lambda path: path.name,
            reverse=True,
        )
        retained_bytes = 0
        for index, path in enumerate(quarantines):
            try:
                size = path.stat().st_size
                keep = (
                    index < 3
                    and size <= HISTORY_FILE_LIMIT
                    and retained_bytes + size <= 2 * HISTORY_FILE_LIMIT
                )
                if keep:
                    retained_bytes += size
                elif path.is_file() and not path.is_symlink():
                    path.unlink(missing_ok=True)
            except OSError:
                continue

    def _load(self) -> list[Conversation]:
        self.last_diagnostic = None
        if not self.paths.history_file.exists():
            return []
        try:
            if self.paths.history_file.stat().st_size > HISTORY_FILE_LIMIT:
                raise ValueError("history exceeds the 32 MiB storage limit")
            with self.paths.history_file.open(encoding="utf-8") as stream:
                value: Any = json.load(stream)
            if not isinstance(value, dict) or value.get("schemaVersion") != 1:
                raise ValueError("unsupported history schema version")
            raw_conversations = value.get("conversations")
            if not isinstance(raw_conversations, list):
                raise ValueError("conversations must be an array")
            return self._sort([
                self._bounded(Conversation.from_dict(conversation))
                for conversation in raw_conversations
            ])[:HISTORY_CONVERSATION_LIMIT]
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            quarantined = quarantine(self.paths.history_file)
            self.last_diagnostic = recovery_diagnostic(quarantined, error)
            self._prune_quarantines()
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
        conversation = self._bounded(conversation)

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
        conversations = conversations[:HISTORY_CONVERSATION_LIMIT]

        if self._payload_size(conversations) > HISTORY_FILE_LIMIT:
            low = 0
            high = len(conversations)
            while low < high:
                candidate_count = (low + high + 1) // 2
                if self._payload_size(
                    conversations[:candidate_count]
                ) <= HISTORY_FILE_LIMIT:
                    low = candidate_count
                else:
                    high = candidate_count - 1
            conversations = conversations[:low]

        atomic_write_json(self.paths.history_file, self._payload(conversations))

    def clear(self) -> None:
        self.paths.history_file.unlink(missing_ok=True)
        self.last_diagnostic = None
