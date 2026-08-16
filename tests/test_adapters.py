import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bridge.quick_chat.adapters.base import AdapterContext, AdapterEvent
from bridge.quick_chat.adapters.claude import ClaudeAdapter
from bridge.quick_chat.adapters.codex import CodexAdapter
from bridge.quick_chat.adapters.custom import CustomAdapter
from bridge.quick_chat.adapters.cursor import CursorAdapter
from bridge.quick_chat.adapters.grok import GrokAdapter
from bridge.quick_chat.adapters.opencode import OpenCodeAdapter
from bridge.quick_chat.adapters.pi import PiAdapter
from bridge.quick_chat.protocol import Attachment


FIXTURES = Path(__file__).parent / "fixtures"


def context(
    prompt="explain",
    model=None,
    session_id=None,
    attachments=(),
    system_instructions="",
    private=False,
):
    return AdapterContext(
        prompt=prompt,
        model=model,
        cwd=Path.home(),
        attachments=attachments,
        session_id=session_id,
        system_instructions=system_instructions,
        private=private,
    )


def adjacent_pairs(values):
    return set(zip(values, values[1:]))


class CodexAdapterTests(unittest.TestCase):
    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_codex_discovers_models_from_app_server(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout=(
                '{"id":1,"result":{}}\n'
                '{"id":2,"result":{"data":['
                '{"model":"gpt-5.6-sol","displayName":"GPT-5.6 Sol",'
                '"description":"Fast coding model","hidden":false},'
                '{"model":"hidden","displayName":"Hidden","hidden":true}'
                ']}}\n'
            ),
            stderr="",
        )
        models = CodexAdapter().discover_models(Path.home())
        self.assertEqual([model.id for model in models], ["gpt-5.6-sol"])
        self.assertEqual(models[0].label, "GPT-5.6 Sol")
        self.assertEqual(run.call_args.args[0], ("codex", "app-server", "--stdio"))
        self.assertIn('"method":"model/list"', run.call_args.kwargs["input"])

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
    def test_claude_exposes_supported_cli_model_aliases(self):
        models = ClaudeAdapter().discover_models(Path.home())
        self.assertEqual([model.id for model in models], ["sonnet", "opus", "haiku"])

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


