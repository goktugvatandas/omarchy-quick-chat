"""Atomic, schema-validated configuration persistence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Config
from .paths import PathSet


def _secure_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def atomic_write_json(path: Path, value: object) -> None:
    """Atomically replace a private JSON file and sync file and directory."""
    _secure_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def quarantine(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = path.with_name(f"{path.name}.corrupt-{stamp}")
    suffix = 1
    while destination.exists():
        destination = path.with_name(f"{path.name}.corrupt-{stamp}.{suffix}")
        suffix += 1
    path.replace(destination)
    return destination


def recovery_diagnostic(path: Path, error: Exception) -> dict[str, str]:
    return {
        "code": "history_recovered",
        "message": f"Invalid local data was quarantined: {error}",
        "path": str(path),
    }


class ConfigStore:
    def __init__(self, paths: PathSet) -> None:
        self.paths = paths
        self.last_diagnostic: dict[str, str] | None = None

    def load(self) -> Config:
        self.last_diagnostic = None
        if not self.paths.config_file.exists():
            return Config.default()
        try:
            with self.paths.config_file.open(encoding="utf-8") as stream:
                value: Any = json.load(stream)
            schema_version = value.get("schemaVersion", 1) if isinstance(value, dict) else None
            config = Config.from_dict(value)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            quarantined = quarantine(self.paths.config_file)
            self.last_diagnostic = recovery_diagnostic(quarantined, error)
            return Config.default()
        if schema_version == 1:
            try:
                self.save(config)
            except OSError:
                # A valid legacy config remains usable when the config mount is
                # temporarily read-only. The next load retries the atomic upgrade.
                pass
        return config

    def save(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise ValueError("config must be a Config record")
        atomic_write_json(self.paths.config_file, config.to_dict())
