"""Shared validation helpers for bridge domain records."""

from typing import Any


def require_identifier(name: str, value: Any) -> str:
    """Return a non-empty identifier-like wire value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def require_optional_string(name: str, value: Any) -> str | None:
    """Return an optional string while rejecting implicit coercion."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string or null")
    return value
