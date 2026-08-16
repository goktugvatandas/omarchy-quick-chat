"""Adapter contracts shared by every CLI integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from ..protocol import Attachment


@dataclass(frozen=True)
class Capabilities:
    streaming: bool
    resume: bool
    model: bool
    native_images: bool
    read_only_enforced: bool
    relayable_approvals: bool


@dataclass(frozen=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    stdin_text: str | None

    def __post_init__(self) -> None:
        if not self.argv or not all(isinstance(value, str) and value for value in self.argv):
            raise ValueError("invocation argv must contain non-empty strings")
        if not isinstance(self.cwd, Path) or not self.cwd.is_dir():
            raise ValueError("invocation cwd must be an existing directory")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in self.env.items()):
            raise ValueError("invocation environment must map strings to strings")
        if self.stdin_text is not None and not isinstance(self.stdin_text, str):
            raise ValueError("invocation stdin must be a string or null")


@dataclass(frozen=True)
class AdapterEvent:
    type: str
    data: dict[str, object]


@dataclass(frozen=True)
class AdapterContext:
    prompt: str
    model: str | None
    cwd: Path
    attachments: tuple[Attachment, ...] = ()
    session_id: str | None = None
    system_instructions: str = ""


class Adapter(Protocol):
    id: str
    capabilities: Capabilities

    def detect(self) -> dict[str, object]: ...

    def start(self, context: AdapterContext) -> Invocation: ...

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]: ...
