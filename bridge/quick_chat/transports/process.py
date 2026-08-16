"""Safe process-backed transport with exact process-group cancellation."""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time
from typing import Callable, TextIO

from ..adapters.base import AdapterEvent, Invocation
from ..sanitize import bounded_diagnostic, strip_terminal_controls
from .base import RunResult


class ProcessTransport:
    def __init__(self, timeout_seconds: float = 120.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._cancelled: set[str] = set()

    def is_running(self, request_id: str) -> bool:
        with self._lock:
            process = self._processes.get(request_id)
            return process is not None and process.poll() is None

    @staticmethod
    def _read_lines(
        name: str,
        stream: TextIO,
        output: queue.Queue[tuple[str, str | None]],
    ) -> None:
        try:
            for line in stream:
                output.put((name, line))
        finally:
            output.put((name, None))

    @staticmethod
    def _signal_group(process: subprocess.Popen[str], sig: signal.Signals) -> None:
        if process.poll() is None:
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        self._signal_group(process, signal.SIGINT)
        try:
            process.wait(timeout=1)
            return
        except subprocess.TimeoutExpired:
            pass
        self._signal_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            pass
        self._signal_group(process, signal.SIGKILL)
        process.wait(timeout=2)

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            process = self._processes.get(request_id)
            if process is None or process.poll() is not None:
                return False
            self._cancelled.add(request_id)
        self._terminate(process)
        return True

    def run(
        self,
        request_id: str,
        invocation: Invocation,
        emit: Callable[[AdapterEvent], None],
    ) -> RunResult:
        process = subprocess.Popen(
            invocation.argv,
            cwd=invocation.cwd,
            env=dict(invocation.env),
            stdin=subprocess.PIPE if invocation.stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            text=True,
            bufsize=1,
        )
        with self._lock:
            if request_id in self._processes:
                self._terminate(process)
                raise RuntimeError(f"request is already running: {request_id}")
            self._processes[request_id] = process
            self._cancelled.discard(request_id)

        if invocation.stdin_text is not None and process.stdin is not None:
            try:
                process.stdin.write(invocation.stdin_text)
                process.stdin.close()
            except BrokenPipeError:
                pass

        assert process.stdout is not None
        assert process.stderr is not None
        output: queue.Queue[tuple[str, str | None]] = queue.Queue()
        readers = (
            threading.Thread(
                target=self._read_lines,
                args=("stdout", process.stdout, output),
                daemon=True,
            ),
            threading.Thread(
                target=self._read_lines,
                args=("stderr", process.stderr, output),
                daemon=True,
            ),
        )
        for reader in readers:
            reader.start()

        started = time.monotonic()
        completed_streams = 0
        stderr_chunks: list[str] = []
        timed_out = False
        try:
            while completed_streams < 2 or process.poll() is None:
                if process.poll() is None and time.monotonic() - started > self.timeout_seconds:
                    timed_out = True
                    self._terminate(process)
                try:
                    source, line = output.get(timeout=0.05)
                except queue.Empty:
                    continue
                if line is None:
                    completed_streams += 1
                elif source == "stderr":
                    stderr_chunks.append(line)
                else:
                    text = strip_terminal_controls(line.rstrip("\r\n"))
                    if text:
                        emit(AdapterEvent("stdout", {"text": text}))
            for reader in readers:
                reader.join(timeout=0.2)
            exit_code = process.wait()
            with self._lock:
                cancelled = request_id in self._cancelled
            return RunResult(
                exit_code=exit_code,
                stderr=bounded_diagnostic(stderr_chunks),
                cancelled=cancelled,
                timed_out=timed_out,
            )
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            with self._lock:
                self._processes.pop(request_id, None)
                self._cancelled.discard(request_id)
