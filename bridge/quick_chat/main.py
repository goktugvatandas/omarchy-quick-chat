"""Quick Chat bridge entry point."""

from __future__ import annotations

import json
from typing import TextIO

from .history import HistoryStore
from .paths import PathSet
from .protocol import Event, MAX_REQUEST_BYTES, ProtocolError, Request
from .storage import ConfigStore


def _write_event(output_stream: TextIO, event: Event) -> None:
    output_stream.write(event.to_json() + "\n")
    output_stream.flush()


def _handle_local_request(request: Request) -> list[Event]:
    paths = PathSet.from_env()
    config_store = ConfigStore(paths)
    config = config_store.load()
    history_store = HistoryStore(paths, config)
    events: list[Event] = []

    if config_store.last_diagnostic is not None:
        events.append(Event("status", request.request_id, config_store.last_diagnostic))

    if request.type == "profiles":
        events.append(Event("complete", request.request_id, {"config": config.to_dict()}))
        return events
    if request.type == "history.list":
        conversations = history_store.list()
        if history_store.last_diagnostic is not None:
            events.append(Event("status", request.request_id, history_store.last_diagnostic))
        events.append(Event("complete", request.request_id, {
            "conversations": [conversation.to_dict() for conversation in conversations],
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
        history_store.clear()
        events.append(Event("complete", request.request_id, {"cleared": True}))
        return events

    events.append(Event("status", request.request_id, {"status": "accepted"}))
    return events


def run(input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve JSONL until the input stream reaches EOF."""
    _write_event(
        output_stream,
        Event("ready", "bridge", {"protocolVersion": 1}),
    )

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
            for event in _handle_local_request(request):
                _write_event(output_stream, event)
        except (json.JSONDecodeError, OSError, ProtocolError, ValueError) as error:
            code = error.code if isinstance(error, ProtocolError) else "invalid_request"
            _write_event(
                output_stream,
                Event(
                    "error",
                    request_id,
                    {"code": code, "message": str(error)},
                ),
            )
