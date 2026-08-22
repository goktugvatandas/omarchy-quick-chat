import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from bridge.quick_chat.process_capture import (
    CaptureLimitExceeded,
    run_bounded,
    run_bounded_checked,
)


FAKE_CLI = Path(__file__).parent / "fixtures" / "fake_stream_cli.py"


class BoundedProcessCaptureTests(unittest.TestCase):
    @staticmethod
    def process_gone(pid: int) -> bool:
        stat = Path(f"/proc/{pid}/stat")
        if not stat.exists():
            return True
        try:
            return stat.read_text().split()[2] == "Z"
        except (OSError, IndexError):
            return True

    def run_fixture(
        self,
        mode: str,
        *,
        timeout: float = 2,
        stdout_limit: int = 64 * 1024,
        stderr_limit: int = 64 * 1024,
    ):
        return run_bounded(
            (sys.executable, str(FAKE_CLI), mode),
            env={"PATH": os.environ["PATH"]},
            timeout=timeout,
            stdout_limit=stdout_limit,
            stderr_limit=stderr_limit,
        )

    def test_captures_small_stdout_and_stderr_separately(self):
        result = self.run_fixture("stderr")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "assistant text")
        self.assertEqual(result.stderr.strip(), "private diagnostic")

    def test_rejects_output_before_capture_can_exceed_limit(self):
        with self.assertRaises(CaptureLimitExceeded):
            self.run_fixture("oversize-line")

    def test_times_out_and_terminates_probe_group(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_fixture("sleep", timeout=0.05)

    def test_checked_capture_translates_timeout_to_runtime_error(self):
        with self.assertRaises(RuntimeError):
            run_bounded_checked(
                (sys.executable, str(FAKE_CLI), "sleep"),
                timeout=0.05,
                stdout_limit=64 * 1024,
                stderr_limit=64 * 1024,
            )

    def test_timeout_kills_descendants_after_group_leader_exits(self):
        with tempfile.TemporaryDirectory() as root:
            pid_file = Path(root) / "child.pid"
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded(
                    (sys.executable, str(FAKE_CLI), "spawn-descendant", str(pid_file)),
                    timeout=0.05,
                    stdout_limit=64 * 1024,
                    stderr_limit=64 * 1024,
                )
            pid = int(pid_file.read_text())
            deadline = time.monotonic() + 1
            while not self.process_gone(pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(self.process_gone(pid))


if __name__ == "__main__":
    unittest.main()
