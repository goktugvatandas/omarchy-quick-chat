"""Quick Chat bridge entry point."""

from __future__ import annotations

import json
from typing import TextIO

from .protocol import Event, MAX_REQUEST_BYTES, ProtocolError, Request


def _write_event(output_stream: TextIO, event: Event) -> None:
    output_stream.write(event.to_json() + "\n")
    output_stream.flush()


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
            _write_event(
                output_stream,
                Event("status", request.request_id, {"status": "accepted"}),
            )
        except (json.JSONDecodeError, ProtocolError) as error:
            code = error.code if isinstance(error, ProtocolError) else "invalid_request"
            _write_event(
                output_stream,
                Event(
                    "error",
                    request_id,
                    {"code": code, "message": str(error)},
                ),
            )
