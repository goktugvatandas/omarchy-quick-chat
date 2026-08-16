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
        self.assertEqual(config.selected_profile_id, "codex")
        self.assertEqual(config.history_limit, 20)
        self.assertEqual(config.default_shortcut, "SUPER ALT, SPACE")

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
