"""Terminal and wire-data normalization with hard memory boundaries."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import TextIO


DIAGNOSTIC_LIMIT = 256 * 1024
PROCESS_LINE_LIMIT = 64 * 1024
RESPONSE_TEXT_LIMIT = 256 * 1024
HISTORY_MESSAGE_LIMIT = 24
HISTORY_MESSAGE_BYTES = 32 * 1024
HISTORY_CONVERSATION_LIMIT = 512
HISTORY_FILE_LIMIT = 32 * 1024 * 1024
WIRE_STRING_LIMIT = 32 * 1024
WIRE_COLLECTION_LIMIT = 128
EVENT_COUNT_LIMIT = 1024
TRUNCATION_MARKER = "\n[Output truncated by Quick Chat.]"
ANSI_PATTERN = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])"
)


def strip_terminal_controls(value: str) -> str:
    value = ANSI_PATTERN.sub("", value)
    return "".join(
        character
        for character in value
        if character in "\t\n" or (ord(character) >= 0x20 and ord(character) != 0x7F)
    )


def truncate_text(
    value: object,
    limit: int,
    marker: str = TRUNCATION_MARKER,
) -> str:
    prefix, truncated, _ = bounded_text_prefix(value, limit)
    if not truncated:
        return prefix
    marker_bytes = marker.encode("utf-8")
    if len(marker_bytes) >= limit:
        return marker_bytes[:limit].decode("utf-8", errors="ignore")
    prefix, _, _ = bounded_text_prefix(value, limit - len(marker_bytes))
    return prefix + marker


def bounded_text_prefix(value: object, limit: int) -> tuple[str, bool, int]:
    """Return a valid UTF-8 prefix, truncation flag, and retained byte count."""
    text = strip_terminal_controls(str(value or ""))
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False, len(encoded)
    prefix = encoded[:limit].decode("utf-8", errors="ignore")
    retained = len(prefix.encode("utf-8"))
    return prefix, True, retained


def iter_bounded_records(
    stream: TextIO,
    limit: int,
) -> Iterator[tuple[str, bool]]:
    """Yield one retained UTF-8 prefix per physical line and flag overflow."""
    chunk_characters = 16 * 1024
    while True:
        parts: list[str] = []
        retained_bytes = 0
        saw_input = False
        oversized = False
        while True:
            chunk = stream.readline(chunk_characters)
            if not chunk:
                if not saw_input:
                    return
                break
            saw_input = True
            if not oversized:
                encoded = chunk.encode("utf-8", errors="replace")
                remaining = limit - retained_bytes
                if len(encoded) <= remaining:
                    parts.append(chunk)
                    retained_bytes += len(encoded)
                else:
                    prefix = encoded[:remaining].decode("utf-8", errors="ignore")
                    parts.append(prefix)
                    retained_bytes += len(prefix.encode("utf-8"))
                    oversized = True
            if chunk.endswith("\n"):
                break
        yield "".join(parts), oversized


def iter_bounded_lines(
    stream: TextIO,
    limit: int = PROCESS_LINE_LIMIT,
) -> Iterator[str]:
    """Yield complete lines without retaining more than the byte limit."""
    marker_bytes = len(TRUNCATION_MARKER.encode("utf-8"))
    for line, oversized in iter_bounded_records(stream, limit):
        if not oversized:
            yield line
            continue
        prefix, _, _ = bounded_text_prefix(
            line.rstrip("\r\n"),
            max(0, limit - marker_bytes),
        )
        yield prefix + TRUNCATION_MARKER


def bounded_wire_value(value: object, depth: int = 0) -> object:
    """Copy untrusted wire metadata into a small JSON-compatible shape."""
    if depth >= 6:
        return "[nested data omitted]"
    if isinstance(value, str):
        return truncate_text(value, WIRE_STRING_LIMIT)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= WIRE_COLLECTION_LIMIT:
                break
            result[truncate_text(key, 256, "")] = bounded_wire_value(item, depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = list(value[:WIRE_COLLECTION_LIMIT])
        return [bounded_wire_value(item, depth + 1) for item in items]
    return truncate_text(value, WIRE_STRING_LIMIT)


def bounded_diagnostic(chunks: list[str], limit: int = DIAGNOSTIC_LIMIT) -> str:
    encoded = "".join(chunks).encode("utf-8", errors="replace")[:limit]
    return strip_terminal_controls(encoded.decode("utf-8", errors="replace"))
