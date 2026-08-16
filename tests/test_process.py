import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from bridge.quick_chat.adapters.base import Invocation
from bridge.quick_chat.transports.process import ProcessTransport


FAKE_CLI = Path(__file__).parent / "fixtures" / "fake_stream_cli.py"


class ProcessTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.cwd = Path(self.temporary.name)
        self.events = []

    def tearDown(self):
        self.temporary.cleanup()

    def invocation(self, mode, stdin_text=None):
        return Invocation(
            argv=(sys.executable, str(FAKE_CLI), mode),
            cwd=self.cwd,
            env={"PATH": os.environ["PATH"]},
            stdin_text=stdin_text,
        )

    def test_prompt_is_stdin_and_never_shell_syntax(self):
        transport = ProcessTransport(timeout_seconds=2)
        prompt = "$(touch should-not-exist); `id`"
        result = transport.run(
            "req-1",
            self.invocation("stream", prompt),
            self.events.append,
        )
        self.assertEqual(result.exit_code, 0)
        self.assertFalse((self.cwd / "should-not-exist").exists())
        self.assertIn(prompt, self.events[0].data["text"])

    def test_stderr_is_separate_from_stdout(self):
        result = ProcessTransport(timeout_seconds=2).run(
            "req-1", self.invocation("stderr"), self.events.append
        )
        self.assertEqual(self.events[0].data["text"], "assistant text")
        self.assertNotIn("private diagnostic", self.events[0].data["text"])
        self.assertIn("private diagnostic", result.stderr)

    def test_ansi_and_c0_controls_are_removed(self):
        ProcessTransport(timeout_seconds=2).run(
            "req-1", self.invocation("ansi"), self.events.append
        )
        self.assertEqual(self.events[0].data["text"], "red text")

    def test_timeout_terminates_only_recorded_process(self):
        result = ProcessTransport(timeout_seconds=0.1).run(
            "req-timeout", self.invocation("sleep"), self.events.append
        )
        self.assertTrue(result.timed_out)
        self.assertIsNotNone(result.exit_code)

    def test_cancel_interrupts_the_exact_active_request(self):
        transport = ProcessTransport(timeout_seconds=10)
        result_holder = []
        thread = threading.Thread(
            target=lambda: result_holder.append(
                transport.run(
                    "req-cancel", self.invocation("ignore-int"), self.events.append
                )
            )
        )
        thread.start()
        deadline = time.monotonic() + 2
        while not transport.is_running("req-cancel") and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(transport.cancel("other-request"))
        self.assertTrue(transport.cancel("req-cancel"))
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(result_holder[0].cancelled)


if __name__ == "__main__":
    unittest.main()
