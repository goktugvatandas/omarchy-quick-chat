import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge.quick_chat.main import _handle_local_request, run
from bridge.quick_chat.adapters.base import Capabilities, ModelOption
from bridge.quick_chat.adapters.registry import AdapterRegistry
from bridge.quick_chat.protocol import Event, ProtocolError, Request


class RequestTests(unittest.TestCase):
    def test_run_request_requires_profile_prompt_and_conversation(self):
        request = Request.from_dict({
            "type": "run",
            "requestId": "req-1",
            "conversationId": "conv-1",
            "profileId": "default",
            "prompt": "Explain this",
            "attachments": [],
            "private": False,
        })
        self.assertEqual(request.profile_id, "default")

    def test_run_request_rejects_missing_required_fields(self):
        base = {
            "type": "run",
            "requestId": "req-1",
            "conversationId": "conv-1",
            "profileId": "default",
            "prompt": "Explain this",
        }
        for field in ("conversationId", "profileId", "prompt"):
            with self.subTest(field=field):
                value = dict(base)
                del value[field]
                with self.assertRaises(ProtocolError):
                    Request.from_dict(value)

    def test_request_rejects_unknown_type_empty_id_and_non_string_prompt(self):
        invalid = (
            {"type": "unknown", "requestId": "req-1"},
            {"type": "probe", "requestId": ""},
            {
                "type": "run",
                "requestId": "req-1",
                "conversationId": "conv-1",
                "profileId": "default",
                "prompt": 42,
            },
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ProtocolError):
                    Request.from_dict(value)

    def test_attachment_must_be_inside_runtime_capture_root(self):
        with tempfile.TemporaryDirectory() as runtime:
            capture_root = Path(runtime) / "omarchy-quick-chat"
            capture_root.mkdir()
            inside = capture_root / "capture.png"
            inside.touch()
            request = {
                "type": "run",
                "requestId": "req-1",
                "conversationId": "conv-1",
                "profileId": "default",
                "prompt": "What is shown?",
                "attachments": [{
                    "id": "attachment-1",
                    "kind": "image",
                    "path": str(inside),
                    "text": None,
                    "mimeType": "image/png",
                }],
            }
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
                parsed = Request.from_dict(request)
                self.assertEqual(parsed.attachments[0].path, str(inside))

                request["attachments"][0]["path"] = str(Path(runtime) / "outside.png")
                with self.assertRaises(ProtocolError):
                    Request.from_dict(request)

    def test_request_body_is_limited_to_one_mebibyte(self):
        request = {
            "type": "run",
            "requestId": "req-1",
            "conversationId": "conv-1",
            "profileId": "default",
            "prompt": "x" * (1024 * 1024),
        }
        with self.assertRaises(ProtocolError):
            Request.from_dict(request)

    def test_clear_confirmation_must_be_a_boolean(self):
        parsed = Request.from_dict({
            "type": "history.clear",
            "requestId": "req-clear",
            "confirm": True,
        })
        self.assertTrue(parsed.confirm)
        with self.assertRaises(ProtocolError):
            Request.from_dict({
                "type": "history.clear",
                "requestId": "req-clear",
                "confirm": "yes",
            })

    def test_model_list_request_accepts_adapter_and_refresh(self):
        parsed = Request.from_dict({
            "type": "models.list",
            "requestId": "req-models",
            "adapterId": "cursor",
            "refresh": True,
        })
        self.assertEqual(parsed.adapter_id, "cursor")
        self.assertTrue(parsed.refresh)


class FakeModelAdapter:
    id = "codex"
    capabilities = Capabilities(True, True, True, True, True, False)

    def detect(self):
        return {"available": True, "version": "test"}

    def discover_models(self, cwd=None):
        return (
            ModelOption("gpt-5.6-sol", "GPT-5.6 Sol", "Fast coding model"),
            ModelOption("gpt-5.6-terra", "GPT-5.6 Terra", "Balanced coding model"),
        )


class ModelCatalogRequestTests(unittest.TestCase):
    def test_local_model_request_returns_adapter_catalog(self):
        request = Request.from_dict({
            "type": "models.list",
            "requestId": "req-models",
            "adapterId": "codex",
        })
        registry = AdapterRegistry({"codex": FakeModelAdapter()})
        events = _handle_local_request(request, registry)
        self.assertEqual(events[-1].type, "complete")
        self.assertEqual(events[-1].data["adapterId"], "codex")
        self.assertEqual(
            [model["id"] for model in events[-1].data["models"]],
            ["gpt-5.6-sol", "gpt-5.6-terra"],
        )


class EventTests(unittest.TestCase):
    def test_event_json_is_one_sanitized_line(self):
        encoded = Event("text_delta", "req-1", {"text": "hello\nworld"}).to_json()
        self.assertEqual(len(encoded.splitlines()), 1)
        self.assertEqual(json.loads(encoded)["data"]["text"], "hello\nworld")

    def test_event_rejects_unknown_type(self):
        with self.assertRaises(ProtocolError):
            Event("mystery", "req-1", {}).to_json()


class JsonLineLoopTests(unittest.TestCase):
    def test_loop_emits_ready_once_and_survives_bad_input(self):
        source = io.StringIO(
            "not json\n"
            + json.dumps({"type": "probe", "requestId": "req-2"})
            + "\n"
        )
        destination = io.StringIO()

        run(source, destination)

        events = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual(events[0], {
            "type": "ready",
            "requestId": "bridge",
            "data": {"protocolVersion": 1},
        })
        self.assertEqual(events[1]["type"], "error")
        self.assertEqual(events[1]["data"]["code"], "invalid_request")
        self.assertEqual(events[2]["type"], "status")
        self.assertEqual(events[2]["requestId"], "req-2")

    def test_loop_rejects_an_oversize_physical_line(self):
        source = io.StringIO("{" + "x" * (1024 * 1024) + "}\n")
        destination = io.StringIO()

        run(source, destination)

        events = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual(events[-1]["data"]["code"], "request_too_large")

    def test_profiles_request_returns_six_local_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            source = io.StringIO(
                json.dumps({"type": "profiles", "requestId": "req-profiles"})
                + "\n"
            )
            destination = io.StringIO()
            environment = {
                "HOME": str(Path(root) / "home"),
                "XDG_CONFIG_HOME": str(Path(root) / "config"),
                "XDG_STATE_HOME": str(Path(root) / "state"),
                "XDG_RUNTIME_DIR": str(Path(root) / "runtime"),
            }
            with patch.dict(os.environ, environment, clear=True):
                run(source, destination)

        events = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(
            [profile["adapterId"] for profile in events[-1]["data"]["config"]["profiles"]],
            ["codex", "claude", "opencode", "grok", "cursor", "pi"],
        )


if __name__ == "__main__":
    unittest.main()
