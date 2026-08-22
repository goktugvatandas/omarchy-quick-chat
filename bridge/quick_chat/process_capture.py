"""Bounded stdout and stderr capture for short provider probes."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class CapturedProcess:
    returncode: int
    stdout: str
    stderr: str


class CaptureLimitExceeded(RuntimeError):
    pass


def terminate_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if process.poll() is None:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    if process.poll() is None:
        process.wait(timeout=1)


def run_bounded(
    argv: tuple[str, ...],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float,
    stdout_limit: int,
    stderr_limit: int,
) -> CapturedProcess:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    try:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        deadline = time.monotonic() + timeout

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            ready = selector.select(remaining)
            if not ready:
                raise subprocess.TimeoutExpired(argv, timeout)
            for key, _ in ready:
                stream = key.fileobj
                chunk = os.read(key.fd, 64 * 1024)
                if not chunk:
                    selector.unregister(stream)
                    continue
                name = key.data
                if len(buffers[name]) + len(chunk) > limits[name]:
                    raise CaptureLimitExceeded(
                        f"{argv[0]} exceeded the {name} capture limit"
                    )
                buffers[name].extend(chunk)

        remaining = max(0.0, deadline - time.monotonic())
        returncode = process.wait(timeout=remaining)
        return CapturedProcess(
            returncode,
            buffers["stdout"].decode("utf-8", errors="replace"),
            buffers["stderr"].decode("utf-8", errors="replace"),
        )
    finally:
        selector.close()
        terminate_process_group(process)
        process.stdout.close()
        process.stderr.close()


def run_bounded_checked(*args, **kwargs) -> CapturedProcess:
    """Translate capture limits and timeouts into bridge-safe runtime errors."""
    argv = args[0] if args else kwargs.get("argv", ("provider",))
    try:
        return run_bounded(*args, **kwargs)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{argv[0]} timed out") from error
    except CaptureLimitExceeded as error:
        raise RuntimeError(str(error)) from error
