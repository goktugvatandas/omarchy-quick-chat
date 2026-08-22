"""User-triggered image-to-text conversion."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from ..process_capture import run_bounded_checked
from .base import AttachmentRecord


OCR_LIMIT = 256 * 1024


def _default_runner(argv, **kwargs):
    return run_bounded_checked(
        tuple(argv),
        timeout=kwargs.get("timeout", 30),
        stdout_limit=OCR_LIMIT,
        stderr_limit=64 * 1024,
    )


class OcrProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def convert(self, path: Path) -> AttachmentRecord:
        if path.is_symlink() or not path.is_file():
            raise ValueError("OCR source must be a regular image file")
        result = self.runner(
            ["tesseract", str(path), "stdout"],
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "OCR failed")
        return AttachmentRecord(
            id=str(uuid.uuid4()),
            kind="text",
            mime_type="text/plain",
            text=result.stdout,
            size=len(result.stdout.encode("utf-8")),
        )
