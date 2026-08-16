"""Validated domain records for Quick Chat configuration and history."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping


PROFILE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
WORKING_DIRECTORY_STRATEGIES = {"home", "fixed", "active-project"}
PERMISSION_POLICIES = {"read-only", "ask"}
MESSAGE_ROLES = {"user", "assistant", "system", "tool"}


def require_identifier(name: str, value: Any) -> str:
    """Return a non-empty identifier-like wire value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def require_optional_string(name: str, value: Any) -> str | None:
    """Return an optional string while rejecting implicit coercion."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string or null")
    return value


def validate_history_limit(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("history limit must be a positive integer or null")
    return value


def _string_tuple(name: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"{name} must contain only strings")
    return tuple(value)


def _require_timestamp(name: str, value: Any) -> str:
    timestamp = require_identifier(name, value)
    try:
        datetime.fromisoformat(timestamp)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    return timestamp


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    adapter_id: str
    model: str | None = None
    system_instructions: str = ""
    working_directory_strategy: Literal["home", "fixed", "active-project"] = "home"
    working_directory: str | None = None
    context_providers: tuple[str, ...] = ()
    permission_policy: Literal["read-only", "ask"] = "read-only"
    shortcut: str | None = None
    history_limit: int | None = None
    private_by_default: bool = False
    advanced_args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not PROFILE_ID_PATTERN.fullmatch(self.id):
            raise ValueError("profile id has an invalid format")
        require_identifier("profile name", self.name)
        require_identifier("adapter id", self.adapter_id)
        require_optional_string("model", self.model)
        if not isinstance(self.system_instructions, str):
            raise ValueError("system instructions must be a string")
        if self.working_directory_strategy not in WORKING_DIRECTORY_STRATEGIES:
            raise ValueError("invalid working directory strategy")
        require_optional_string("working directory", self.working_directory)
        if self.working_directory_strategy == "fixed":
            if not self.working_directory or not Path(self.working_directory).is_dir():
                raise ValueError("fixed working directory must exist")
        _string_tuple("context providers", self.context_providers)
        if self.permission_policy not in PERMISSION_POLICIES:
            raise ValueError("invalid permission policy")
        require_optional_string("shortcut", self.shortcut)
        validate_history_limit(self.history_limit)
        if not isinstance(self.private_by_default, bool):
            raise ValueError("privateByDefault must be a boolean")
        _string_tuple("advanced arguments", self.advanced_args)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "adapterId": self.adapter_id,
            "model": self.model,
            "systemInstructions": self.system_instructions,
            "workingDirectoryStrategy": self.working_directory_strategy,
            "workingDirectory": self.working_directory,
            "contextProviders": list(self.context_providers),
            "permissionPolicy": self.permission_policy,
            "shortcut": self.shortcut,
            "historyLimit": self.history_limit,
            "privateByDefault": self.private_by_default,
            "advancedArgs": list(self.advanced_args),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Profile:
        if not isinstance(value, Mapping):
            raise ValueError("profile must be an object")
        return cls(
            id=value.get("id"),
            name=value.get("name"),
            adapter_id=value.get("adapterId"),
            model=value.get("model"),
            system_instructions=value.get("systemInstructions", ""),
            working_directory_strategy=value.get("workingDirectoryStrategy", "home"),
            working_directory=value.get("workingDirectory"),
            context_providers=_string_tuple(
                "context providers", value.get("contextProviders", [])
            ),
            permission_policy=value.get("permissionPolicy", "read-only"),
            shortcut=value.get("shortcut"),
            history_limit=validate_history_limit(value.get("historyLimit")),
            private_by_default=value.get("privateByDefault", False),
            advanced_args=_string_tuple("advanced arguments", value.get("advancedArgs", [])),
        )


def default_profile(profile_id: str, name: str) -> Profile:
    return Profile(id=profile_id, name=name, adapter_id=profile_id)


DEFAULT_PROFILES = (
    default_profile("codex", "Codex"),
    default_profile("claude", "Claude Code"),
    default_profile("opencode", "OpenCode"),
    default_profile("grok", "Grok"),
    default_profile("cursor", "Cursor"),
    default_profile("pi", "Pi"),
)


@dataclass(frozen=True)
class Config:
    schema_version: int = 1
    profiles: tuple[Profile, ...] = DEFAULT_PROFILES
    selected_profile_id: str = "codex"
    history_limit: int | None = 20
    default_shortcut: str = "SUPER ALT, SPACE"

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported config schema version")
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise ValueError("config must contain at least one profile")
        identifiers = [profile.id for profile in self.profiles]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("profile ids must be unique")
        if self.selected_profile_id not in identifiers:
            raise ValueError("selected profile does not exist")
        validate_history_limit(self.history_limit)
        require_identifier("default shortcut", self.default_shortcut)

    @classmethod
    def default(cls) -> Config:
        return cls()

    def profile(self, profile_id: str) -> Profile | None:
        return next((profile for profile in self.profiles if profile.id == profile_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "selectedProfileId": self.selected_profile_id,
            "historyLimit": self.history_limit,
            "defaultShortcut": self.default_shortcut,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Config:
        if not isinstance(value, Mapping):
            raise ValueError("config must be an object")
        profiles = value.get("profiles")
        if not isinstance(profiles, list):
            raise ValueError("profiles must be an array")
        return cls(
            schema_version=value.get("schemaVersion"),
            profiles=tuple(Profile.from_dict(profile) for profile in profiles),
            selected_profile_id=value.get("selectedProfileId"),
            history_limit=validate_history_limit(value.get("historyLimit")),
            default_shortcut=value.get("defaultShortcut", "SUPER ALT, SPACE"),
        )


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    created_at: str
    attachment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in MESSAGE_ROLES:
            raise ValueError("invalid message role")
        if not isinstance(self.content, str):
            raise ValueError("message content must be a string")
        _require_timestamp("message createdAt", self.created_at)
        _string_tuple("attachment ids", self.attachment_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "createdAt": self.created_at,
            "attachmentIds": list(self.attachment_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Message:
        if not isinstance(value, Mapping):
            raise ValueError("message must be an object")
        return cls(
            role=value.get("role"),
            content=value.get("content"),
            created_at=value.get("createdAt"),
            attachment_ids=_string_tuple("attachment ids", value.get("attachmentIds", [])),
        )


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    profile_id: str
    created_at: str
    updated_at: str
    messages: tuple[Message, ...] = ()
    cli_sessions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_identifier("conversation id", self.id)
        require_identifier("conversation title", self.title)
        require_identifier("profile id", self.profile_id)
        _require_timestamp("conversation createdAt", self.created_at)
        _require_timestamp("conversation updatedAt", self.updated_at)
        if not isinstance(self.messages, tuple) or not all(
            isinstance(message, Message) for message in self.messages
        ):
            raise ValueError("messages must contain Message records")
        if not isinstance(self.cli_sessions, dict) or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in self.cli_sessions.items()
        ):
            raise ValueError("CLI sessions must map strings to non-empty strings")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "profileId": self.profile_id,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
            "cliSessions": dict(self.cli_sessions),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Conversation:
        if not isinstance(value, Mapping):
            raise ValueError("conversation must be an object")
        messages = value.get("messages", [])
        sessions = value.get("cliSessions", {})
        if not isinstance(messages, list):
            raise ValueError("messages must be an array")
        if not isinstance(sessions, dict):
            raise ValueError("cliSessions must be an object")
        return cls(
            id=value.get("id"),
            title=value.get("title"),
            profile_id=value.get("profileId"),
            created_at=value.get("createdAt"),
            updated_at=value.get("updatedAt"),
            messages=tuple(Message.from_dict(message) for message in messages),
            cli_sessions=dict(sessions),
        )
