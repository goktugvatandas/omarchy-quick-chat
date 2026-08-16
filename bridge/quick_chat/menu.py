"""Idempotent Omarchy root-menu integration."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path


MENU_ENTRY_ID = "quick-chat"
LEGACY_MENU_ENTRY = {
    "icon": "󰚩",
    "label": "Quick Chat",
    "description": "Ask Codex, Claude Code, OpenCode, Grok, Cursor, or Pi",
    "aliases": ["quick-chat", "chat", "ask"],
    "when": (
        "jq -e 'any(.plugins[]?; .id == \"goktugvatandas.quick-chat\")' "
        '"$HOME/.config/omarchy/shell.json" >/dev/null'
    ),
    "action": "omarchy-shell shell summon goktugvatandas.quick-chat '{}'",
}
MENU_ENTRY = {
    "icon": "󰚩",
    "label": "Quick Chat",
    # Current Omarchy releases ignore relative-order metadata and append all
    # extension rows after stock rows. Keeping the requested anchor on our
    # namespaced entry makes the intent forward-compatible with the planned
    # core ordering hook while remaining harmless today.
    "after": "apps",
    "description": "Ask Codex, Claude Code, OpenCode, Grok, Cursor, or Pi",
    "aliases": ["quick-chat", "chat", "ask"],
    "when": (
        "jq -e 'any(.plugins[]?; .id == \"goktugvatandas.quick-chat\")' "
        '"$HOME/.config/omarchy/shell.json" >/dev/null'
    ),
    "action": "omarchy-shell shell summon goktugvatandas.quick-chat '{}'",
}


@dataclass(frozen=True)
class MenuInstallResult:
    path: Path
    changed: bool
    entry_id: str = MENU_ENTRY_ID

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "path": str(self.path),
            "changed": self.changed,
            "entryId": self.entry_id,
        }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _entry_exists(content: str) -> bool:
    without_comments = re.sub(
        r"^\s*//[^\n]*(\n|$)",
        "",
        content,
        flags=re.MULTILINE,
    )
    normalized = re.sub(r",(\s*[}\]])", r"\1", without_comments)
    try:
        parsed = json.loads(normalized)
        source = parsed.get("items", parsed) if isinstance(parsed, dict) else {}
        return isinstance(source, dict) and MENU_ENTRY_ID in source
    except json.JSONDecodeError:
        pattern = rf'{re.escape(json.dumps(MENU_ENTRY_ID))}\s*:'
        return re.search(pattern, without_comments) is not None


def _serialized_entry(entry: dict[str, object]) -> str:
    key = json.dumps(MENU_ENTRY_ID, ensure_ascii=False)
    value = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
    return f"{key}: {value},"


def _upgrade_generated_entry(content: str) -> str | None:
    legacy = _serialized_entry(LEGACY_MENU_ENTRY)
    current = _serialized_entry(MENU_ENTRY)
    pattern = re.compile(
        rf"(?m)^([ \t]*){re.escape(legacy)}([ \t]*)$"
    )
    match = pattern.search(content)
    if match is None:
        return None
    replacement = f"{match.group(1)}{current}{match.group(2)}"
    return content[: match.start()] + replacement + content[match.end() :]


def _insertion_point(content: str) -> tuple[int, str]:
    items = re.search(r'(?m)^([ \t]*)"items"\s*:\s*\{', content)
    if items is not None:
        brace = content.find("{", items.start(), items.end())
        return brace + 1, items.group(1) + "  "

    brace = content.find("{")
    if brace < 0:
        raise ValueError("Omarchy menu extension is not a JSONC object")
    return brace + 1, "  "


def install_menu_entry(path: Path) -> MenuInstallResult:
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = "{}\n"

    upgraded = _upgrade_generated_entry(content)
    if upgraded is not None:
        _atomic_write(path, upgraded)
        return MenuInstallResult(path=path, changed=True)

    if _entry_exists(content):
        return MenuInstallResult(path=path, changed=False)

    position, indentation = _insertion_point(content)
    insertion = f"\n{indentation}{_serialized_entry(MENU_ENTRY)}"
    updated = content[:position] + insertion + content[position:]
    _atomic_write(path, updated)
    return MenuInstallResult(path=path, changed=True)
