"""Omarchy screenshot capture with private runtime copies."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Callable

from ..paths import PathSet
from ..process_capture import CapturedProcess, run_bounded_checked
from .base import AttachmentRecord


Runner = Callable[..., CapturedProcess]


def _default_runner(argv, **kwargs):
    return run_bounded_checked(
        tuple(argv),
        timeout=kwargs.get("timeout", 15),
        stdout_limit=4 * 1024,
        stderr_limit=64 * 1024,
    )


class CaptureProvider:
    def __init__(self, paths: PathSet, runner: Runner = _default_runner) -> None:
        self.paths = paths
        self.runner = runner

    def active_window(self) -> AttachmentRecord:
        return self._capture("windows")

    def fullscreen(self) -> AttachmentRecord:
        return self._capture("fullscreen")

    def _capture(self, mode: str) -> AttachmentRecord:
        command = ["omarchy", "capture", "screenshot", mode, "save"]
        result = self.runner(
            command,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "screen capture failed")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("screen capture returned no file")
        source = Path(lines[-1]).expanduser()
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("screen capture returned an invalid file")

        self.paths.capture_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.paths.capture_dir.chmod(0o700)
        identifier = str(uuid.uuid4())
        suffix = source.suffix.lower() if source.suffix else ".png"
        destination = self.paths.capture_dir / f"{identifier}{suffix}"
        shutil.copyfile(source, destination, follow_symlinks=False)
        destination.chmod(0o600)
        return AttachmentRecord(
            id=identifier,
            kind="image",
            path=destination,
            mime_type="image/png",
            size=destination.stat().st_size,
        )
