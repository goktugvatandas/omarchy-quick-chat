"""Safe model-catalog discovery through each CLI's read-only interface."""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import time
from pathlib import Path
from typing import Iterable, Mapping

from .adapters.base import ModelOption


ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-\[\]=,]*$")
IGNORED_TOKENS = frozenset({
    "available",
    "default",
    "description",
    "id",
    "model",
    "models",
    "name",
    "provider",
    "thinking",
    "tip:",
})
MAX_OUTPUT_BYTES = 1024 * 1024


class ModelDiscoveryError(RuntimeError):
    """A CLI could not provide a model catalog without exposing raw output."""


def _clean(value: str) -> str:
    return ANSI_PATTERN.sub("", value).strip()


def _safe_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["NO_COLOR"] = "1"
    environment["TERM"] = "dumb"
    return environment


def _run(
    argv: tuple[str, ...],
    cwd: Path | None,
    input_text: str | None = None,
    timeout: float = 12,
) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=_safe_environment(),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError as error:
        raise ModelDiscoveryError(f"{argv[0]} is not installed.") from error
    except subprocess.TimeoutExpired as error:
        raise ModelDiscoveryError(f"{argv[0]} model discovery timed out.") from error

    output = result.stdout or ""
    if len(output.encode("utf-8", errors="replace")) > MAX_OUTPUT_BYTES:
        raise ModelDiscoveryError(f"{argv[0]} returned an oversized model catalog.")
    if result.returncode != 0:
        diagnostic = ((result.stderr or "") + "\n" + output).lower()
        if any(word in diagnostic for word in ("auth", "login", "unauthorized", "sign in")):
            raise ModelDiscoveryError(f"Authenticate {argv[0]} before discovering models.")
        raise ModelDiscoveryError(f"{argv[0]} could not list models.")
    return output


def _exchange_json_response(
    argv: tuple[str, ...],
    messages: tuple[Mapping[str, object], ...],
    response_id: int,
    cwd: Path | None,
    timeout: float,
) -> dict[str, object]:
    """Keep a JSONL server alive until its requested response is received."""
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=_safe_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            shell=False,
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise ModelDiscoveryError(f"{argv[0]} is not installed.") from error

    if process.stdin is None or process.stdout is None:
        process.kill()
        raise ModelDiscoveryError(f"{argv[0]} could not start model discovery.")

    selector = selectors.DefaultSelector()
    output_bytes = 0
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        for message in messages:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready = selector.select(remaining)
            if not ready:
                break
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                continue
            output_bytes += len(line.encode("utf-8", errors="replace"))
            if output_bytes > MAX_OUTPUT_BYTES:
                raise ModelDiscoveryError(
                    f"{argv[0]} returned an oversized model catalog."
                )
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("id") == response_id:
                return value
        raise ModelDiscoveryError(f"{argv[0]} returned no model catalog response.")
    except (BrokenPipeError, OSError) as error:
        raise ModelDiscoveryError(f"{argv[0]} could not list models.") from error
    finally:
        selector.close()
        try:
            process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        process.stdout.close()


def _identifier(value: str) -> str | None:
    candidate = value.strip().strip("*•-│┃┆|`'")
    candidate = candidate.rstrip("*,")
    if not candidate or not MODEL_ID_PATTERN.fullmatch(candidate):
        return None
    if candidate.lower() in IGNORED_TOKENS:
        return None
    return candidate


def _dedupe(models: Iterable[ModelOption]) -> tuple[ModelOption, ...]:
    result: list[ModelOption] = []
    seen: set[str] = set()
    for model in models:
        if model.id in seen:
            continue
        seen.add(model.id)
        result.append(model)
    return tuple(result)


def discover_command_models(
    argv: tuple[str, ...],
    style: str,
    cwd: Path | None = None,
) -> tuple[ModelOption, ...]:
    output = _run(argv, cwd)
    models: list[ModelOption] = []

    for raw_line in output.splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        columns = [part.strip() for part in re.split(r"\t+|\s{2,}", line) if part.strip()]
        words = line.split()

        if style == "pi":
            if len(columns) >= 2:
                provider = _identifier(columns[0])
                model = _identifier(columns[1])
            elif len(words) >= 2:
                provider = _identifier(words[0])
                model = _identifier(words[1])
            else:
                provider = model = None
            if provider and model:
                identifier = model if "/" in model else f"{provider}/{model}"
                description = " · ".join(columns[2:]) if len(columns) > 2 else provider
                models.append(ModelOption(identifier, identifier, description))
            continue

        display_label = ""
        if " - " in line:
            first, display_label = line.split(" - ", 1)
        else:
            first = columns[0] if columns else (words[0] if words else "")
        identifier = _identifier(first)
        if identifier is None and words:
            first = words[0]
            identifier = _identifier(first)
        if identifier is None:
            continue
        if style == "opencode" and "/" not in identifier:
            continue
        description = " · ".join(columns[1:]) if len(columns) > 1 else ""
        if display_label:
            models.append(ModelOption(identifier, display_label, identifier))
        else:
            models.append(ModelOption(identifier, identifier, description))

    discovered = _dedupe(models)
    if not discovered:
        raise ModelDiscoveryError(f"{argv[0]} returned no selectable models.")
    return discovered


def discover_codex_models(cwd: Path | None = None) -> tuple[ModelOption, ...]:
    messages = (
        {
            "method": "initialize",
            "id": 1,
            "params": {
                "clientInfo": {
                    "name": "omarchy_quick_chat",
                    "title": "Omarchy Quick Chat",
                    "version": "1",
                }
            },
        },
        {"method": "initialized", "params": {}},
        {
            "method": "model/list",
            "id": 2,
            "params": {"cursor": None, "limit": 200, "includeHidden": False},
        },
    )
    response = _exchange_json_response(
        ("codex", "app-server", "--stdio"),
        messages,
        response_id=2,
        cwd=cwd,
        timeout=20,
    )
    if "error" in response:
        raise ModelDiscoveryError("Codex could not list models.")

    result = response.get("result")
    rows = result.get("data") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        raise ModelDiscoveryError("Codex returned an invalid model catalog.")

    models: list[ModelOption] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("hidden") is True:
            continue
        identifier = row.get("model") or row.get("id")
        if not isinstance(identifier, str) or not _identifier(identifier):
            continue
        label = row.get("displayName")
        description = row.get("description")
        models.append(ModelOption(
            identifier,
            label if isinstance(label, str) and label else identifier,
            description if isinstance(description, str) else "",
        ))

    discovered = _dedupe(models)
    if not discovered:
        raise ModelDiscoveryError("Codex returned no selectable models.")
    return discovered
