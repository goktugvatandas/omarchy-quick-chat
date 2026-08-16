import dataclasses
import os
import tempfile
import threading
import unittest
from pathlib import Path

from bridge.quick_chat.adapters.base import (
    AdapterContext,
    AdapterEvent,
    Capabilities,
    Invocation,
)
from bridge.quick_chat.adapters.registry import AdapterRegistry
from bridge.quick_chat.engine import BusyError, Engine
from bridge.quick_chat.models import Config
from bridge.quick_chat.protocol import Attachment, Request
from bridge.quick_chat.transports.base import RunResult


class FakeAdapter:
    id = "codex"
    capabilities = Capabilities(True, True, True, False, True, False)

    def __init__(self):
        self.contexts = []

    def detect(self):
        return {"available": True, "version": "test"}

    def start(self, context: AdapterContext):
        self.contexts.append(context)
        return Invocation(("fake",), context.cwd, {"PATH": ""}, context.prompt)

    def parse_event(self, event: AdapterEvent):
        if event.type == "stdout":
            return [AdapterEvent("text_delta", {"text": event.data["text"]})]
        return []


class FakeTransport:
    def __init__(self, block=False, result=None):
        self.block = block
        self.entered = threading.Event()
        self.release = threading.Event()
        self.result = result or RunResult(0, "", False, False)

    def run(self, request_id, invocation, emit):
        self.entered.set()
        if self.block:
            self.release.wait(timeout=3)
        emit(AdapterEvent("stdout", {"text": "answer"}))
        return self.result

    def cancel(self, request_id):
        self.release.set()
        return True


class ToolRequestAdapter(FakeAdapter):
    capabilities = Capabilities(True, True, True, False, True, False)

    def parse_event(self, event):
        return [AdapterEvent("tool_request", {
            "approvalId": "approval-1",
            "title": "Run tool",
            "operation": "write_file",
            "details": "/tmp/file",
        })]


class RelayableToolAdapter(ToolRequestAdapter):
    capabilities = Capabilities(True, True, True, False, True, True)


class ApprovalTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.responses = []

    def respond_approval(self, request_id, approval_id, approved):
        self.responses.append((request_id, approval_id, approved))


def request(identifier="req-1"):
    return Request.from_dict({
        "type": "run",
        "requestId": identifier,
        "conversationId": "conv-1",
        "profileId": "codex",
        "prompt": "question",
    })


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.registry = AdapterRegistry({"codex": self.adapter})

    def test_engine_emits_start_delta_and_exactly_one_terminal_event(self):
        engine = Engine(self.registry, FakeTransport(), Config.default())
        events = list(engine.handle(request()))
        self.assertEqual(events[0].data["status"], "starting")
        self.assertEqual(events[1].type, "text_delta")
        self.assertEqual(events[-1].type, "complete")
        self.assertEqual(sum(event.type in {"complete", "error"} for event in events), 1)

    def test_nonzero_exit_is_an_error_and_keeps_stderr_diagnostic(self):
        transport = FakeTransport(result=RunResult(7, "failed", False, False))
        events = list(Engine(self.registry, transport, Config.default()).handle(request()))
        self.assertEqual(events[-1].type, "error")
        self.assertEqual(events[-1].data["code"], "cli_failed")
        self.assertEqual(events[-1].data["diagnostic"], "failed")

    def test_second_concurrent_run_is_rejected(self):
        transport = FakeTransport(block=True)
        engine = Engine(self.registry, transport, Config.default())
        first_events = []
        thread = threading.Thread(
            target=lambda: first_events.extend(engine.handle(request("req-1")))
        )
        thread.start()
        self.assertTrue(transport.entered.wait(timeout=2))
        with self.assertRaises(BusyError):
            list(engine.handle(request("req-2")))
        transport.release.set()
        thread.join(timeout=3)

    def test_existing_cli_session_is_passed_to_adapter(self):
        engine = Engine(
            self.registry,
            FakeTransport(),
            Config.default(),
            session_resolver=lambda conversation_id, adapter_id: "session-existing",
        )
        list(engine.handle(request()))
        self.assertEqual(self.adapter.contexts[0].session_id, "session-existing")

    def test_attachments_are_cleaned_after_every_terminal_path(self):
        cleaned = []
        engine = Engine(
            self.registry,
            FakeTransport(),
            Config.default(),
            attachment_cleanup=lambda identifiers: cleaned.extend(identifiers),
        )
        value = request()
        value = dataclasses.replace(value, attachments=(
            Attachment("attachment-1", "text", None, "selected", "text/plain"),
        ))
        list(engine.handle(value))
        self.assertEqual(cleaned, ["attachment-1"])

    def test_unrelayable_tool_request_is_denied(self):
        registry = AdapterRegistry({"codex": ToolRequestAdapter()})
        events = list(Engine(registry, FakeTransport(), Config.default()).handle(request()))
        self.assertEqual(events[-1].type, "error")
        self.assertEqual(events[-1].data["code"], "approval_not_relayable")
        self.assertIsInstance(events[-1].data["continueCommand"], list)

    def test_relayable_approval_accepts_only_matching_approve_once(self):
        transport = ApprovalTransport()
        engine = Engine(
            AdapterRegistry({"codex": RelayableToolAdapter()}),
            transport,
            Config.default(),
            approval_timeout_seconds=1,
        )
        generator = engine.handle(request())
        self.assertEqual(next(generator).type, "status")
        approval = next(generator)
        self.assertEqual(approval.type, "tool_request")
        self.assertFalse(engine.resolve_approval("req-1", "wrong", True))
        self.assertTrue(engine.resolve_approval("req-1", "approval-1", True))
        self.assertEqual(next(generator).type, "complete")
        self.assertEqual(transport.responses, [("req-1", "approval-1", True)])

    def test_approval_timeout_becomes_deny(self):
        transport = ApprovalTransport()
        engine = Engine(
            AdapterRegistry({"codex": RelayableToolAdapter()}),
            transport,
            Config.default(),
            approval_timeout_seconds=0.01,
        )
        events = list(engine.handle(request()))
        self.assertEqual(events[-1].data["code"], "approval_timeout")
        self.assertEqual(transport.responses[-1], ("req-1", "approval-1", False))


if __name__ == "__main__":
    unittest.main()
