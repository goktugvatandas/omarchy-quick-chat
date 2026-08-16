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
LUA_DESCRIPTION_PREFIX = "Quick Chat: "


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


def _description(profile_name: str) -> str:
    return f"{LUA_DESCRIPTION_PREFIX}{profile_name}"


def _owned(
    binding: dict[str, object],
    profile_id: str | None = None,
    profile_name: str | None = None,
) -> bool:
    argument = binding.get("arg")
    expected = _target(profile_id) if profile_id is not None else "community.quick-chat:profile-"
    if binding.get("dispatcher") == "global" and isinstance(argument, str) and (
        argument == expected if profile_id is not None else argument.startswith(expected)
    ):
        return True
    description = binding.get("description")
    if binding.get("dispatcher") != "__lua" or not isinstance(description, str):
        return False
    if profile_name is not None:
        return description == _description(profile_name)
    return description.startswith(LUA_DESCRIPTION_PREFIX)


def _run(runner: Callable, argv: list[str]):
    return runner(
        argv,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
        shell=False,
    )


def _using_lua(runner: Callable) -> bool:
    result = _run(runner, ["hyprctl", "eval", "return true"])
    return result.returncode == 0 and (result.stdout or "").strip() == "ok"


def _lua_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _lua_keys(shortcut: str) -> str:
    modifiers, key = shortcut.split(", ", 1)
    return " + ".join([*modifiers.split(), key])


def _require_ok(result, fallback: str) -> None:
    output = (result.stdout or "").strip()
    if result.returncode == 0 and output == "ok":
        return
    raise RuntimeError((result.stderr or "").strip() or output or fallback)


def _unbind(runner: Callable, shortcut: str, *, using_lua: bool) -> None:
    if using_lua:
        code = f"hl.unbind({_lua_literal(_lua_keys(shortcut))})"
        result = _run(runner, ["hyprctl", "eval", code])
    else:
        result = _run(
            runner,
            ["hyprctl", "keyword", "unbind", shortcut.replace(", ", ",")],
        )
    _require_ok(result, "unable to remove shortcut")


def _bind(
    runner: Callable,
    shortcut: str,
    profile_id: str,
    profile_name: str,
    *,
    using_lua: bool,
) -> None:
    if using_lua:
        code = (
            f"hl.bind({_lua_literal(_lua_keys(shortcut))}, "
            f"hl.dsp.global({_lua_literal(_target(profile_id))}), "
            f"{{ description = {_lua_literal(_description(profile_name))} }})"
        )
        result = _run(runner, ["hyprctl", "eval", code])
    else:
        modifiers, key = shortcut.split(", ", 1)
        description = (
            f"{modifiers},{key},Quick Chat: {profile_name},"
            f"global,{_target(profile_id)}"
        )
        result = _run(runner, ["hyprctl", "keyword", "bindd", description])
    _require_ok(result, "unable to add shortcut")


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
    result = _run(runner, ["hyprctl", "-j", "binds"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "unable to read Hyprland bindings")
    bindings = json.loads(result.stdout or "[]")
    if not isinstance(bindings, list):
        raise RuntimeError("Hyprland bindings response is invalid")
    using_lua = _using_lua(runner)

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
    profile_by_description = {
        _description(profile.name): profile.id for profile in config.profiles
    }

    for binding in bindings:
        if not isinstance(binding, dict) or not _owned(binding):
            continue
        shortcut = _binding_shortcut(binding)
        if binding.get("dispatcher") == "global":
            argument = str(binding.get("arg"))
            profile_id = argument.removeprefix("community.quick-chat:profile-")
        else:
            profile_id = profile_by_description.get(
                str(binding.get("description")),
                str(binding.get("description") or "unknown"),
            )
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
                _unbind(runner, shortcut, using_lua=using_lua)
                removed.append(profile_id)

    for profile_id, (shortcut, profile_name) in desired.items():
        existing = [
            binding
            for binding in bindings
            if isinstance(binding, dict) and _binding_shortcut(binding) == shortcut
        ]
        if any(_owned(binding, profile_id, profile_name) for binding in existing):
            continue
        foreign = next(
            (
                binding
                for binding in existing
                if not _owned(binding, profile_id, profile_name)
            ),
            None,
        )
        if foreign is not None:
            owner = str(
                foreign.get("description")
                or foreign.get("arg")
                or foreign.get("dispatcher")
                or "unknown"
            )
            conflicts.append(ShortcutConflict(profile_id, shortcut, owner))
            continue
        _bind(
            runner,
            shortcut,
            profile_id,
            profile_name,
            using_lua=using_lua,
        )
        applied.append(profile_id)

    return SyncResult(tuple(conflicts), tuple(applied), tuple(removed))
