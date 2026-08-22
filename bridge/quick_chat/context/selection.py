"""Explicit primary-selection text capture."""

from __future__ import annotations

import uuid
from typing import Callable

from ..process_capture import run_bounded_checked
from .base import AttachmentRecord


SELECTION_LIMIT = 256 * 1024


def _default_runner(argv, **kwargs):
    return run_bounded_checked(
        tuple(argv),
        timeout=kwargs.get("timeout", 2),
        stdout_limit=SELECTION_LIMIT,
        stderr_limit=64 * 1024,
    )


class SelectionProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def capture(self) -> AttachmentRecord:
        result = self.runner(
            ["wl-paste", "--primary", "--no-newline"],
            timeout=2,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "selected text is unavailable")
        encoded = result.stdout.encode("utf-8", errors="replace")[:SELECTION_LIMIT]
        text = encoded.decode("utf-8", errors="replace")
        return AttachmentRecord(
            id=str(uuid.uuid4()),
            kind="text",
            mime_type="text/plain",
            text=text,
            size=len(encoded),
        )
