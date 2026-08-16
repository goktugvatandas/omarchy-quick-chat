import dataclasses
import json
import os
import stat
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bridge.quick_chat.history import HistoryStore
from bridge.quick_chat.models import Config, Conversation, Message, Profile
from bridge.quick_chat.paths import PathSet
from bridge.quick_chat.storage import ConfigStore, atomic_write_json


def sample_conversation(identifier: str = "one", profile_id: str = "codex") -> Conversation:
    updated = datetime(2026, 8, 16, tzinfo=UTC) + timedelta(minutes=int(identifier) if identifier.isdigit() else 0)
    return Conversation(
        id=f"conversation-{identifier}",
        title=f"Conversation {identifier}",
        profile_id=profile_id,
        created_at=updated.isoformat(),
        updated_at=updated.isoformat(),
        messages=(Message(role="user", content=f"Question {identifier}", created_at=updated.isoformat()),),
        cli_sessions={profile_id: f"session-{identifier}"},
    )


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.paths = PathSet.from_env({
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
        })
        self.config = ConfigStore(self.paths).load()
        self.history = HistoryStore(self.paths, self.config)

    def tearDown(self):
        self.temporary.cleanup()

    def test_xdg_paths_use_omarchy_quick_chat_directories(self):
        root = Path(self.temporary.name)
        self.assertEqual(self.paths.config_file, root / "config/omarchy/quick-chat/config.json")
        self.assertEqual(self.paths.history_file, root / "state/omarchy/quick-chat/history.json")
        self.assertEqual(
            self.paths.menu_extension_file,
            root / "home/.config/omarchy/extensions/omarchy-menu.jsonc",
        )
        self.assertEqual(self.paths.capture_dir, root / "runtime/omarchy-quick-chat")

    def test_default_config_has_six_profiles_and_twenty_item_retention(self):
        self.assertEqual(self.config.history_limit, 20)
        self.assertEqual(
            [profile.adapter_id for profile in self.config.profiles],
            ["codex", "claude", "opencode", "grok", "cursor", "pi"],
        )

    def test_config_round_trip_and_file_permissions(self):
        changed = dataclasses.replace(self.config, selected_profile_id="claude")
        store = ConfigStore(self.paths)
        store.save(changed)

        mode = stat.S_IMODE(self.paths.config_file.stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(store.load(), changed)

    def test_loading_v1_config_persists_one_time_v2_migration(self):
        legacy = Config.default().to_dict()
        legacy["schemaVersion"] = 1
        legacy.pop("uiShortcuts", None)
        legacy["defaultShortcut"] = "SUPER ALT, SPACE"
        for profile in legacy["profiles"]:
            profile.pop("thinkingEffort", None)
        atomic_write_json(self.paths.config_file, legacy)

        loaded = ConfigStore(self.paths).load()
        persisted = json.loads(self.paths.config_file.read_text())

        self.assertEqual(loaded.schema_version, 2)
        self.assertEqual(loaded.default_shortcut, "SUPER ALT, SPACE")
        self.assertEqual(persisted["schemaVersion"], 2)
        self.assertIn("uiShortcuts", persisted)
        self.assertTrue(
            all("thinkingEffort" in profile for profile in persisted["profiles"])
        )

    def test_read_only_v1_migration_returns_valid_config_without_quarantine(self):
        legacy = Config.default().to_dict()
        legacy["schemaVersion"] = 1
        legacy.pop("uiShortcuts", None)
        for profile in legacy["profiles"]:
            profile.pop("thinkingEffort", None)
        atomic_write_json(self.paths.config_file, legacy)
        store = ConfigStore(self.paths)

        with patch.object(store, "save", side_effect=OSError("read only")):
            loaded = store.load()

        self.assertEqual(loaded.schema_version, 2)
        self.assertTrue(self.paths.config_file.exists())
        self.assertEqual(
            list(self.paths.config_dir.glob("config.json.corrupt-*")),
            [],
        )

    def test_atomic_write_replaces_content_without_temp_files(self):
        target = self.paths.state_dir / "value.json"
        atomic_write_json(target, {"value": 1})
        atomic_write_json(target, {"value": 2})
        self.assertEqual(json.loads(target.read_text()), {"value": 2})
        self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_private_conversation_writes_nothing(self):
        self.history.upsert(sample_conversation(), private=True)
        self.assertFalse(self.paths.history_file.exists())

    def test_default_retention_keeps_latest_twenty_conversations(self):
        for index in range(25):
            self.history.upsert(sample_conversation(str(index)), private=False)
        conversations = self.history.list()
        self.assertEqual(len(conversations), 20)
        self.assertEqual(conversations[0].id, "conversation-24")
        self.assertEqual(conversations[-1].id, "conversation-5")

    def test_null_retention_keeps_all_conversations(self):
        config = dataclasses.replace(self.config, history_limit=None)
        history = HistoryStore(self.paths, config)
        for index in range(25):
            history.upsert(sample_conversation(str(index)), private=False)
        self.assertEqual(len(history.list()), 25)

    def test_profile_retention_overrides_global_limit(self):
        profile = dataclasses.replace(self.config.profiles[0], history_limit=2)
        config = dataclasses.replace(
            self.config,
            profiles=(profile,) + self.config.profiles[1:],
        )
        history = HistoryStore(self.paths, config)
        for index in range(4):
            history.upsert(sample_conversation(str(index)), private=False)
        self.assertEqual([item.id for item in history.list()], [
            "conversation-3",
            "conversation-2",
        ])

    def test_session_mapping_round_trips_inside_conversation(self):
        self.history.upsert(sample_conversation("7"), private=False)
        loaded = HistoryStore(self.paths, self.config).list()[0]
        self.assertEqual(loaded.cli_sessions, {"codex": "session-7"})

    def test_clear_removes_persisted_history(self):
        self.history.upsert(sample_conversation(), private=False)
        self.history.clear()
        self.assertEqual(self.history.list(), [])
        self.assertFalse(self.paths.history_file.exists())

    def test_invalid_config_is_quarantined_and_defaults_are_returned(self):
        self.paths.config_dir.mkdir(parents=True)
        self.paths.config_file.write_text("{broken")
        store = ConfigStore(self.paths)
        config = store.load()

        self.assertEqual(config, Config.default())
        self.assertEqual(store.last_diagnostic["code"], "history_recovered")
        quarantined = list(self.paths.config_dir.glob("config.json.corrupt-*"))
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(store.last_diagnostic["path"], str(quarantined[0]))

    def test_invalid_history_is_quarantined(self):
        self.paths.state_dir.mkdir(parents=True)
        self.paths.history_file.write_text(json.dumps({"schemaVersion": 99}))
        history = HistoryStore(self.paths, self.config)

        self.assertEqual(history.list(), [])
        self.assertEqual(history.last_diagnostic["code"], "history_recovered")
        self.assertEqual(
            len(list(self.paths.state_dir.glob("history.json.corrupt-*"))),
            1,
        )


if __name__ == "__main__":
    unittest.main()
