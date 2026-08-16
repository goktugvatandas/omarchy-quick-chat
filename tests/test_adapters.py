import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bridge.quick_chat.adapters.base import AdapterContext, AdapterEvent, ModelOption
from bridge.quick_chat.adapters.claude import ClaudeAdapter
from bridge.quick_chat.adapters.codex import CodexAdapter
from bridge.quick_chat.adapters.custom import CustomAdapter
from bridge.quick_chat.adapters import cursor as cursor_module
from bridge.quick_chat.adapters.cursor import CursorAdapter
from bridge.quick_chat.adapters.grok import GrokAdapter
from bridge.quick_chat.adapters.opencode import OpenCodeAdapter
from bridge.quick_chat.adapters.pi import PiAdapter
from bridge.quick_chat.model_discovery import _exchange_json_response
from bridge.quick_chat.protocol import Attachment


FIXTURES = Path(__file__).parent / "fixtures"
LIVE_SMOKE_PATH = Path(__file__).parents[1] / "test" / "live-harness-smoke.py"


def load_live_smoke_module():
    spec = importlib.util.spec_from_file_location(
        "quick_chat_live_harness_smoke",
        LIVE_SMOKE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the live harness smoke runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(
    prompt="explain",
    model=None,
    session_id=None,
    attachments=(),
    system_instructions="",
    private=False,
    thinking_effort=None,
):
    return AdapterContext(
        prompt=prompt,
        model=model,
        cwd=Path.home(),
        attachments=attachments,
        session_id=session_id,
        system_instructions=system_instructions,
        private=private,
        thinking_effort=thinking_effort,
    )


def adjacent_pairs(values):
    return set(zip(values, values[1:]))


class CodexAdapterTests(unittest.TestCase):
    @patch("bridge.quick_chat.adapters.process_base.subprocess.run")
    def test_detection_uses_provider_version_after_mise_preamble(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout=(
                "mise ~/.config/mise/config.toml tools: codex@0.147.0\n"
                "codex-cli 0.147.0\n"
            ),
            stderr="",
        )

        detection = CodexAdapter().detect()

        self.assertEqual(detection["version"], "codex-cli 0.147.0")
        self.assertTrue(detection["structured"])

    def test_codex_exchange_keeps_jsonl_server_open_for_async_response(self):
        server = (
            "import json,sys,time\n"
            "for line in sys.stdin:\n"
            " request=json.loads(line)\n"
            " if request.get('id') == 2:\n"
            "  time.sleep(0.05)\n"
            "  print(json.dumps({'id':2,'result':{'ready':True}}), flush=True)\n"
            "  break\n"
        )
        response = _exchange_json_response(
            (sys.executable, "-u", "-c", server),
            ({"id": 1}, {"id": 2}),
            response_id=2,
            cwd=Path.home(),
            timeout=2,
        )
        self.assertEqual(response["result"], {"ready": True})

    @patch("bridge.quick_chat.model_discovery._exchange_json_response")
    def test_codex_discovers_models_from_app_server(self, exchange):
        exchange.return_value = {
            "id": 2,
            "result": {
                "data": [
                    {
                        "model": "gpt-5.6-sol",
                        "displayName": "GPT-5.6 Sol",
                        "description": "Fast coding model",
                        "hidden": False,
                        "isDefault": True,
                        "defaultReasoningEffort": "high",
                        "supportedReasoningEfforts": [
                            {
                                "reasoningEffort": "low",
                                "description": "Faster",
                            },
                            {
                                "reasoningEffort": "high",
                                "description": "Deeper",
                            },
                        ],
                    },
                    {"model": "hidden", "displayName": "Hidden", "hidden": True},
                ]
            },
        }
        models = CodexAdapter().discover_models(Path.home())
        self.assertEqual([model.id for model in models], ["gpt-5.6-sol"])
        self.assertEqual(models[0].label, "GPT-5.6 Sol")
        self.assertTrue(models[0].is_default)
        self.assertEqual([item.id for item in models[0].efforts], ["low", "high"])
        self.assertEqual(
            models[0].to_dict()["efforts"][1]["description"],
            "Deeper",
        )
        self.assertEqual(
            exchange.call_args.args[0], ("codex", "app-server", "--stdio")
        )
        self.assertEqual(exchange.call_args.args[1][-1]["method"], "model/list")

    def test_model_option_distinguishes_adapter_fallback_from_explicit_none(self):
        fallback = ModelOption("fallback", "Fallback")
        explicit_none = ModelOption("none", "None", efforts=())
        self.assertIsNone(fallback.to_dict()["efforts"])
        self.assertEqual(explicit_none.to_dict()["efforts"], [])

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
    def test_structured_adapters_ignore_mise_launcher_preamble(self):
        cases = (
            (CodexAdapter(), "codex-stream.jsonl"),
            (ClaudeAdapter(), "claude-stream.jsonl"),
            (OpenCodeAdapter(), "opencode-stream.jsonl"),
            (GrokAdapter(), "grok-stream.jsonl"),
        )
        for adapter, fixture in cases:
            with self.subTest(adapter=adapter.id):
                preamble = AdapterEvent("stdout", {
                    "text": (
                        "mise ~/.config/mise/config.toml tools: "
                        f"{adapter.id}@1.2.3"
                    ),
                })
                self.assertEqual(adapter.parse_event(preamble), [])

                events = []
                for line in (FIXTURES / fixture).read_text().splitlines():
                    events.extend(adapter.parse_event(
                        AdapterEvent("stdout", {"text": line})
                    ))

                self.assertEqual(
                    [event.type for event in events],
                    ["session", "text_delta", "complete"],
                )
                self.assertTrue(adapter.capabilities.streaming)

    def test_each_adapter_maps_native_thinking_effort(self):
        cases = (
            (
                CodexAdapter(),
                context(thinking_effort="high"),
                ("-c", 'model_reasoning_effort="high"'),
            ),
            (
                ClaudeAdapter(),
                context(thinking_effort="high"),
                ("--effort", "high"),
            ),
            (
                OpenCodeAdapter(),
                context(thinking_effort="high"),
                ("--variant", "high"),
            ),
            (
                GrokAdapter(),
                context(thinking_effort="high"),
                ("--reasoning-effort", "high"),
            ),
            (
                PiAdapter(),
                context(thinking_effort="high"),
                ("--thinking", "high"),
            ),
        )
        for adapter, adapter_context, pair in cases:
            with self.subTest(adapter=adapter.id):
                self.assertIn(pair, adjacent_pairs(adapter.start(adapter_context).argv))

    def test_codex_config_override_precedes_exec(self):
        argv = CodexAdapter().start(context(thinking_effort="high")).argv
        self.assertEqual(argv[:4], (
            "codex",
            "-c",
            'model_reasoning_effort="high"',
            "exec",
        ))

    def test_cursor_is_ask_only_and_merges_model_parameters(self):
        call = CursorAdapter().start(context(
            model="claude-opus-4-8[context=1m,fast=false]",
            thinking_effort="high",
        ))
        self.assertIn(("--mode", "ask"), adjacent_pairs(call.argv))
        self.assertIn((
            "--model",
            "claude-opus-4-8[context=1m,fast=false,effort=high]",
        ), adjacent_pairs(call.argv))
        self.assertNotIn("--force", call.argv)
        self.assertNotIn("--yolo", call.argv)

    def test_cursor_effort_replaces_only_existing_effort(self):
        self.assertEqual(
            cursor_module.merge_cursor_effort(
                "model[effort=low,context=1m]",
                "high",
            ),
            "model[effort=high,context=1m]",
        )
        with self.assertRaises(ValueError):
            cursor_module.merge_cursor_effort("model[nested=[bad]]", "high")
        with self.assertRaises(ValueError):
            CursorAdapter().start(context(thinking_effort="high"))

    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_help_efforts_require_explicit_choices_for_the_requested_flag(self, run):
        cases = (
            (
                ClaudeAdapter(),
                "--effort <level>  Effort level (choices: low, medium, high)\n"
                "--mode <mode>  possible values: unsafe\n",
                ["low", "medium", "high"],
                ("claude", "--help"),
            ),
            (
                PiAdapter(),
                "--thinking <level>  Set thinking level: off, low, high\n",
                ["off", "low", "high"],
                ("pi", "--help"),
            ),
            (
                GrokAdapter(),
                "--reasoning-effort <EFFORT>  Set reasoning effort\n",
                [],
                ("grok", "--help"),
            ),
        )
        for adapter, stdout, expected, argv in cases:
            with self.subTest(adapter=adapter.id):
                run.reset_mock()
                run.return_value = Mock(returncode=0, stdout=stdout, stderr="")
                self.assertEqual(
                    [option.id for option in adapter.effort_options(Path.home())],
                    expected,
                )
                self.assertEqual(run.call_args.args[0], argv)

    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_extended_effort_ids_get_readable_labels(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout="--effort <level>  Effort level (choices: low, xhigh)\n",
            stderr="",
        )
        options = ClaudeAdapter().effort_options(Path.home())
        self.assertEqual(
            [(option.id, option.label) for option in options],
            [("low", "Low"), ("xhigh", "Extra High")],
        )

    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_catalog_efforts_come_only_from_explicit_variants_and_parameters(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout=(
                "anthropic/claude-sonnet-4\n"
                "  variants: low, high\n"
                "openai/gpt-5\n"
            ),
            stderr="",
        )
        opencode_models = OpenCodeAdapter().discover_models(Path.home())
        self.assertEqual(
            [option.id for option in opencode_models[0].efforts],
            ["low", "high"],
        )
        self.assertIsNone(opencode_models[1].efforts)

        run.return_value = Mock(
            returncode=0,
            stdout=(
                "claude-opus-4-8[context=1m] - Claude Opus\n"
                "claude-opus-4-8[context=1m,effort=low] - Claude Opus\n"
                "claude-opus-4-8[context=1m,effort=high] - Claude Opus\n"
            ),
            stderr="",
        )
        cursor_models = CursorAdapter().discover_models(Path.home())
        self.assertEqual(
            [model.id for model in cursor_models],
            ["claude-opus-4-8[context=1m]"],
        )
        self.assertEqual(
            [option.id for option in cursor_models[0].efforts],
            ["low", "high"],
        )

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

    @patch("bridge.quick_chat.model_discovery.subprocess.run")
    def test_grok_catalog_ignores_login_prose_and_marks_native_default(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout=(
                "You are logged in with grok.com.\n\n"
                "Default model: grok-4.6\n\n"
                "Available models:\n"
                "  * grok-4.6 (default)\n"
                "  - grok-4.5\n"
            ),
            stderr="",
        )
        models = GrokAdapter().discover_models(Path.home())
        self.assertEqual([model.id for model in models], ["grok-4.6", "grok-4.5"])
        self.assertTrue(models[0].is_default)
        self.assertFalse(models[1].is_default)

    def test_grok_current_stream_uses_data_and_camel_case_end_fields(self):
        adapter = GrokAdapter()
        text_events = adapter.parse_event(AdapterEvent("stdout", {
            "text": '{"type":"text","data":"QUICK_CHAT_OK"}',
        }))
        end_events = adapter.parse_event(AdapterEvent("stdout", {
            "text": (
                '{"type":"end","stopReason":"end_turn",'
                '"sessionId":"grok-session-current"}'
            ),
        }))
        self.assertEqual(
            [(event.type, event.data) for event in text_events],
            [("text_delta", {"text": "QUICK_CHAT_OK"})],
        )
        self.assertEqual([event.type for event in end_events], ["session", "complete"])
        self.assertEqual(end_events[0].data["sessionId"], "grok-session-current")
        self.assertEqual(end_events[1].data["stopReason"], "end_turn")

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


class LiveHarnessSmokeTests(unittest.TestCase):
    def test_live_smoke_uses_exact_bounded_prompt(self):
        smoke = load_live_smoke_module()
        self.assertEqual(
            smoke.PROMPT,
            "Reply with exactly QUICK_CHAT_OK and nothing else.",
        )

    def test_live_smoke_auth_probes_are_noninteractive(self):
        smoke = load_live_smoke_module()
        self.assertEqual(smoke.auth_probe("codex", "gpt-5"), (
            "codex",
            "login",
            "status",
        ))
        self.assertEqual(smoke.auth_probe("claude", "sonnet"), (
            "claude",
            "auth",
            "status",
        ))
        self.assertEqual(smoke.auth_probe("cursor", "auto"), (
            "cursor-agent",
            "status",
        ))
        self.assertEqual(smoke.auth_probe("pi", "openai/gpt-5"), (
            "pi",
            "auth",
            "check",
            "--model",
            "openai/gpt-5",
            "--json",
            "--no-refresh",
        ))
        self.assertIsNone(smoke.auth_probe("grok", "grok-4"))
        self.assertIsNone(smoke.auth_probe("opencode", "openai/gpt-5"))

    def test_live_smoke_auth_probes_never_print_credentials(self):
        smoke = load_live_smoke_module()
        forbidden = {
            "--api-key",
            "--credentials",
            "--print-api-key",
            "--print-credentials",
            "--print-token",
            "--show-token",
            "--token",
        }
        for adapter_id in smoke.ADAPTER_IDS:
            with self.subTest(adapter=adapter_id):
                probe = smoke.auth_probe(adapter_id, "provider/model") or ()
                self.assertTrue(forbidden.isdisjoint(probe), probe)


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
