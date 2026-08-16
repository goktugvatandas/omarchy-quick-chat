"""Validated Quick Chat shortcut synchronization for Hyprland."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from .models import Config


MODIFIER_ORDER = ("SUPER", "ALT", "CTRL", "SHIFT")
MODIFIER_BITS = {"SHIFT": 1, "CTRL": 4, "ALT": 8, "SUPER": 64}
KEY_PATTERN = re.compile(r"[A-Z0-9_]+\Z")


def _default_runner(argv, **kwargs):
    return subprocess.run(argv, **kwargs)


def normalize_shortcut(value: str) -> str:
    if not isinstance(value, str) or value.count(",") != 1:
        raise ValueError("shortcut must use MODIFIERS, KEY format")
    modifiers_text, key_text = value.upper().split(",", 1)
    modifiers = modifiers_text.split()
    if not modifiers or len(modifiers) != len(set(modifiers)):
        raise ValueError("shortcut modifiers are invalid")
    if any(modifier not in MODIFIER_ORDER for modifier in modifiers):
        raise ValueError("shortcut contains an unsupported modifier")
    key = key_text.strip()
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("shortcut key is invalid")
    canonical_modifiers = [
        modifier for modifier in MODIFIER_ORDER if modifier in modifiers
    ]
    return f"{' '.join(canonical_modifiers)}, {key}"


def _binding_shortcut(binding: dict[str, object]) -> str | None:
    key = binding.get("key")
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key.upper()):
        return None
    mods = binding.get("mods")
    if isinstance(mods, str) and mods.strip():
        modifier_text = mods
    else:
        modmask = binding.get("modmask")
        if isinstance(modmask, bool) or not isinstance(modmask, int):
            return None
        modifier_text = " ".join(
            modifier
            for modifier in MODIFIER_ORDER
            if modmask & MODIFIER_BITS[modifier]
        )
    try:
        return normalize_shortcut(f"{modifier_text}, {key}")
    except ValueError:
        return None


def _target(profile_id: str) -> str:
    return f"community.quick-chat:profile-{profile_id}"


def _owned(binding: dict[str, object], profile_id: str | None = None) -> bool:
    argument = binding.get("arg")
    expected = _target(profile_id) if profile_id is not None else "community.quick-chat:profile-"
    return binding.get("dispatcher") == "global" and isinstance(argument, str) and (
        argument == expected if profile_id is not None else argument.startswith(expected)
    )


@dataclass(frozen=True)
class ShortcutConflict:
    profile_id: str
    shortcut: str
    owner: str


@dataclass(frozen=True)
class SyncResult:
    conflicts: tuple[ShortcutConflict, ...]
    applied: tuple[str, ...]
    removed: tuple[str, ...]


def sync_shortcuts(
    config: Config,
    runner: Callable = _default_runner,
) -> SyncResult:
    result = runner(
        ["hyprctl", "-j", "binds"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "unable to read Hyprland bindings")
    bindings = json.loads(result.stdout or "[]")
    if not isinstance(bindings, list):
        raise RuntimeError("Hyprland bindings response is invalid")

    desired: dict[str, tuple[str, str]] = {}
    for profile in config.profiles:
        shortcut_value = profile.shortcut
        if shortcut_value is None and profile.id == config.selected_profile_id:
            shortcut_value = config.default_shortcut
        if shortcut_value:
            desired[profile.id] = (normalize_shortcut(shortcut_value), profile.name)

    conflicts: list[ShortcutConflict] = []
    applied: list[str] = []
    removed: list[str] = []

    for binding in bindings:
        if not isinstance(binding, dict) or not _owned(binding):
            continue
        shortcut = _binding_shortcut(binding)
        argument = str(binding.get("arg"))
        profile_id = argument.removeprefix("community.quick-chat:profile-")
        expected = desired.get(profile_id)
        if shortcut and (expected is None or expected[0] != shortcut):
            same_chord = [
                other
                for other in bindings
                if isinstance(other, dict)
                and other is not binding
                and _binding_shortcut(other) == shortcut
            ]
            if not same_chord:
                runner(
                    ["hyprctl", "keyword", "unbind", shortcut.replace(", ", ",")],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                    shell=False,
                )
                removed.append(profile_id)

    for profile_id, (shortcut, profile_name) in desired.items():
        existing = [
            binding
            for binding in bindings
            if isinstance(binding, dict) and _binding_shortcut(binding) == shortcut
        ]
        if any(_owned(binding, profile_id) for binding in existing):
            continue
        foreign = next((binding for binding in existing if not _owned(binding, profile_id)), None)
        if foreign is not None:
            owner = str(foreign.get("arg") or foreign.get("dispatcher") or "unknown")
            conflicts.append(ShortcutConflict(profile_id, shortcut, owner))
            continue
        modifiers, key = shortcut.split(", ", 1)
        description = f"{modifiers},{key},Quick Chat: {profile_name},global,{_target(profile_id)}"
        bind_result = runner(
            ["hyprctl", "keyword", "bindd", description],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            shell=False,
        )
        if bind_result.returncode != 0:
            raise RuntimeError(bind_result.stderr.strip() or "unable to add shortcut")
        applied.append(profile_id)

    return SyncResult(tuple(conflicts), tuple(applied), tuple(removed))
