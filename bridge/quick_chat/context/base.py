"""Context records, ownership, cleanup, and provider contracts."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..paths import PathSet


@dataclass(frozen=True)
class AttachmentRecord:
    id: str
    kind: str
    mime_type: str
    path: Path | None = None
    text: str | None = None
    app_name: str = ""
    window_title: str = ""
    size: int = 0

    def to_wire(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": str(self.path) if self.path is not None else None,
            "text": self.text,
            "mimeType": self.mime_type,
            "appName": self.app_name,
            "windowTitle": self.window_title,
            "size": self.size,
        }


class ContextProvider(Protocol):
    def capture(self) -> AttachmentRecord: ...


class ContextManager:
    def __init__(self, paths: PathSet) -> None:
        self.paths = paths
        self._records: dict[str, AttachmentRecord] = {}

    def add(self, attachment: AttachmentRecord) -> AttachmentRecord:
        if attachment.id in self._records:
            raise ValueError("attachment id is already registered")
        self._records[attachment.id] = attachment
        return attachment

    def get(self, attachment_id: str) -> AttachmentRecord:
        try:
            return self._records[attachment_id]
        except KeyError as error:
            raise ValueError("attachment was not found") from error

    def remove(self, attachment_id: str) -> bool:
        attachment = self._records.pop(attachment_id, None)
        if attachment is None:
            return False
        self._delete_owned_path(attachment.path)
        return True

    def remove_many(self, attachment_ids: tuple[str, ...] | list[str]) -> None:
        for attachment_id in attachment_ids:
            self.remove(attachment_id)

    def cleanup_all(self) -> None:
        self.remove_many(list(self._records))

    def _delete_owned_path(self, path: Path | None) -> None:
        if path is None or path.is_symlink():
            return
        root = self.paths.capture_dir.resolve()
        candidate = path.resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            candidate.unlink(missing_ok=True)

    def sweep(self, maximum_age_seconds: float = 24 * 60 * 60) -> None:
        if not self.paths.capture_dir.exists():
            return
        cutoff = time.time() - maximum_age_seconds
        with os.scandir(self.paths.capture_dir) as entries:
            for entry in entries:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    continue
                if entry.stat(follow_symlinks=False).st_mtime < cutoff:
                    Path(entry.path).unlink(missing_ok=True)
