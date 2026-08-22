"""Safe process-backed transport with exact process-group cancellation."""

from __future__ import annotations

import queue
import resource
import subprocess
import threading
import time
from typing import Callable, TextIO

from ..adapters.base import AdapterEvent, Invocation
from ..process_capture import terminate_process_group
from ..sanitize import (
    DIAGNOSTIC_LIMIT,
    PROCESS_LINE_LIMIT,
    bounded_diagnostic,
    bounded_text_prefix,
    iter_bounded_lines,
    strip_terminal_controls,
)
from .base import RunResult


class ProcessTransport:
    def __init__(self, timeout_seconds: float = 120.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._cancelled: set[str] = set()

    def is_running(self, request_id: str) -> bool:
        with self._lock:
            return request_id in self._processes

    @staticmethod
    def _read_lines(
        name: str,
        stream: TextIO,
        output: queue.Queue[tuple[str, str | None]],
    ) -> None:
        try:
            for line in iter_bounded_lines(stream, PROCESS_LINE_LIMIT):
                output.put((name, line))
        finally:
            output.put((name, None))

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        terminate_process_group(process)

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            process = self._processes.get(request_id)
            if process is None:
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
        if invocation.file_size_limit is not None:
            try:
                resource.prlimit(
                    process.pid,
                    resource.RLIMIT_FSIZE,
                    (invocation.file_size_limit, invocation.file_size_limit),
                )
            except (OSError, ValueError):
                self._terminate(process)
                raise RuntimeError("unable to apply provider file size limit")
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
        # A bounded queue backpressures a noisy child instead of retaining its
        # entire output burst in the desktop process.
        output: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=64)
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
        stderr_bytes = 0
        timed_out = False
        try:
            while completed_streams < 2 or process.poll() is None:
                if not timed_out and time.monotonic() - started > self.timeout_seconds:
                    timed_out = True
                    self._terminate(process)
                try:
                    source, line = output.get(timeout=0.05)
                except queue.Empty:
                    continue
                if line is None:
                    completed_streams += 1
                elif source == "stderr":
                    if stderr_bytes < DIAGNOSTIC_LIMIT:
                        remaining = DIAGNOSTIC_LIMIT - stderr_bytes
                        chunk, _, retained_bytes = bounded_text_prefix(line, remaining)
                        stderr_chunks.append(chunk)
                        stderr_bytes += retained_bytes
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
            terminate_process_group(process)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            with self._lock:
                self._processes.pop(request_id, None)
                self._cancelled.discard(request_id)
