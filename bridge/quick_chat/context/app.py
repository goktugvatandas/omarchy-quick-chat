"""Active-window metadata and active-project working-directory resolution."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..process_capture import run_bounded_checked
from .base import AttachmentRecord


def _default_runner(argv, **kwargs):
    return run_bounded_checked(
        tuple(argv),
        timeout=kwargs.get("timeout", 2),
        stdout_limit=64 * 1024,
        stderr_limit=64 * 1024,
    )


@dataclass(frozen=True)
class AppMetadata:
    app_name: str
    window_title: str
    pid: int | None

    def to_attachment(self) -> AttachmentRecord:
        text = json.dumps({
            "appName": self.app_name,
            "windowTitle": self.window_title,
        })
        return AttachmentRecord(
            id=str(uuid.uuid4()),
            kind="metadata",
            mime_type="application/json",
            text=text,
            app_name=self.app_name,
            window_title=self.window_title,
            size=len(text.encode("utf-8")),
        )


class ActiveAppProvider:
    def __init__(self, runner: Callable = _default_runner) -> None:
        self.runner = runner

    def get(self) -> AppMetadata:
        result = self.runner(
            ["hyprctl", "-j", "activewindow"],
            timeout=2,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "active window lookup failed")
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise RuntimeError("active window response is invalid")
        pid = value.get("pid")
        return AppMetadata(
            app_name=str(value.get("class") or "Unknown app"),
            window_title=str(value.get("title") or "Untitled window"),
            pid=pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
        )


@dataclass(frozen=True)
class ProjectResolution:
    path: Path
    diagnostic: str | None = None


class ActiveProjectResolver:
    def __init__(self, proc_root: Path = Path("/proc"), home: Path | None = None) -> None:
        self.proc_root = proc_root
        self.home = Path.home() if home is None else home

    def resolve(self, pid: int | None) -> ProjectResolution:
        if pid is None or pid <= 0:
            return ProjectResolution(self.home, "Active app PID is unavailable; using home.")
        cwd = self.proc_root / str(pid) / "cwd"
        try:
            resolved = cwd.resolve(strict=True)
            if not resolved.is_dir():
                raise OSError("cwd is not a directory")
            return ProjectResolution(resolved)
        except OSError:
            return ProjectResolution(self.home, "Active project is unavailable; using home.")
