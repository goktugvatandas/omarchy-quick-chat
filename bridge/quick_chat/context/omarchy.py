"""Read-only allowlisted Omarchy CLI context queries."""

from __future__ import annotations

import subprocess
import uuid
from typing import Callable

from .base import AttachmentRecord


QUERY_COMMANDS = {
    "commands": ("omarchy", "commands", "--json"),
    "debug": ("omarchy", "debug", "--no-sudo", "--print"),
}


def _default_runner(argv, **kwargs):
    return subprocess.run(argv, **kwargs)


class OmarchyQueryProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def query(self, name: str) -> AttachmentRecord:
        if name not in QUERY_COMMANDS:
            raise ValueError("unsupported Omarchy context query")
        command = QUERY_COMMANDS[name]
        result = self.runner(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            shell=False,
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
