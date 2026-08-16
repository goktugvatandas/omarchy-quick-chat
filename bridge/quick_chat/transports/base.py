"""Transport protocol."""

from dataclasses import dataclass
from typing import Callable, Protocol

from ..adapters.base import AdapterEvent, Invocation


@dataclass(frozen=True)
class RunResult:
    exit_code: int | None
    stderr: str
    cancelled: bool
    timed_out: bool


class Transport(Protocol):
    def run(
        self,
        request_id: str,
        invocation: Invocation,
        emit: Callable[[AdapterEvent], None],
    ) -> RunResult: ...

    def cancel(self, request_id: str) -> bool: ...
