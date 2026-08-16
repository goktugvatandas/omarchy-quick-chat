"""Version-one JSON Lines protocol used by QML and the bridge."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .models import require_identifier, require_optional_string
from .paths import PathSet


MAX_REQUEST_BYTES = 1024 * 1024

REQUEST_TYPES = frozenset({
    "run",
    "cancel",
    "approve",
    "deny",
    "probe",
    "profiles",
    "history.list",
    "history.get",
    "history.clear",
    "context.capture",
    "context.ocr",
    "context.remove",
})

EVENT_TYPES = frozenset({
    "ready",
    "status",
    "text_delta",
    "tool_request",
    "session",
    "complete",
    "error",
})


class ProtocolError(ValueError):
    """A request or event violates the bridge wire contract."""

    def __init__(self, message: str, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Attachment:
    id: str
    kind: Literal["image", "text", "metadata"]
    path: str | None
    text: str | None
    mime_type: str

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        capture_root: Path,
    ) -> Attachment:
        if not isinstance(value, Mapping):
            raise ProtocolError("attachments must contain objects")

        try:
            attachment_id = require_identifier("attachment id", value.get("id"))
            mime_type = require_identifier("mimeType", value.get("mimeType"))
            path = require_optional_string("path", value.get("path"))
            text = require_optional_string("text", value.get("text"))
        except ValueError as error:
            raise ProtocolError(str(error)) from error

        kind = value.get("kind")
        if kind not in {"image", "text", "metadata"}:
            raise ProtocolError("attachment kind must be image, text, or metadata")
        if path is None and text is None:
            raise ProtocolError("attachment must include path or text")
        if path is not None:
            candidate = Path(path).expanduser().resolve()
            root = capture_root.expanduser().resolve()
            if not candidate.is_relative_to(root):
                raise ProtocolError("attachment path is outside the runtime capture root")

        return cls(
            id=attachment_id,
            kind=kind,
            path=path,
            text=text,
            mime_type=mime_type,
        )


@dataclass(frozen=True)
class Request:
    type: str
    request_id: str
    conversation_id: str | None = None
    profile_id: str | None = None
    prompt: str | None = None
    attachments: tuple[Attachment, ...] = ()
    private: bool = False
    confirm: bool = False
    mode: str | None = None
    attachment_id: str | None = None
    query: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Request:
        if not isinstance(value, Mapping):
            raise ProtocolError("request must be a JSON object")
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ProtocolError("request is not valid JSON data") from error
        if len(encoded) > MAX_REQUEST_BYTES:
            raise ProtocolError("request body exceeds 1 MiB", "request_too_large")

        request_type = value.get("type")
        if request_type not in REQUEST_TYPES:
            raise ProtocolError("unsupported request type")
        try:
            request_id = require_identifier("requestId", value.get("requestId"))
            conversation_id = require_optional_string(
                "conversationId", value.get("conversationId")
            )
            profile_id = require_optional_string("profileId", value.get("profileId"))
            prompt = require_optional_string("prompt", value.get("prompt"))
            mode = require_optional_string("mode", value.get("mode"))
            attachment_id = require_optional_string(
                "attachmentId", value.get("attachmentId")
            )
            query = require_optional_string("query", value.get("query"))
        except ValueError as error:
            raise ProtocolError(str(error)) from error

        private = value.get("private", False)
        if not isinstance(private, bool):
            raise ProtocolError("private must be a boolean")
        confirm = value.get("confirm", False)
        if not isinstance(confirm, bool):
            raise ProtocolError("confirm must be a boolean")
        raw_attachments = value.get("attachments", [])
        if not isinstance(raw_attachments, list):
            raise ProtocolError("attachments must be an array")

        runtime_root = PathSet.from_env(os.environ).capture_dir
        attachments = tuple(
            Attachment.from_dict(attachment, runtime_root)
            for attachment in raw_attachments
        )

        if request_type == "run":
            for name, field in (
                ("conversationId", conversation_id),
                ("profileId", profile_id),
            ):
                try:
                    require_identifier(name, field)
                except ValueError as error:
                    raise ProtocolError(str(error)) from error
            if not isinstance(prompt, str):
                raise ProtocolError("prompt must be a string")

        return cls(
            type=request_type,
            request_id=request_id,
            conversation_id=conversation_id,
            profile_id=profile_id,
            prompt=prompt,
            attachments=attachments,
            private=private,
            confirm=confirm,
            mode=mode,
            attachment_id=attachment_id,
            query=query,
        )


@dataclass(frozen=True)
class Event:
    type: str
    request_id: str
    data: dict[str, object]

    def to_json(self) -> str:
        if self.type not in EVENT_TYPES:
            raise ProtocolError("unsupported event type", "invalid_event")
        try:
            request_id = require_identifier("requestId", self.request_id)
        except ValueError as error:
            raise ProtocolError(str(error), "invalid_event") from error
        if not isinstance(self.data, dict):
            raise ProtocolError("event data must be an object", "invalid_event")
        try:
            return json.dumps(
                {"type": self.type, "requestId": request_id, "data": self.data},
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise ProtocolError("event data is not JSON serializable", "invalid_event") from error
