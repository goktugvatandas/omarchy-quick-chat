import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge.quick_chat.main import run
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


if __name__ == "__main__":
    unittest.main()
