import json
import os
import re
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from bridge.quick_chat.main import main
from bridge.quick_chat.menu import LEGACY_MENU_ENTRY, MENU_ENTRY_ID, install_menu_entry


def parse_jsonc(content: str) -> dict:
    stripped = re.sub(r"^\s*//[^\n]*(\n|$)", "", content, flags=re.MULTILINE)
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    return json.loads(stripped)


class MenuIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "omarchy-menu.jsonc"

    def tearDown(self):
        self.temporary.cleanup()

    def test_installs_root_entry_and_preserves_existing_jsonc(self):
        original = '{\n  // Keep this comment.\n  "personal": {"label":"Personal"},\n}\n'
        self.path.write_text(original)

        result = install_menu_entry(self.path)
        content = self.path.read_text()
        parsed = parse_jsonc(content)

        self.assertTrue(result.changed)
        self.assertIn("// Keep this comment.", content)
        self.assertEqual(parsed["personal"]["label"], "Personal")
        self.assertEqual(parsed[MENU_ENTRY_ID]["label"], "Quick Chat")
        self.assertEqual(parsed[MENU_ENTRY_ID]["after"], "apps")
        self.assertIn("goktugvatandas.quick-chat", parsed[MENU_ENTRY_ID]["action"])
        self.assertEqual(next(iter(parsed)), MENU_ENTRY_ID)

        installed = self.path.read_text()
        second = install_menu_entry(self.path)
        self.assertFalse(second.changed)
        self.assertEqual(self.path.read_text(), installed)

    def test_install_is_idempotent_and_respects_user_override(self):
        self.path.write_text('{"quick-chat":{"label":"My Chat"}}\n')
        before = self.path.read_text()

        result = install_menu_entry(self.path)

        self.assertFalse(result.changed)
        self.assertEqual(self.path.read_text(), before)

    def test_upgrades_the_plugin_generated_entry_without_touching_comments(self):
        legacy = json.dumps(LEGACY_MENU_ENTRY, ensure_ascii=False, separators=(",", ":"))
        self.path.write_text(
            "{\n"
            f'  "{MENU_ENTRY_ID}": {legacy},\n'
            "  // User-owned content stays byte-for-byte.\n"
            '  "personal": {"label":"Personal"},\n'
            "}\n"
        )

        result = install_menu_entry(self.path)
        content = self.path.read_text()
        parsed = parse_jsonc(content)

        self.assertTrue(result.changed)
        self.assertEqual(parsed[MENU_ENTRY_ID]["after"], "apps")
        self.assertIn("// User-owned content stays byte-for-byte.", content)
        self.assertEqual(parsed["personal"]["label"], "Personal")

    def test_supports_items_wrapper(self):
        self.path.write_text('{\n  "items": {\n    "personal": {"label":"Personal"}\n  }\n}\n')

        install_menu_entry(self.path)
        parsed = parse_jsonc(self.path.read_text())

        self.assertIn(MENU_ENTRY_ID, parsed["items"])
        self.assertEqual(next(iter(parsed["items"])), MENU_ENTRY_ID)

    def test_bridge_menu_install_command_uses_omarchy_user_path(self):
        home = Path(self.temporary.name) / "home"
        output = StringIO()

        with patch.dict(os.environ, {"HOME": str(home)}):
            exit_code = main(["menu", "install"], StringIO(), output)

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["changed"])
        self.assertEqual(
            Path(payload["path"]),
            home / ".config/omarchy/extensions/omarchy-menu.jsonc",
        )


if __name__ == "__main__":
    unittest.main()
