import tempfile
import unittest
from pathlib import Path

from bridge.quick_chat.models import (
    Config,
    Profile,
    require_identifier,
    require_optional_string,
)


class ModelValidationTests(unittest.TestCase):
    def test_identifier_must_be_non_empty_string(self):
        self.assertEqual(require_identifier("requestId", "req-1"), "req-1")
        for invalid in (None, "", "   ", 1):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_identifier("requestId", invalid)

    def test_optional_string_preserves_none_and_rejects_other_types(self):
        self.assertIsNone(require_optional_string("model", None))
        self.assertEqual(require_optional_string("model", "fast"), "fast")
        with self.assertRaises(ValueError):
            require_optional_string("model", False)

    def test_default_config_selects_codex_and_twenty_item_history(self):
        config = Config.default()
        self.assertEqual(config.schema_version, 2)
        self.assertEqual(config.selected_profile_id, "codex")
        self.assertEqual(config.history_limit, 20)
        self.assertEqual(config.default_shortcut, "SUPER ALT, C")
        self.assertEqual(config.ui_shortcuts["model"], "Ctrl+K")

    def test_v1_config_migrates_without_losing_user_values(self):
        legacy = Config.default().to_dict()
        legacy["schemaVersion"] = 1
        legacy.pop("uiShortcuts", None)
        legacy["defaultShortcut"] = "SUPER ALT, SPACE"
        legacy["selectedProfileId"] = "claude"
        legacy["historyLimit"] = None
        legacy["profiles"][1]["model"] = "opus"
        for profile in legacy["profiles"]:
            profile.pop("thinkingEffort", None)

        migrated = Config.from_dict(legacy)

        self.assertEqual(migrated.schema_version, 2)
        self.assertEqual(migrated.selected_profile_id, "claude")
        self.assertIsNone(migrated.history_limit)
        self.assertEqual(migrated.default_shortcut, "SUPER ALT, SPACE")
        self.assertEqual(migrated.profile("claude").model, "opus")
        self.assertIsNone(migrated.profile("claude").thinking_effort)
        self.assertEqual(migrated.ui_shortcuts["model"], "Ctrl+K")

    def test_ui_shortcuts_are_canonical_unique_and_not_reserved(self):
        config = Config.default().to_dict()
        config["uiShortcuts"]["private"] = "control+shift+p"
        parsed = Config.from_dict(config)
        self.assertEqual(parsed.ui_shortcuts["private"], "Ctrl+Shift+P")

        for value in (
            "Ctrl",
            "Enter",
            "Ctrl+Enter",
            "Escape",
            "Alt+Left",
            "Tab",
            "Shift+Tab",
        ):
            invalid = Config.default().to_dict()
            invalid["uiShortcuts"]["model"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                Config.from_dict(invalid)

        duplicate = Config.default().to_dict()
        duplicate["uiShortcuts"]["history"] = duplicate["uiShortcuts"]["model"]
        with self.assertRaises(ValueError):
            Config.from_dict(duplicate)

    def test_thinking_effort_is_safe_optional_identifier(self):
        self.assertEqual(
            Profile(id="safe", name="Safe", adapter_id="codex", thinking_effort="xhigh")
            .thinking_effort,
            "xhigh",
        )
        for value in ("", "High", "high;touch-pwned", 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Profile(
                    id="unsafe",
                    name="Unsafe",
                    adapter_id="codex",
                    thinking_effort=value,
                )

    def test_profile_ids_and_history_limits_are_validated(self):
        with self.assertRaises(ValueError):
            Profile(id="Bad ID", name="Bad", adapter_id="codex")
        with self.assertRaises(ValueError):
            Profile(id="valid", name="Valid", adapter_id="codex", history_limit=0)
        with self.assertRaises(ValueError):
            Config(history_limit=True)

    def test_fixed_working_directory_must_exist(self):
        missing = str(Path(tempfile.gettempdir()) / "quick-chat-missing-directory")
        with self.assertRaises(ValueError):
            Profile(
                id="work",
                name="Work",
                adapter_id="codex",
                working_directory_strategy="fixed",
                working_directory=missing,
            )


if __name__ == "__main__":
    unittest.main()
