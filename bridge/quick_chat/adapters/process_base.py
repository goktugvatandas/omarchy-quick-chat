"""Shared safe version probing and degraded-mode behavior."""

from __future__ import annotations

import re
import subprocess
from dataclasses import replace
from pathlib import Path

from ..process_capture import CaptureLimitExceeded, run_bounded
from .base import Capabilities, EffortOption, ModelOption


VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+")


class ProcessAdapterBase:
    executable: str
    _capabilities: Capabilities
    _effort_options: tuple[EffortOption, ...] = ()

    def __init__(self) -> None:
        self._degraded = False

    @property
    def capabilities(self) -> Capabilities:
        if not self._degraded:
            return self._capabilities
        return replace(
            self._capabilities,
            streaming=False,
            resume=False,
            native_images=False,
            relayable_approvals=False,
        )

    def degrade(self) -> None:
        self._degraded = True

    @staticmethod
    def is_launcher_preamble(text: str) -> bool:
        return text.startswith("mise ") and " tools: " in text

    def discover_models(self, cwd: Path | None = None) -> tuple[ModelOption, ...]:
        return ()

    def effort_options(self, cwd: Path | None = None) -> tuple[EffortOption, ...]:
        return tuple(self._effort_options)

    def detect(self) -> dict[str, object]:
        try:
            result = run_bounded(
                (self.executable, "--version"),
                timeout=2,
                stdout_limit=64 * 1024,
                stderr_limit=64 * 1024,
            )
        except FileNotFoundError:
            return {
                "available": False,
                "code": "not_installed",
                "executable": self.executable,
            }
        except subprocess.TimeoutExpired:
            return {
                "available": False,
                "code": "probe_timeout",
                "executable": self.executable,
            }
        except CaptureLimitExceeded:
            return {
                "available": False,
                "code": "probe_output_too_large",
                "executable": self.executable,
            }

        version = (result.stdout or result.stderr).strip().splitlines()
        version_text = next(
            (line for line in version if not self.is_launcher_preamble(line)),
            version[0] if version else "",
        )
        supported = result.returncode == 0 and bool(VERSION_PATTERN.search(version_text))
        if not supported:
            self.degrade()
        return {
            "available": result.returncode == 0,
            "version": version_text,
            "structured": supported,
            "degraded": not supported,
        }
