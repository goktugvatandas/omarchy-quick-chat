"""Terminal output normalization and bounded diagnostics."""

import re


DIAGNOSTIC_LIMIT = 256 * 1024
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


def bounded_diagnostic(chunks: list[str], limit: int = DIAGNOSTIC_LIMIT) -> str:
    encoded = "".join(chunks).encode("utf-8", errors="replace")[:limit]
    return strip_terminal_controls(encoded.decode("utf-8", errors="replace"))
