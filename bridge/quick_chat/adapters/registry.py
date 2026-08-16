"""Adapter lookup and bridge-lifetime capability probe cache."""

from __future__ import annotations

from typing import Mapping

from .base import Adapter


ADAPTER_IDS = ("codex", "claude", "opencode", "grok", "cursor", "pi", "custom")


class AdapterRegistry:
    def __init__(self, adapters: Mapping[str, Adapter] | None = None) -> None:
        self._adapters: dict[str, Adapter | None] = {
            adapter_id: None for adapter_id in ADAPTER_IDS
        }
        self._probe_cache: dict[str, dict[str, object]] = {}
        self._acp_transports = {}
        self._acp_failed: set[tuple[str, str | None]] = set()
        if adapters is None:
            from .claude import ClaudeAdapter
            from .codex import CodexAdapter
            from .cursor import CursorAdapter
            from .grok import GrokAdapter
            from .opencode import OpenCodeAdapter
            from .pi import PiAdapter

            adapters = {
                "codex": CodexAdapter(),
                "claude": ClaudeAdapter(),
                "opencode": OpenCodeAdapter(),
                "grok": GrokAdapter(),
                "cursor": CursorAdapter(),
                "pi": PiAdapter(),
            }
        if adapters:
            for adapter_id, adapter in adapters.items():
                self.register(adapter_id, adapter)

    @property
    def keys(self) -> tuple[str, ...]:
        return ADAPTER_IDS

    def register(self, adapter_id: str, adapter: Adapter) -> None:
        if adapter_id not in self._adapters:
            raise KeyError(f"unknown adapter: {adapter_id}")
        self._adapters[adapter_id] = adapter
        self.invalidate(adapter_id)

    def get(self, adapter_id: str) -> Adapter:
        if adapter_id not in self._adapters:
            raise KeyError(f"unknown adapter: {adapter_id}")
        adapter = self._adapters[adapter_id]
        if adapter is None:
            raise KeyError(f"adapter is not registered: {adapter_id}")
        return adapter

    def detect(self, adapter_id: str, refresh: bool = False) -> dict[str, object]:
        if refresh:
            self.invalidate(adapter_id)
        if adapter_id not in self._probe_cache:
            self._probe_cache[adapter_id] = self.get(adapter_id).detect()
        return dict(self._probe_cache[adapter_id])

    def invalidate(self, adapter_id: str) -> None:
        self._probe_cache.pop(adapter_id, None)

    def acp_transport(
        self,
        adapter_id: str,
        model: str | None,
        argv: tuple[str, ...],
    ):
        from ..transports.acp import AcpTransport

        key = (adapter_id, model)
        if key in self._acp_failed:
            return None
        if key not in self._acp_transports:
            self._acp_transports[key] = AcpTransport(argv)
        return self._acp_transports[key]

    def mark_acp_failed(self, adapter_id: str, model: str | None) -> None:
        key = (adapter_id, model)
        transport = self._acp_transports.pop(key, None)
        if transport is not None:
            transport.close()
        self._acp_failed.add(key)

    def close(self) -> None:
        for transport in self._acp_transports.values():
            transport.close()
        self._acp_transports.clear()
