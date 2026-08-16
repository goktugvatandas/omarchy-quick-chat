import json
import subprocess
import unittest

from bridge.quick_chat.models import Config, Profile
from bridge.quick_chat.shortcuts import normalize_shortcut, sync_shortcuts


class FakeHyprctl:
    def __init__(self, binds=(), *, lua=False):
        self.binds = list(binds)
        self.lua = lua
        self.calls = []

    def __call__(self, argv, **kwargs):
        command = list(argv)
        self.calls.append(command)
        if command == ["hyprctl", "-j", "binds"]:
            return subprocess.CompletedProcess(command, 0, json.dumps(self.binds), "")
        if command == ["hyprctl", "eval", "return true"]:
            output = "ok" if self.lua else "eval can't work with legacy parsers"
            return subprocess.CompletedProcess(command, 0, output, "")
        return subprocess.CompletedProcess(command, 0, "ok", "")


class ShortcutTests(unittest.TestCase):
    def test_fresh_default_shortcut_is_super_alt_c(self):
        self.assertEqual(Config.default().default_shortcut, "SUPER ALT, C")
        self.assertEqual(normalize_shortcut("alt super, space"), "SUPER ALT, SPACE")

    def test_invalid_modifiers_and_keys_are_rejected(self):
        for shortcut in ("SUPER META, SPACE", "SUPER, F-1", "SUPER SPACE"):
            with self.subTest(shortcut=shortcut):
                with self.assertRaises(ValueError):
                    normalize_shortcut(shortcut)

    def test_existing_foreign_binding_is_not_overwritten(self):
        runner = FakeHyprctl([{
            "mods": "SUPER ALT",
            "key": "C",
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
        self.assertIn("goktugvatandas.quick-chat:profile-work", bind_call[3])

    def test_lua_config_adds_exact_global_target_through_eval(self):
        work = Profile(
            id="work",
            name="Work",
            adapter_id="codex",
            shortcut="SUPER CTRL, K",
        )
        config = Config(profiles=(work,), selected_profile_id="work")
        runner = FakeHyprctl(lua=True)

        result = sync_shortcuts(config, runner)

        self.assertEqual(result.conflicts, ())
        self.assertEqual(runner.calls[-1], [
            "hyprctl",
            "eval",
            'hl.bind("SUPER + CTRL + K", '
            'hl.dsp.global("goktugvatandas.quick-chat:profile-work"), '
            '{ description = "Quick Chat: Work" })',
        ])

    def test_existing_lua_binding_is_owned_by_description(self):
        work = Profile(
            id="work",
            name="Work",
            adapter_id="codex",
            shortcut="SUPER CTRL, K",
        )
        config = Config(profiles=(work,), selected_profile_id="work")
        runner = FakeHyprctl([{
            "modmask": 68,
            "key": "K",
            "dispatcher": "__lua",
            "arg": "238",
            "description": "Quick Chat: Work",
        }], lua=True)

        result = sync_shortcuts(config, runner)

        self.assertEqual(result.conflicts, ())
        self.assertEqual(result.applied, ())
        self.assertFalse(any(
            command[:2] == ["hyprctl", "eval"] and "hl.bind" in command[-1]
            for command in runner.calls
        ))

    def test_stale_lua_binding_is_removed_before_rebinding(self):
        work = Profile(
            id="work",
            name="Work",
            adapter_id="codex",
            shortcut="SUPER CTRL, K",
        )
        config = Config(profiles=(work,), selected_profile_id="work")
        runner = FakeHyprctl([{
            "modmask": 72,
            "key": "C",
            "dispatcher": "__lua",
            "arg": "237",
            "description": "Quick Chat: Work",
        }], lua=True)

        result = sync_shortcuts(config, runner)

        self.assertEqual(result.removed, ("work",))
        self.assertIn(
            ["hyprctl", "eval", 'hl.unbind("SUPER + ALT + C")'],
            runner.calls,
        )
        self.assertIn("work", result.applied)

    def test_modmask_is_understood_for_conflict_detection(self):
        runner = FakeHyprctl([{
            "modmask": 72,
            "key": "C",
            "dispatcher": "global",
            "arg": "another.plugin:open",
        }])
        result = sync_shortcuts(Config.default(), runner)
        self.assertEqual(len(result.conflicts), 1)


if __name__ == "__main__":
    unittest.main()
