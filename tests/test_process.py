import os
import subprocess
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
    @staticmethod
    def process_gone(pid: int) -> bool:
        stat = Path(f"/proc/{pid}/stat")
        if not stat.exists():
            return True
        try:
            return stat.read_text().split()[2] == "Z"
        except (OSError, IndexError):
            return True

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

    def test_oversized_stdout_line_is_bounded_before_queueing(self):
        ProcessTransport(timeout_seconds=2).run(
            "req-1", self.invocation("oversize-line"), self.events.append
        )
        text = "".join(str(event.data.get("text", "")) for event in self.events)
        self.assertLessEqual(len(text), 64 * 1024)
        self.assertIn("truncated", text.lower())

    def test_invocation_file_size_limit_is_applied_to_provider(self):
        target = self.cwd / "provider-session.jsonl"
        invocation = Invocation(
            argv=(sys.executable, str(FAKE_CLI), "write-file", str(target)),
            cwd=self.cwd,
            env={"PATH": os.environ["PATH"]},
            stdin_text=None,
            file_size_limit=1024,
        )

        result = ProcessTransport(timeout_seconds=2).run(
            "req-file-limit", invocation, self.events.append
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertLessEqual(target.stat().st_size, 1024)

    def test_limited_exec_applies_rlimit_before_provider_exec(self):
        target = self.cwd / "wrapped-session.jsonl"
        wrapper = Path(__file__).parents[1] / "bridge" / "quick-chat-limited-exec"

        result = subprocess.run(
            (
                sys.executable,
                str(wrapper),
                "1024",
                sys.executable,
                str(FAKE_CLI),
                "write-file",
                str(target),
            ),
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertLessEqual(target.stat().st_size, 1024)

    def test_timeout_terminates_only_recorded_process(self):
        result = ProcessTransport(timeout_seconds=0.1).run(
            "req-timeout", self.invocation("sleep"), self.events.append
        )
        self.assertTrue(result.timed_out)
        self.assertIsNotNone(result.exit_code)

    def test_timeout_kills_descendants_after_group_leader_exits(self):
        pid_file = self.cwd / "child.pid"
        invocation = Invocation(
            argv=(
                sys.executable,
                str(FAKE_CLI),
                "spawn-descendant",
                str(pid_file),
            ),
            cwd=self.cwd,
            env={"PATH": os.environ["PATH"]},
            stdin_text=None,
        )

        result = ProcessTransport(timeout_seconds=0.05).run(
            "req-descendant", invocation, self.events.append
        )
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 1
        while not self.process_gone(pid) and time.monotonic() < deadline:
            time.sleep(0.01)

        self.assertTrue(result.timed_out)
        self.assertTrue(self.process_gone(pid))

    def test_normal_leader_exit_still_cleans_process_group_descendants(self):
        pid_file = self.cwd / "detached-child.pid"
        invocation = Invocation(
            argv=(
                sys.executable,
                str(FAKE_CLI),
                "spawn-detached-descendant",
                str(pid_file),
            ),
            cwd=self.cwd,
            env={"PATH": os.environ["PATH"]},
            stdin_text=None,
        )

        result = ProcessTransport(timeout_seconds=2).run(
            "req-detached-descendant", invocation, self.events.append
        )
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 1
        while not self.process_gone(pid) and time.monotonic() < deadline:
            time.sleep(0.01)

        self.assertFalse(result.timed_out)
        self.assertTrue(self.process_gone(pid))

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
