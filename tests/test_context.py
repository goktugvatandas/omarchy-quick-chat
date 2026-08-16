import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path

from bridge.quick_chat.context.app import ActiveAppProvider, ActiveProjectResolver
from bridge.quick_chat.context.base import ContextManager
from bridge.quick_chat.context.capture import CaptureProvider
from bridge.quick_chat.context.ocr import OcrProvider
from bridge.quick_chat.context.omarchy import OmarchyQueryProvider
from bridge.quick_chat.context.selection import SelectionProvider
from bridge.quick_chat.history import HistoryStore
from bridge.quick_chat.models import Conversation, Message
from bridge.quick_chat.paths import PathSet
from bridge.quick_chat.storage import ConfigStore


class FakeRunner:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, argv, **kwargs):
        command = list(argv)
        self.calls.append(command)
        response = self.responses.get(tuple(command), (0, "", ""))
        return subprocess.CompletedProcess(command, *response)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.paths = PathSet.from_env({
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
        })
        self.source = root / "source.png"
        self.source.write_bytes(b"png-data")

    def tearDown(self):
        self.temporary.cleanup()

    def test_fullscreen_capture_uses_omarchy_and_returns_runtime_file(self):
        command = ("omarchy", "capture", "screenshot", "fullscreen", "save")
        runner = FakeRunner({command: (0, f"saved\n{self.source}\n", "")})
        capture = CaptureProvider(self.paths, runner=runner)
        attachment = capture.fullscreen()
        self.assertEqual(runner.calls[0], list(command))
        self.assertTrue(attachment.path.is_relative_to(self.paths.capture_dir))
        self.assertEqual(stat.S_IMODE(attachment.path.stat().st_mode), 0o600)

    def test_active_window_capture_uses_windows_mode(self):
        command = ("omarchy", "capture", "screenshot", "windows", "save")
        runner = FakeRunner({command: (0, f"{self.source}\n", "")})
        CaptureProvider(self.paths, runner=runner).active_window()
        self.assertEqual(runner.calls[0], list(command))

    def test_active_app_metadata_is_parsed_as_data(self):
        command = ("hyprctl", "-j", "activewindow")
        payload = json.dumps({"class": "org.example.App; touch nope", "title": "A title", "pid": 42})
        provider = ActiveAppProvider(FakeRunner({command: (0, payload, "")}))
        metadata = provider.get()
        self.assertEqual(metadata.app_name, "org.example.App; touch nope")
        self.assertEqual(metadata.window_title, "A title")
        self.assertEqual(metadata.pid, 42)

    def test_selected_text_is_explicit_and_capped(self):
        command = ("wl-paste", "--primary", "--no-newline")
        provider = SelectionProvider(FakeRunner({command: (0, "x" * 300000, "")}))
        attachment = provider.capture()
        self.assertEqual(len(attachment.text.encode()), 256 * 1024)

    def test_ocr_uses_tesseract_argument_array(self):
        command = ("tesseract", str(self.source), "stdout")
        runner = FakeRunner({command: (0, "recognized text", "")})
        attachment = OcrProvider(runner).convert(self.source)
        self.assertEqual(runner.calls[0], list(command))
        self.assertEqual(attachment.text, "recognized text")

    def test_omarchy_queries_are_allowlisted(self):
        runner = FakeRunner({
            ("omarchy", "commands", "--json"): (0, "[]", ""),
        })
        provider = OmarchyQueryProvider(runner)
        self.assertEqual(provider.query("commands").text, "[]")
        with self.assertRaises(ValueError):
            provider.query("plugin remove")

    def test_active_project_resolves_proc_cwd_and_falls_back(self):
        proc_root = Path(self.temporary.name) / "proc"
        project = Path(self.temporary.name) / "project"
        project.mkdir()
        (proc_root / "42").mkdir(parents=True)
        (proc_root / "42" / "cwd").symlink_to(project, target_is_directory=True)
        resolver = ActiveProjectResolver(proc_root=proc_root, home=Path("/fallback"))
        self.assertEqual(resolver.resolve(42).path, project)
        fallback = resolver.resolve(None)
        self.assertEqual(fallback.path, Path("/fallback"))
        self.assertIsNotNone(fallback.diagnostic)

    def test_remove_and_private_completion_delete_capture(self):
        command = ("omarchy", "capture", "screenshot", "windows", "save")
        runner = FakeRunner({command: (0, f"{self.source}\n", "")})
        manager = ContextManager(self.paths)
        attachment = CaptureProvider(self.paths, runner=runner).active_window()
        manager.add(attachment)
        self.assertTrue(attachment.path.exists())
        manager.remove(attachment.id)
        self.assertFalse(attachment.path.exists())

    def test_sweep_removes_old_regular_files_without_following_symlinks(self):
        self.paths.capture_dir.mkdir(parents=True)
        old = self.paths.capture_dir / "old.png"
        old.write_bytes(b"old")
        stale = time.time() - 25 * 60 * 60
        os.utime(old, (stale, stale))
        outside = Path(self.temporary.name) / "outside"
        outside.write_text("keep")
        link = self.paths.capture_dir / "link"
        link.symlink_to(outside)
        manager = ContextManager(self.paths)
        manager.sweep()
        self.assertFalse(old.exists())
        self.assertTrue(link.is_symlink())
        self.assertEqual(outside.read_text(), "keep")

    def test_private_image_turn_leaves_no_history_mapping_or_capture(self):
        command = ("omarchy", "capture", "screenshot", "windows", "save")
        runner = FakeRunner({command: (0, f"{self.source}\n", "")})
        manager = ContextManager(self.paths)
        attachment = manager.add(CaptureProvider(self.paths, runner=runner).active_window())
        now = datetime.now(UTC).isoformat()
        conversation = Conversation(
            id="private-conversation",
            title="Private",
            profile_id="codex",
            created_at=now,
            updated_at=now,
            messages=(Message("user", "private image", now),),
            cli_sessions={"codex": "private-session"},
        )
        history = HistoryStore(self.paths, ConfigStore(self.paths).load())
        history.upsert(conversation, private=True)
        manager.remove_many([attachment.id])
        self.assertFalse(self.paths.history_file.exists())
        self.assertFalse(attachment.path.exists())


if __name__ == "__main__":
    unittest.main()
