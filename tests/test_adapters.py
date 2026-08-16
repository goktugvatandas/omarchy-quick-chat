import os
import tempfile
import unittest
from pathlib import Path

from bridge.quick_chat.adapters.base import AdapterContext, AdapterEvent
from bridge.quick_chat.adapters.claude import ClaudeAdapter
from bridge.quick_chat.adapters.codex import CodexAdapter
from bridge.quick_chat.protocol import Attachment


FIXTURES = Path(__file__).parent / "fixtures"


def context(
    prompt="explain",
    model=None,
    session_id=None,
    attachments=(),
    system_instructions="",
):
    return AdapterContext(
        prompt=prompt,
        model=model,
        cwd=Path.home(),
        attachments=attachments,
        session_id=session_id,
        system_instructions=system_instructions,
    )


def adjacent_pairs(values):
    return set(zip(values, values[1:]))


class CodexAdapterTests(unittest.TestCase):
    def test_codex_is_read_only_and_accepts_prompt_on_stdin(self):
        call = CodexAdapter().start(context(prompt="explain", model="gpt-5"))
        self.assertEqual(call.argv[:4], ("codex", "exec", "--json", "--sandbox"))
        self.assertIn("read-only", call.argv)
        self.assertNotIn("--full-auto", call.argv)
        self.assertEqual(call.stdin_text, "explain")
        self.assertIn(("--model", "gpt-5"), adjacent_pairs(call.argv))

    def test_codex_resume_and_images_are_individual_arguments(self):
        with tempfile.TemporaryDirectory() as runtime:
            image = Path(runtime) / "capture.png"
            image.touch()
            attachment = Attachment("one", "image", str(image), None, "image/png")
            call = CodexAdapter().start(context(
                session_id="thread-1",
                attachments=(attachment,),
            ))
        self.assertIn(("resume", "thread-1"), adjacent_pairs(call.argv))
        self.assertIn(("--image", str(image)), adjacent_pairs(call.argv))

    def test_codex_fixture_normalizes_session_text_and_completion(self):
        adapter = CodexAdapter()
        events = []
        for line in (FIXTURES / "codex-stream.jsonl").read_text().splitlines():
            events.extend(adapter.parse_event(AdapterEvent("stdout", {"text": line})))
        self.assertEqual([event.type for event in events], [
            "session",
            "text_delta",
            "complete",
        ])
        self.assertEqual(events[0].data["sessionId"], "thread-codex-1")

    def test_codex_parse_failure_degrades_without_weakening_read_only(self):
        adapter = CodexAdapter()
        events = adapter.parse_event(AdapterEvent("stdout", {"text": "plain output"}))
        self.assertEqual(events[0].type, "text_delta")
        self.assertFalse(adapter.capabilities.resume)
        call = adapter.start(context())
        self.assertIn("read-only", call.argv)


class ClaudeAdapterTests(unittest.TestCase):
    def test_claude_uses_plan_mode_and_disallows_mutation_tools(self):
        call = ClaudeAdapter().start(context(prompt="explain"))
        self.assertIn(("--permission-mode", "plan"), adjacent_pairs(call.argv))
        for tool in ("Bash", "Edit", "Write", "NotebookEdit"):
            self.assertIn(tool, call.argv)
        self.assertNotIn("--dangerously-skip-permissions", call.argv)
        self.assertNotIn("--allowedTools", call.argv)

    def test_claude_resume_model_and_system_instructions(self):
        call = ClaudeAdapter().start(context(
            model="sonnet",
            session_id="session-1",
            system_instructions="Be concise",
        ))
        pairs = adjacent_pairs(call.argv)
        self.assertIn(("--model", "sonnet"), pairs)
        self.assertIn(("--resume", "session-1"), pairs)
        self.assertIn(("--append-system-prompt", "Be concise"), pairs)

    def test_claude_fixture_normalizes_session_text_and_completion(self):
        adapter = ClaudeAdapter()
        events = []
        for line in (FIXTURES / "claude-stream.jsonl").read_text().splitlines():
            events.extend(adapter.parse_event(AdapterEvent("stdout", {"text": line})))
        self.assertEqual([event.type for event in events], [
            "session",
            "text_delta",
            "complete",
        ])
        self.assertFalse(adapter.capabilities.native_images)


if __name__ == "__main__":
    unittest.main()
