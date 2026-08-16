import sys
import time
import unittest
from pathlib import Path

from bridge.quick_chat.adapters.base import AdapterEvent
from bridge.quick_chat.adapters.grok import GrokAdapter
from bridge.quick_chat.adapters.registry import AdapterRegistry
from bridge.quick_chat.engine import Engine
from bridge.quick_chat.models import Config, Profile
from bridge.quick_chat.protocol import Request
from bridge.quick_chat.transports.acp import (
    AcpDisconnected,
    AcpProtocolError,
    AcpTransport,
    text_block,
)


FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


class AcpTransportTests(unittest.TestCase):
    def make_transport(self, *extra, **kwargs):
        return AcpTransport((sys.executable, str(FAKE_AGENT), *extra), **kwargs)

    def tearDown(self):
        transport = getattr(self, "transport", None)
        if transport is not None:
            transport.close()

    def test_acp_initializes_version_one_and_starts_session(self):
        self.transport = self.make_transport()
        session = self.transport.open_session(Path("/tmp"), existing_id=None)
        self.assertEqual(self.transport.protocol_version, 1)
        self.assertEqual(session.id, "session-1")

    def test_disconnected_process_reconnects_once_and_loads_session(self):
        self.transport = self.make_transport()
        session = self.transport.open_session(Path("/tmp"), None)
        self.transport.disconnect()
        events = []
        result = self.transport.prompt(
            session.id,
            [text_block("continue")],
            events.append,
        )
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertEqual(events[0].type, "text_delta")
        self.assertEqual(self.transport.loaded_session_id, session.id)

    def test_permission_request_uses_callback_result(self):
        decisions = []
        self.transport = self.make_transport(
            "--permission",
            permission_handler=lambda request: decisions.append(request) or False,
        )
        session = self.transport.open_session(Path("/tmp"), None)
        self.transport.prompt(session.id, [text_block("test")], lambda event: None)
        self.assertEqual(decisions[0]["operation"], "read_file")
        self.assertFalse(self.transport.permission_responses[-1])

    def test_protocol_mismatch_is_rejected(self):
        self.transport = self.make_transport("--mismatch")
        with self.assertRaises(AcpProtocolError):
            self.transport.open_session(Path("/tmp"), None)

    def test_cancel_targets_active_session(self):
        self.transport = self.make_transport()
        session = self.transport.open_session(Path("/tmp"), None)
        self.assertTrue(self.transport.cancel(session.id))

    def test_partial_prompt_disconnect_is_not_replayed(self):
        self.transport = self.make_transport("--disconnect-prompt")
        session = self.transport.open_session(Path("/tmp"), None)
        with self.assertRaises(AcpDisconnected):
            self.transport.prompt(session.id, [text_block("do not replay")], lambda event: None)

    def test_idle_transport_closes_itself(self):
        self.transport = self.make_transport(idle_seconds=0.03)
        self.transport.open_session(Path("/tmp"), None)
        time.sleep(0.08)
        self.assertFalse(self.transport.running)

    def test_grok_exposes_acp_stdio_command(self):
        self.assertEqual(GrokAdapter().acp_argv(), ("grok", "agent", "stdio"))

    def test_engine_prefers_explicit_acp_profile(self):
        class FakeGrok(GrokAdapter):
            def detect(self):
                return {"available": True, "version": "test", "structured": True}

            def acp_argv(self):
                return (sys.executable, str(FAKE_AGENT))

        class ProcessMustNotRun:
            def run(self, request_id, invocation, emit):
                raise AssertionError("process fallback must not run")

            def cancel(self, request_id):
                return False

        profile = Profile(
            id="grok",
            name="Grok",
            adapter_id="grok",
            transport="acp",
        )
        registry = AdapterRegistry({"grok": FakeGrok()})
        engine = Engine(
            registry,
            ProcessMustNotRun(),
            Config(profiles=(profile,), selected_profile_id="grok"),
        )
        request = Request.from_dict({
            "type": "run",
            "requestId": "req-acp",
            "conversationId": "conversation-acp",
            "profileId": "grok",
            "prompt": "hello",
        })
        try:
            events = list(engine.handle(request))
        finally:
            registry.close()
        self.assertEqual([event.type for event in events], [
            "status", "session", "text_delta", "complete",
        ])


if __name__ == "__main__":
    unittest.main()
