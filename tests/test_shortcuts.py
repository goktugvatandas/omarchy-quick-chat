import json
import subprocess
import unittest

from bridge.quick_chat.models import Config, Profile
from bridge.quick_chat.shortcuts import normalize_shortcut, sync_shortcuts


class FakeHyprctl:
    def __init__(self, binds=()):
        self.binds = list(binds)
        self.calls = []

    def __call__(self, argv, **kwargs):
        command = list(argv)
        self.calls.append(command)
        if command == ["hyprctl", "-j", "binds"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.binds), "")
        return subprocess.CompletedProcess(command, 0, "ok", "")


class ShortcutTests(unittest.TestCase):
    def test_default_shortcut_is_super_alt_space(self):
        self.assertEqual(Config.default().default_shortcut, "SUPER ALT, SPACE")
        self.assertEqual(normalize_shortcut("alt super, space"), "SUPER ALT, SPACE")

    def test_invalid_modifiers_and_keys_are_rejected(self):
        for shortcut in ("SUPER META, SPACE", "SUPER, F-1", "SUPER SPACE"):
            with self.subTest(shortcut=shortcut):
                with self.assertRaises(ValueError):
                    normalize_shortcut(shortcut)

    def test_existing_foreign_binding_is_not_overwritten(self):
        runner = FakeHyprctl([{
            "mods": "SUPER ALT",
            "key": "SPACE",
            "dispatcher": "exec",
            "arg": "something-else",
            "description": "Apps menu",
        }])
        result = sync_shortcuts(Config.default(), runner)
        self.assertEqual(result.conflicts[0].profile_id, "codex")
        self.assertEqual(result.conflicts[0].owner, "Apps menu")
        self.assertFalse(any("bindd" in call for command in runner.calls for call in command))

    def test_profile_shortcut_adds_exact_global_target(self):
        work = Profile(
            id="work",
            name="Work",
            adapter_id="codex",
            shortcut="SUPER CTRL, K",
        )
        config = Config(profiles=(work,), selected_profile_id="work")
        runner = FakeHyprctl()
        result = sync_shortcuts(config, runner)
        self.assertEqual(result.conflicts, ())
        bind_call = runner.calls[-1]
        self.assertEqual(bind_call[:3], ["hyprctl", "keyword", "bindd"])
        self.assertIn("community.quick-chat:profile-work", bind_call[3])

    def test_modmask_is_understood_for_conflict_detection(self):
        runner = FakeHyprctl([{
            "modmask": 72,
            "key": "SPACE",
            "dispatcher": "global",
            "arg": "another.plugin:open",
        }])
        result = sync_shortcuts(Config.default(), runner)
        self.assertEqual(len(result.conflicts), 1)


if __name__ == "__main__":
    unittest.main()
