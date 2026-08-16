"""User-triggered image-to-text conversion."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Callable

from .base import AttachmentRecord


def _default_runner(argv, **kwargs):
    return subprocess.run(argv, **kwargs)


class OcrProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def convert(self, path: Path) -> AttachmentRecord:
        if path.is_symlink() or not path.is_file():
            raise ValueError("OCR source must be a regular image file")
        result = self.runner(
            ["tesseract", str(path), "stdout"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            shell=False,
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
