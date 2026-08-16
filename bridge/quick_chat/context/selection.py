"""Explicit primary-selection text capture."""

from __future__ import annotations

import subprocess
import uuid
from typing import Callable

from .base import AttachmentRecord


SELECTION_LIMIT = 256 * 1024


def _default_runner(argv, **kwargs):
    return subprocess.run(argv, **kwargs)


class SelectionProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def capture(self) -> AttachmentRecord:
        result = self.runner(
            ["wl-paste", "--primary", "--no-newline"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            shell=False,
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