class RemainingAdapterTests(unittest.TestCase):
    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_cli_catalog_commands_are_parsed_into_selectable_models(self, run):
        fixtures = (
            (OpenCodeAdapter(), ("opencode", "models"), "anthropic/claude-sonnet-4\nopenai/gpt-5\n", ["anthropic/claude-sonnet-4", "openai/gpt-5"]),
            (
                CursorAdapter(),
                ("cursor-agent", "models"),
                "Available models\nauto - Auto (current, default)\n"
                "gpt-5 - GPT-5\nsonnet-4-thinking - Sonnet 4 Thinking\n"
                "Tip: use --model <id> to switch.\n",
                ["auto", "gpt-5", "sonnet-4-thinking"],
            ),
            (PiAdapter(), ("pi", "--list-models"), "anthropic  claude-sonnet-4\nopenai  gpt-5\n", ["anthropic/claude-sonnet-4", "openai/gpt-5"]),
            (GrokAdapter(), ("grok", "--no-auto-update", "models"), "grok-build\ngrok-4.3\n", ["grok-build", "grok-4.3"]),
        )
        for adapter, argv, stdout, expected in fixtures:
            with self.subTest(adapter=adapter.id):
                run.reset_mock()
                run.return_value = Mock(returncode=0, stdout=stdout, stderr="")
                models = adapter.discover_models(Path.home())
                self.assertEqual([model.id for model in models], expected)
                self.assertEqual(run.call_args.args[0], argv)

        run.return_value = Mock(
            returncode=0,
            stdout="auto - Auto (current, default)\ngpt-5 - GPT-5\n",
            stderr="",
        )
        cursor_models = CursorAdapter().discover_models(Path.home())
        self.assertEqual(cursor_models[1].label, "GPT-5")
        self.assertEqual(cursor_models[1].description, "gpt-5")

    def test_process_adapters_never_auto_approve(self):
        calls = [
            OpenCodeAdapter().start(context()),
            GrokAdapter().start(context()),
            CursorAdapter().start(context()),
            PiAdapter().start(context()),
        ]
        forbidden = {"--auto", "--always-approve", "--force", "--yolo"}
        for call in calls:
            self.assertTrue(forbidden.isdisjoint(call.argv), call.argv)

    def test_opencode_supports_model_session_and_native_files(self):
        attachment = Attachment("one", "image", "/tmp/image.png", None, "image/png")
        call = OpenCodeAdapter().start(context(
            model="provider/model",
            session_id="session-1",
            attachments=(attachment,),
        ))
        pairs = adjacent_pairs(call.argv)
        self.assertEqual(call.argv[:4], ("opencode", "run", "--format", "json"))
        self.assertIn(("--session", "session-1"), pairs)
        self.assertIn(("--file", "/tmp/image.png"), pairs)
        self.assertNotIn("--auto", call.argv)

    def test_grok_uses_only_read_tools(self):
        call = GrokAdapter().start(context())
        self.assertIn("read_file,grep,list_dir", call.argv)
        self.assertIn(("--disallowed-tools", "Agent"), adjacent_pairs(call.argv))
        self.assertNotIn("--always-approve", call.argv)

    def test_cursor_uses_resume_without_force(self):
        call = CursorAdapter().start(context(session_id="cursor-session"))
        self.assertIn("--resume=cursor-session", call.argv)
        self.assertNotIn("--force", call.argv)

    def test_pi_uses_only_read_tools_and_state_session(self):
        with tempfile.TemporaryDirectory() as state:
            call = PiAdapter(state_dir=Path(state)).start(context(model="openai/gpt-5"))
        self.assertIn("read,grep,find,ls", call.argv)
        self.assertIn(("--provider", "openai"), adjacent_pairs(call.argv))
        self.assertIn(("--model", "gpt-5"), adjacent_pairs(call.argv))
        session_path = call.argv[call.argv.index("--session") + 1]
        self.assertTrue(session_path.startswith(state))
        for forbidden in ("bash", "edit", "write"):
            self.assertNotIn(forbidden, call.argv)

    def test_pi_private_session_is_runtime_scoped_and_cleaned(self):
        with tempfile.TemporaryDirectory() as runtime:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
                adapter = PiAdapter()
                call = adapter.start(context(private=True))
                session_path = Path(call.argv[call.argv.index("--session") + 1])
                session_path.touch()
                self.assertTrue(session_path.is_relative_to(
                    Path(runtime) / "omarchy-quick-chat"
                ))
                adapter.cleanup_private_session()
                self.assertFalse(session_path.exists())

    def test_four_adapter_fixtures_normalize_streams(self):
        fixtures = (
            (OpenCodeAdapter(), "opencode-stream.jsonl"),
            (GrokAdapter(), "grok-stream.jsonl"),
            (CursorAdapter(), "cursor-stream.jsonl"),
            (PiAdapter(), "pi-stream.jsonl"),
        )
        for adapter, fixture in fixtures:
            with self.subTest(adapter=adapter.id):
                events = []
                for line in (FIXTURES / fixture).read_text().splitlines():
                    events.extend(adapter.parse_event(AdapterEvent("stdout", {"text": line})))
                self.assertEqual(
                    [event.type for event in events],
                    ["session", "text_delta", "complete"],
                )


class CustomAdapterTests(unittest.TestCase):
    def test_custom_arguments_are_individual_values(self):
        adapter = CustomAdapter(
            executable="ask",
            args=("--cwd", "{cwd}", "{prompt}"),
        )
        call = adapter.start(context(prompt="$(touch nope)"))
        self.assertEqual(call.argv, (
            "ask",
            "--cwd",
            str(Path.home()),
            "$(touch nope)",
        ))

    def test_attachment_placeholder_expands_as_repeated_values(self):
        adapter = CustomAdapter("ask", args=("{attachments}", "{prompt}"))
        attachments = (
            Attachment("one", "image", "/tmp/one.png", None, "image/png"),
            Attachment("two", "image", "/tmp/two.png", None, "image/png"),
        )
        call = adapter.start(context(attachments=attachments))
        self.assertEqual(call.argv[1:3], ("/tmp/one.png", "/tmp/two.png"))

    def test_partial_unknown_and_shell_templates_are_rejected(self):
        invalid = (
            ("ask", ("--prompt={prompt}",)),
            ("ask", ("{unknown}",)),
            ("bash", ("-c", "{prompt}")),
            ("ask", ("|", "other")),
        )
        for executable, arguments in invalid:
            with self.subTest(executable=executable, arguments=arguments):
                with self.assertRaises(ValueError):
                    CustomAdapter(executable, args=arguments)

    def test_read_only_arguments_are_appended_individually(self):
        adapter = CustomAdapter("ask", args=("{prompt}",), read_only_args=("--safe",))
        call = adapter.start(context())
        self.assertEqual(call.argv[-1], "--safe")
        self.assertTrue(adapter.capabilities.read_only_enforced)


if __name__ == "__main__":
    unittest.main()
