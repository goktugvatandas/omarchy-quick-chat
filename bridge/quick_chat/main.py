"""Quick Chat bridge entry point."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TextIO

from .adapters.registry import AdapterRegistry
from .engine import BusyError, Engine
from .history import HistoryStore
from .models import Conversation, Message
from .paths import PathSet
from .protocol import Event, MAX_REQUEST_BYTES, ProtocolError, Request
from .storage import ConfigStore
from .transports.process import ProcessTransport


def _write_event(
    output_stream: TextIO,
    event: Event,
    lock: threading.Lock | None = None,
) -> None:
    if lock is None:
        output_stream.write(event.to_json() + "\n")
        output_stream.flush()
        return
    with lock:
        output_stream.write(event.to_json() + "\n")
        output_stream.flush()


def _handle_local_request(
    request: Request,
    registry: AdapterRegistry | None = None,
) -> list[Event]:
    paths = PathSet.from_env()
    config_store = ConfigStore(paths)
    config = config_store.load()
    history_store = HistoryStore(paths, config)
    events: list[Event] = []

    if config_store.last_diagnostic is not None:
        events.append(Event("status", request.request_id, config_store.last_diagnostic))

    if request.type == "profiles":
        adapter_states = []
        if registry is not None:
            for adapter_id in registry.keys:
                try:
                    adapter = registry.get(adapter_id)
                    adapter_states.append({
                        "id": adapter_id,
                        "availability": "unknown",
                        "capabilities": asdict(adapter.capabilities),
                    })
                except KeyError:
                    adapter_states.append({
                        "id": adapter_id,
                        "availability": "unregistered",
                        "capabilities": None,
                    })
        events.append(Event("complete", request.request_id, {
            "config": config.to_dict(),
            "adapters": adapter_states,
        }))
        return events
    if request.type == "history.list":
        conversations = history_store.list()
        if history_store.last_diagnostic is not None:
            events.append(Event("status", request.request_id, history_store.last_diagnostic))
        events.append(Event("complete", request.request_id, {
            "conversations": [{
                "id": conversation.id,
                "title": conversation.title,
                "profileId": conversation.profile_id,
                "updatedAt": conversation.updated_at,
            } for conversation in conversations],
        }))
        return events
    if request.type == "history.get":
        if not request.conversation_id:
            raise ProtocolError("history.get requires conversationId")
        conversation = next(
            (
                item
                for item in history_store.list()
                if item.id == request.conversation_id
            ),
            None,
        )
        if conversation is None:
            raise ProtocolError("conversation was not found", "not_found")
        events.append(Event("complete", request.request_id, {
            "conversation": conversation.to_dict(),
        }))
        return events
    if request.type == "history.clear":
        if not request.confirm:
            raise ProtocolError("history.clear requires confirm: true", "confirmation_required")
        history_store.clear()
        events.append(Event("complete", request.request_id, {"cleared": True}))
        return events

    events.append(Event("status", request.request_id, {"status": "accepted"}))
    return events


def run(input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve JSONL until the input stream reaches EOF."""
    output_lock = threading.Lock()
    paths = PathSet.from_env()
    config = ConfigStore(paths).load()
    registry = AdapterRegistry()
    engine = Engine(registry, ProcessTransport(), config)
    workers: dict[str, threading.Thread] = {}
    _write_event(
        output_stream,
        Event("ready", "bridge", {"protocolVersion": 1}),
        output_lock,
    )

    def run_request(request: Request) -> None:
        emitted: list[Event] = []
        persisted = False

        def persist_conversation() -> None:
            nonlocal persisted
            if persisted or request.private or not emitted:
                return
            history = HistoryStore(paths, engine.config)
            existing = next((
                item
                for item in history.list()
                if item.id == request.conversation_id
            ), None)
            now = datetime.now(UTC).isoformat()
            messages = list(existing.messages) if existing else []
            messages.append(Message("user", request.prompt or "", now))
            answer = "".join(
                str(event.data.get("text", ""))
                for event in emitted
                if event.type == "text_delta"
            )
            if answer:
                messages.append(Message("assistant", answer, now))
            sessions = dict(existing.cli_sessions) if existing else {}
            for event in emitted:
                if event.type == "session" and isinstance(event.data.get("sessionId"), str):
                    profile = engine.config.profile(request.profile_id or "")
                    if profile is not None:
                        sessions[profile.adapter_id] = str(event.data["sessionId"])
            history.upsert(Conversation(
                id=request.conversation_id or request.request_id,
                title=(existing.title if existing else (request.prompt or "New chat")[:80]),
                profile_id=request.profile_id or engine.config.selected_profile_id,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                messages=tuple(messages),
                cli_sessions=sessions,
            ), private=False)
            persisted = True

        try:
            for event in engine.handle(request):
                emitted.append(event)
                if event.type in {"complete", "error"}:
                    persist_conversation()
                _write_event(output_stream, event, output_lock)
        except BusyError as error:
            _write_event(output_stream, Event("error", request.request_id, {
                "code": "busy",
                "message": str(error),
            }), output_lock)
        except (KeyError, OSError, ValueError) as error:
            _write_event(output_stream, Event("error", request.request_id, {
                "code": "request_failed",
                "message": str(error),
            }), output_lock)
        finally:
            try:
                persist_conversation()
            except (OSError, ValueError):
                pass
            workers.pop(request.request_id, None)

    def resolve_session(conversation_id: str, adapter_id: str) -> str | None:
        history = HistoryStore(paths, engine.config)
        conversation = next(
            (item for item in history.list() if item.id == conversation_id),
            None,
        )
        return conversation.cli_sessions.get(adapter_id) if conversation else None

    engine.session_resolver = resolve_session

    for line in input_stream:
        request_id = "bridge"
        try:
            if len(line.encode("utf-8")) > MAX_REQUEST_BYTES:
                raise ProtocolError(
                    "request body exceeds 1 MiB",
                    "request_too_large",
                )
            decoded = json.loads(line)
            if isinstance(decoded, dict) and isinstance(decoded.get("requestId"), str):
                request_id = decoded["requestId"] or "bridge"
            request = Request.from_dict(decoded)
            if request.type == "run":
                config = ConfigStore(paths).load()
                engine.config = config
                worker = threading.Thread(target=run_request, args=(request,), daemon=True)
                workers[request.request_id] = worker
                worker.start()
            elif request.type == "cancel":
                cancelled = engine.cancel(request.request_id)
                event = Event(
                    "status" if cancelled else "error",
                    request.request_id,
                    {"status": "cancelling"}
                    if cancelled
                    else {"code": "not_running", "message": "Request is not running."},
                )
                _write_event(output_stream, event, output_lock)
            elif request.type == "probe" and request.profile_id:
                profile = config.profile(request.profile_id)
                if profile is None:
                    raise ProtocolError("profile was not found", "profile_not_found")
                detection = registry.detect(profile.adapter_id, refresh=True)
                _write_event(
                    output_stream,
                    Event("complete", request.request_id, detection),
                    output_lock,
                )
            else:
                for event in _handle_local_request(request, registry):
                    _write_event(output_stream, event, output_lock)
        except (json.JSONDecodeError, OSError, ProtocolError, ValueError) as error:
            code = error.code if isinstance(error, ProtocolError) else "invalid_request"
            _write_event(
                output_stream,
                Event(
                    "error",
                    request_id,
                    {"code": code, "message": str(error)},
                ),
                output_lock,
            )

    for request_id, worker in list(workers.items()):
        if worker.is_alive():
            engine.cancel(request_id)
        worker.join(timeout=4)
