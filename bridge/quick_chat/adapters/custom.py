"""Typed shell-free custom command adapter."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .base import AdapterContext, AdapterEvent, Capabilities, Invocation


PLACEHOLDERS = {"{prompt}", "{cwd}", "{model}", "{session}", "{attachments}"}
SHELL_EXECUTABLES = {"sh", "bash", "zsh", "fish", "dash", "shell"}
SHELL_OPERATORS = {"|", "||", "&&", ";", ">", ">>", "<", "<<", "2>"}
BRACE_PATTERN = re.compile(r"[{}]")


def _validate_argument(argument: str, allow_placeholders: bool) -> None:
    if not isinstance(argument, str) or not argument:
        raise ValueError("custom arguments must be non-empty strings")
    if argument in SHELL_OPERATORS:
        raise ValueError("shell operators are not supported")
    if BRACE_PATTERN.search(argument):
        if not allow_placeholders or argument not in PLACEHOLDERS:
            raise ValueError("placeholders must occupy one complete argument")


class CustomAdapter:
    id = "custom"

    def __init__(
        self,
        executable: str,
        args: tuple[str, ...] = (),
        stdin: bool = False,
        read_only_args: tuple[str, ...] = (),
        output: str = "plain",
    ) -> None:
        if not isinstance(executable, str) or not executable.strip():
            raise ValueError("custom executable is required")
        if Path(executable).name.lower() in SHELL_EXECUTABLES:
            raise ValueError("shell executables are not supported")
        if any(character in executable for character in "|;&><"):
            raise ValueError("custom executable contains a shell operator")
        for argument in args:
            _validate_argument(argument, allow_placeholders=True)
        for argument in read_only_args:
            _validate_argument(argument, allow_placeholders=False)
        if not isinstance(stdin, bool):
            raise ValueError("custom stdin must be a boolean")
        if output not in {"plain", "jsonl"}:
            raise ValueError("custom output must be plain or jsonl")
        self.executable = executable
        self.args = tuple(args)
        self.stdin = stdin
        self.read_only_args = tuple(read_only_args)
        self.output = output
        self.capabilities = Capabilities(
            streaming=True,
            resume="{session}" in self.args,
            model="{model}" in self.args,
            native_images="{attachments}" in self.args,
            read_only_enforced=bool(self.read_only_args),
            relayable_approvals=False,
        )

    def detect(self) -> dict[str, object]:
        executable = Path(self.executable)
        available = executable.is_file() if executable.is_absolute() else True
        return {"available": available, "version": "custom"}

    def start(self, context: AdapterContext) -> Invocation:
        replacements = {
            "{prompt}": context.prompt,
            "{cwd}": str(context.cwd),
            "{model}": context.model or "",
            "{session}": context.session_id or "",
        }
        arguments = [self.executable]
        for argument in self.args:
            if argument == "{attachments}":
                arguments.extend(
                    attachment.path
                    for attachment in context.attachments
                    if attachment.path
                )
            else:
                arguments.append(replacements.get(argument, argument))
        arguments.extend(self.read_only_args)
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        return Invocation(
            tuple(arguments),
            context.cwd,
            environment,
            context.prompt if self.stdin else None,
        )

    def parse_event(self, event: AdapterEvent) -> list[AdapterEvent]:
        if event.type != "stdout":
            return []
        text = str(event.data.get("text", ""))
        if self.output == "plain":
            return [AdapterEvent("text_delta", {"text": text + "\n"})]
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return [AdapterEvent("text_delta", {"text": text + "\n"})]
        if not isinstance(value, dict):
            return []
        event_type = value.get("type")
        if event_type in {"text_delta", "session", "complete", "error", "tool_request"}:
            data = value.get("data", value)
            if isinstance(data, dict):
                return [AdapterEvent(str(event_type), dict(data))]
        return []
