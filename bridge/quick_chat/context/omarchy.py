"""Read-only allowlisted Omarchy CLI context queries."""

from __future__ import annotations

import uuid
from typing import Callable

from ..process_capture import run_bounded_checked
from .base import AttachmentRecord


QUERY_COMMANDS = {
    "commands": ("omarchy", "commands", "--json"),
    "debug": ("omarchy", "debug", "--no-sudo", "--print"),
}


def _default_runner(argv, **kwargs):
    return run_bounded_checked(
        tuple(argv),
        timeout=kwargs.get("timeout", 15),
        stdout_limit=1024 * 1024,
        stderr_limit=64 * 1024,
    )


class OmarchyQueryProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def query(self, name: str) -> AttachmentRecord:
        if name not in QUERY_COMMANDS:
            raise ValueError("unsupported Omarchy context query")
        command = QUERY_COMMANDS[name]
        result = self.runner(
            command,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Omarchy query failed")
        return AttachmentRecord(
            id=str(uuid.uuid4()),
            kind="text",
            mime_type="application/json" if name == "commands" else "text/plain",
            text=result.stdout,
            size=len(result.stdout.encode("utf-8")),
        )
