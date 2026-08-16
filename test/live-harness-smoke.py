#!/usr/bin/env python3
"""Opt-in, real-provider smoke matrix for the six built-in CLI adapters."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge.quick_chat.adapters.base import AdapterContext, AdapterEvent, ModelOption
from bridge.quick_chat.adapters.pi import PiAdapter
from bridge.quick_chat.adapters.process_base import VERSION_PATTERN
from bridge.quick_chat.adapters.registry import AdapterRegistry
from bridge.quick_chat.model_discovery import ModelDiscoveryError
from bridge.quick_chat.paths import PathSet
from bridge.quick_chat.sanitize import strip_terminal_controls
from bridge.quick_chat.transports.process import ProcessTransport


ADAPTER_IDS = ("codex", "claude", "opencode", "grok", "cursor", "pi")
PROMPT = "Reply with exactly QUICK_CHAT_OK and nothing else."
AUTH_TIMEOUT_SECONDS = 20
REQUEST_TIMEOUT_SECONDS = 180
MAX_ANSWER_CHARS = 256
MAX_VERSION_CHARS = 160
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def auth_probe(adapter_id: str, model: str | None) -> tuple[str, ...] | None:
    """Return a non-interactive auth check, or None for catalog-backed auth."""
    probes: dict[str, tuple[str, ...] | None] = {
        "codex": ("codex", "login", "status"),
        "claude": ("claude", "auth", "status"),
        "opencode": None,
        "grok": None,
        "cursor": ("cursor-agent", "status"),
        "pi": (
            "pi",
            "auth",
            "check",
            "--model",
            model or "",
            "--json",
            "--no-refresh",
        ),
    }
    if adapter_id not in probes:
        raise KeyError(f"unknown live smoke adapter: {adapter_id}")
    probe = probes[adapter_id]
    if probe is not None and any(not argument for argument in probe):
        return None
    return probe


def _row(adapter_id: str) -> dict[str, Any]:
    return {
        "id": adapter_id,
        "version": None,
        "auth": False,
        "model": None,
        "efforts": [],
        "answer": "",
        "completed": False,
        "error": None,
    }


def _safe_text(value: object, limit: int) -> str:
    text = strip_terminal_controls(str(value))
    return _CONTROL_PATTERN.sub("", text)[:limit]


def _configured_models() -> dict[str, str]:
    """Read configured model ids without mutating or migrating user config."""
    try:
        config_path = PathSet.from_env().config_file
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    profiles = value.get("profiles") if isinstance(value, dict) else None
    if not isinstance(profiles, list):
        return {}
    configured: dict[str, str] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        adapter_id = profile.get("adapterId")
        model = profile.get("model")
        if (
            isinstance(adapter_id, str)
            and adapter_id in ADAPTER_IDS
            and adapter_id not in configured
            and isinstance(model, str)
            and model
        ):
            configured[adapter_id] = model
    return configured


def _select_model(
    models: tuple[ModelOption, ...],
    configured_model: str | None,
) -> ModelOption | None:
    if configured_model:
        selected = next(
            (option for option in models if option.id == configured_model),
            None,
        )
        if selected is not None:
            return selected
    return next((option for option in models if option.is_default), None) or (
        models[0] if models else None
    )


def _auth_ok(command: tuple[str, ...], cwd: Path) -> bool:
    environment = os.environ.copy()
    environment["NO_COLOR"] = "1"
    environment["TERM"] = "dumb"
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=AUTH_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _directory_entries(directory: Path) -> frozenset[str]:
    return frozenset(
        str(path.relative_to(directory)) for path in directory.rglob("*")
    )


def _model_efforts(adapter: object, model: ModelOption, cwd: Path) -> list[str]:
    if model.efforts is not None:
        return [option.id for option in model.efforts]
    discover = getattr(adapter, "effort_options", None)
    if not callable(discover):
        return []
    try:
        return [option.id for option in discover(cwd)]
    except (ModelDiscoveryError, OSError, subprocess.SubprocessError):
        return []


def _run_adapter(
    adapter_id: str,
    registry: AdapterRegistry,
    configured_model: str | None,
) -> dict[str, Any]:
    row = _row(adapter_id)
    adapter = registry.get(adapter_id)

    try:
        detection = adapter.detect()
    except (OSError, subprocess.SubprocessError):
        row["error"] = "not_installed"
        return row
    version = detection.get("version")
    if detection.get("available") is not True:
        row["error"] = "not_installed"
        return row
    if not isinstance(version, str) or VERSION_PATTERN.search(version) is None:
        row["error"] = "version_probe_failed"
        return row
    row["version"] = _safe_text(version, MAX_VERSION_CHARS)

    with tempfile.TemporaryDirectory(prefix=f"quick-chat-{adapter_id}-") as root:
        root_path = Path(root)
        cwd = root_path / "work"
        runtime = root_path / "runtime"
        cwd.mkdir(mode=0o700)
        runtime.mkdir(mode=0o700)
        before = _directory_entries(cwd)

        try:
            models = tuple(adapter.discover_models(cwd))
        except (ModelDiscoveryError, OSError, subprocess.SubprocessError):
            row["error"] = (
                "authentication_required"
                if adapter_id in {"opencode", "grok"}
                else "model_discovery_failed"
            )
            return row
        model = _select_model(models, configured_model)
        if model is None:
            row["error"] = "model_discovery_failed"
            return row
        row["model"] = model.id
        row["efforts"] = _model_efforts(adapter, model, cwd)

        probe = auth_probe(adapter_id, model.id)
        row["auth"] = probe is None or _auth_ok(probe, cwd)
        if not row["auth"]:
            row["error"] = "authentication_required"
            return row

        previous_runtime = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = str(runtime)
        try:
            invocation = adapter.start(AdapterContext(
                prompt=PROMPT,
                model=model.id,
                cwd=cwd,
                attachments=(),
                private=True,
                thinking_effort=None,
            ))
        except (OSError, TypeError, ValueError):
            row["error"] = "invocation_failed"
            return row
        finally:
            if previous_runtime is None:
                os.environ.pop("XDG_RUNTIME_DIR", None)
            else:
                os.environ["XDG_RUNTIME_DIR"] = previous_runtime

        text_parts: list[str] = []
        provider_error = False

        def collect(raw_event: AdapterEvent) -> None:
            nonlocal provider_error
            for event in adapter.parse_event(raw_event):
                if event.type == "text_delta":
                    text = event.data.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
                elif event.type == "complete":
                    row["completed"] = True
                elif event.type == "error":
                    provider_error = True

        try:
            result = ProcessTransport(
                timeout_seconds=REQUEST_TIMEOUT_SECONDS
            ).run(
                f"live-{adapter_id}-{uuid.uuid4()}",
                invocation,
                collect,
            )
        except (FileNotFoundError, OSError, RuntimeError):
            row["error"] = "process_start_failed"
            return row
        finally:
            cleanup = getattr(adapter, "cleanup_private_session", None)
            if callable(cleanup):
                cleanup()

        answer = "".join(text_parts)
        row["answer"] = _safe_text(answer, MAX_ANSWER_CHARS)
        created = _directory_entries(cwd) - before
        if created:
            row["error"] = "filesystem_write"
        elif result.timed_out:
            row["error"] = "timeout"
        elif result.cancelled:
            row["error"] = "cancelled"
        elif result.exit_code != 0:
            row["error"] = "nonzero_exit"
        elif provider_error:
            row["error"] = "provider_error"
        elif "QUICK_CHAT_OK" not in answer:
            row["error"] = "missing_token"
        elif not row["completed"]:
            row["error"] = "missing_completion"
        return row


def _successful(row: dict[str, Any]) -> bool:
    return (
        row["auth"] is True
        and isinstance(row["model"], str)
        and bool(row["model"])
        and "QUICK_CHAT_OK" in row["answer"]
        and row["completed"] is True
        and row["error"] is None
    )


def main() -> int:
    if os.environ.get("QUICK_CHAT_LIVE_HARNESSES") != "1":
        print(
            "Live harness smoke matrix disabled; set "
            "QUICK_CHAT_LIVE_HARNESSES=1 to make six real provider requests."
        )
        return 0

    configured = _configured_models()
    registry = AdapterRegistry()
    rows: list[dict[str, Any]] = []
    try:
        for adapter_id in ADAPTER_IDS:
            try:
                row = _run_adapter(adapter_id, registry, configured.get(adapter_id))
            except Exception:
                row = _row(adapter_id)
                row["error"] = "runner_error"
            rows.append(row)
            print(json.dumps(row, ensure_ascii=True, separators=(",", ":")), flush=True)
    finally:
        registry.close()
    return 0 if all(_successful(row) for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
