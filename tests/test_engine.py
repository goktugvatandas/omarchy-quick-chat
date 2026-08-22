import dataclasses
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from bridge.quick_chat.adapters.base import (
    AdapterContext,
    AdapterEvent,
    Capabilities,
    EffortOption,
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


class SlowStartAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.start_entered = threading.Event()
        self.start_release = threading.Event()

    def start(self, context):
        self.start_entered.set()
        self.start_release.wait(timeout=1)
        return super().start(context)


class MultiToolAdapter(FakeAdapter):
    capabilities = Capabilities(True, True, True, False, True, True)

    def parse_event(self, event):
        return [
            AdapterEvent("tool_request", {
                "approvalId": f"approval-{index}",
                "title": "Read",
                "operation": "read_file",
                "details": f"file-{index}",
            })
            for index in range(3)
        ]


class EffortAdapter(FakeAdapter):
    def effort_options(self, cwd=None):
        return (EffortOption("low", "Low", "Faster"),)


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


class CancellableRegistrationTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.registered = threading.Event()
        self.cancelled = threading.Event()
        self.cancel_calls = 0

    def is_running(self, request_id):
        return self.registered.is_set() and not self.cancelled.is_set()

    def run(self, request_id, invocation, emit):
        self.registered.set()
        self.cancelled.wait(timeout=1)
        return RunResult(-15, "", self.cancelled.is_set(), False)

    def cancel(self, request_id):
        if not self.registered.is_set():
            return False
        self.cancel_calls += 1
        self.cancelled.set()
        return True


class BurstTransport(FakeTransport):
    def run(self, request_id, invocation, emit):
        self.entered.set()
        for _ in range(10):
            emit(AdapterEvent("stdout", {"text": "x" * (64 * 1024)}))
        return self.result


class UnicodeBurstTransport(FakeTransport):
    def run(self, request_id, invocation, emit):
        self.entered.set()
        for _ in range(10):
            emit(AdapterEvent("stdout", {"text": "🙂" * 8192}))
        return self.result


class EventFloodTransport(FakeTransport):
    def run(self, request_id, invocation, emit):
        self.entered.set()
        for _ in range(5000):
            emit(AdapterEvent("stdout", {"text": "x"}))
        return self.result


class BackpressuredCancelTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.cancel_entered = threading.Event()
        self.output_drained = threading.Event()

    def run(self, request_id, invocation, emit):
        self.entered.set()
        for _ in range(5000):
            emit(AdapterEvent("stdout", {"text": "x"}))
        self.output_drained.set()
        return self.result

    def cancel(self, request_id):
        self.cancel_entered.set()
        return self.output_drained.wait(timeout=1)


class SessionLimitAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.finalized = False

    def session_limit_exceeded(self):
        return True

    def finalize_session(self):
        self.finalized = True


class TerminalFloodAdapter(FakeAdapter):
    def parse_event(self, event):
        return [
            AdapterEvent("complete", {f"key-{index}": "value"})
            for index in range(5000)
        ]


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

    def test_engine_bounds_total_assistant_output_before_qml_and_history(self):
        events = list(
            Engine(self.registry, BurstTransport(), Config.default()).handle(request())
        )
        text = "".join(
            str(event.data.get("text", ""))
            for event in events
            if event.type == "text_delta"
        )
        self.assertLessEqual(len(text), 256 * 1024)
        self.assertEqual(text.lower().count("truncated"), 1)
        self.assertEqual(events[-1].type, "complete")

    def test_engine_bounds_provider_event_count_before_qml(self):
        events = list(
            Engine(self.registry, EventFloodTransport(), Config.default()).handle(request())
        )
        deltas = [event for event in events if event.type == "text_delta"]
        self.assertLessEqual(len(deltas), 1025)
        self.assertEqual(
            "".join(str(event.data.get("text", "")) for event in deltas)
            .lower()
            .count("truncated"),
            1,
        )
        self.assertEqual(events[-1].type, "complete")

    def test_provider_session_limit_cancels_and_finalizes(self):
        adapter = SessionLimitAdapter()
        registry = AdapterRegistry({"codex": adapter})
        events = list(Engine(registry, FakeTransport(), Config.default()).handle(request()))

        self.assertEqual(events[-1].type, "error")
        self.assertEqual(events[-1].data["code"], "session_too_large")
        self.assertTrue(adapter.finalized)

    def test_event_limit_cancellation_does_not_block_queue_drain(self):
        transport = BackpressuredCancelTransport()
        started = time.monotonic()

        events = list(Engine(self.registry, transport, Config.default()).handle(request()))

        self.assertLess(time.monotonic() - started, 0.75)
        self.assertTrue(transport.cancel_entered.wait(timeout=0.2))
        self.assertTrue(transport.output_drained.is_set())
        self.assertEqual(events[-1].type, "complete")

    def test_engine_bounds_terminal_event_count_and_aggregate_metadata(self):
        registry = AdapterRegistry({"codex": TerminalFloodAdapter()})
        events = list(Engine(registry, FakeTransport(), Config.default()).handle(request()))

        self.assertEqual(events[-1].type, "complete")
        self.assertLessEqual(len(events[-1].data), 128)
        text = "".join(
            str(event.data.get("text", ""))
            for event in events
            if event.type == "text_delta"
        )
        self.assertEqual(text.lower().count("truncated"), 1)

    def test_engine_response_budget_is_measured_in_utf8_bytes(self):
        events = list(
            Engine(self.registry, UnicodeBurstTransport(), Config.default()).handle(request())
        )
        text = "".join(
            str(event.data.get("text", ""))
            for event in events
            if event.type == "text_delta"
        )
        self.assertLessEqual(len(text.encode("utf-8")), 256 * 1024)
        self.assertEqual(text.lower().count("truncated"), 1)

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

    def test_cancel_before_transport_registration_is_latched_once(self):
        adapter = SlowStartAdapter()
        transport = CancellableRegistrationTransport()
        engine = Engine(AdapterRegistry({"codex": adapter}), transport, Config.default())
        events = []
        thread = threading.Thread(target=lambda: events.extend(engine.handle(request())))
        thread.start()
        self.assertTrue(adapter.start_entered.wait(timeout=1))

        self.assertTrue(engine.cancel("req-1"))
        self.assertTrue(engine.cancel("req-1"))
        adapter.start_release.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(transport.cancel_calls, 1)
        self.assertEqual(events[-1].data["stopReason"], "cancelled")

    def test_existing_cli_session_is_passed_to_adapter(self):
        engine = Engine(
            self.registry,
            FakeTransport(),
            Config.default(),
            session_resolver=lambda conversation_id, adapter_id: "session-existing",
        )
        list(engine.handle(request()))
        self.assertEqual(self.adapter.contexts[0].session_id, "session-existing")

    def test_unsupported_effort_stops_before_transport(self):
        adapter = EffortAdapter()
        registry = AdapterRegistry({"codex": adapter})
        transport = FakeTransport()
        profile = dataclasses.replace(
            Config.default().profiles[0],
            thinking_effort="made-up",
        )
        config = dataclasses.replace(
            Config.default(),
            profiles=(profile,) + Config.default().profiles[1:],
        )

        events = list(Engine(registry, transport, config).handle(request()))

        self.assertEqual(events[-1].type, "error")
        self.assertEqual(events[-1].data["code"], "unsupported_effort")
        self.assertFalse(transport.entered.is_set())
        self.assertEqual(adapter.contexts, [])

    def test_supported_effort_reaches_adapter_context(self):
        adapter = EffortAdapter()
        registry = AdapterRegistry({"codex": adapter})
        profile = dataclasses.replace(
            Config.default().profiles[0],
            thinking_effort="low",
        )
        config = dataclasses.replace(
            Config.default(),
            profiles=(profile,) + Config.default().profiles[1:],
        )

        events = list(Engine(registry, FakeTransport(), config).handle(request()))

        self.assertEqual(events[-1].type, "complete")
        self.assertEqual(adapter.contexts[0].thinking_effort, "low")

    def test_custom_profile_rejects_effort_without_registry_lookup(self):
        custom = dataclasses.replace(
            Config.default().profiles[0],
            id="custom-test",
            adapter_id="custom",
            custom_executable="safe-custom",
            thinking_effort="low",
        )
        config = Config(profiles=(custom,), selected_profile_id=custom.id)
        custom_request = dataclasses.replace(request(), profile_id=custom.id)

        events = list(
            Engine(AdapterRegistry({}), FakeTransport(), config).handle(custom_request)
        )

        self.assertEqual(events[-1].data["code"], "unsupported_effort")

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

    def test_cancel_denies_queued_approvals_without_more_waits(self):
        transport = ApprovalTransport()
        engine = Engine(
            AdapterRegistry({"codex": MultiToolAdapter()}),
            transport,
            Config.default(),
            approval_timeout_seconds=1,
        )
        generator = engine.handle(request())
        self.assertEqual(next(generator).type, "status")
        self.assertEqual(next(generator).type, "tool_request")
        started = time.monotonic()

        self.assertTrue(engine.cancel("req-1"))
        terminal = next(generator)

        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(terminal.type, "error")
        self.assertEqual(terminal.data["code"], "approval_denied")

    def test_cancel_wakes_pending_approval_as_denied(self):
        transport = ApprovalTransport()
        engine = Engine(
            AdapterRegistry({"codex": RelayableToolAdapter()}),
            transport,
            Config.default(),
            approval_timeout_seconds=1,
        )
        generator = engine.handle(request())
        self.assertEqual(next(generator).type, "status")
        self.assertEqual(next(generator).type, "tool_request")

        self.assertTrue(engine.cancel("req-1"))
        terminal = next(generator)

        self.assertEqual(terminal.type, "error")
        self.assertEqual(terminal.data["code"], "approval_denied")
        self.assertEqual(transport.responses[-1], ("req-1", "approval-1", False))

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
