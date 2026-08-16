# Adapter authoring

An adapter translates one CLI into Quick Chat's normalized event model. It
provides an immutable `id`, `Capabilities`, `detect()`,
`discover_models(cwd)`, `start(context)`, and `parse_event(event)`.

## Detection and capabilities

`detect()` must invoke `<executable> --version` with `shell=False` and a short
timeout. Report availability and the parsed version without triggering login or
configuration. Capabilities declare streaming, resume, model selection, native
images, enforced read-only behavior, relayable approvals, and whether thinking
effort can be represented safely.

New process adapters must ship with `relayable_approvals=false` until a stable,
tested bidirectional protocol exists. A tool request that cannot be relayed is
denied, never guessed or auto-approved.

`discover_models(cwd)` returns immutable `ModelOption` values. A model may
carry `efforts=None` for adapter fallback, `efforts=()` for explicitly
unsupported, or a non-empty tuple of `EffortOption(id, label, description)`
values. Prefer the CLI's native, non-interactive catalog command. Run a fixed
argument tuple with `shell=False`, cap time and output, strip terminal control
sequences, and never surface raw stderr in the UI. If the CLI has no catalog
operation, expose only documented aliases or return an empty tuple so manual
model entry remains available.

`effort_options(cwd)` may inspect a bounded native help or catalog command, but
it must return only an explicit enum associated with the harness's actual
effort flag. Placeholder syntax such as `<EFFORT>` is not a choice list. Never
copy values from another provider or invent a generic low/medium/high set.

## Invocation

`start(AdapterContext)` returns `Invocation(argv, cwd, env, stdin_text)`.
Construct every argument independently. Never join a prompt, path, model, or
session into a shell string, and never use `shell=True`. Put prompts on stdin
when supported. Include the CLI's strongest read-only, plan, or disallowed-tool
flags and test for the absence of bypass flags.

Implement new and resume forms explicitly. Session IDs emitted by the CLI are
stored inside the Quick Chat conversation and supplied on the next turn.
Images are accepted only when `native_images` is true; otherwise the UI offers
OCR or profile switching.

`AdapterContext.thinking_effort` is `None` for provider default or a previously
validated supported identifier. Built-in adapters translate it natively:

| Adapter | Read-only/Q&A contract | Effort translation |
| --- | --- | --- |
| Codex | `--sandbox read-only` | `-c model_reasoning_effort="…"` before `exec` |
| Claude Code | plan mode plus disallowed mutation tools | `--effort …` |
| OpenCode | no approval bypass flags | `--variant …` |
| Grok | read-only tool allowlist | `--reasoning-effort …` |
| Cursor | mandatory `--mode ask` | merge `effort=…` into the final model parameter block |
| Pi | `--tools read,grep,find,ls` | `--thinking …` |

Omit the native option when effort is `None`. Effort handling must never remove
or replace a read-only argument. In particular, Cursor model parameters are
parsed and rendered as data; they are not string-appended blindly.

## Event parsing

`parse_event()` receives sanitized stdout lines and returns zero or more
`AdapterEvent` values: `status`, `text_delta`, `tool_request`, `session`,
`complete`, or `error`. Unknown JSON fields are ignored. Stderr is a bounded
diagnostic channel and must never become assistant output.

If a recognized CLI produces malformed structured output, preserve that output
as plain text and degrade capabilities to no resume, no native images, and no
relayed approvals. Read-only invocation flags remain mandatory in degraded
mode.

## Fixtures and tests

Add synthetic JSONL under `tests/fixtures/` and adapter contract cases in
`tests/test_adapters.py`. Cover:

- new and resume argv;
- models and attachment paths;
- session and text normalization;
- unknown fields and malformed output;
- exact read-only flags and forbidden-flag absence;
- non-zero exits and authentication diagnostics.

Cancellation belongs to the transport. It targets only the recorded process
group with SIGINT, then SIGTERM, then SIGKILL after bounded waits.

The normal suite must remain offline. After unit and fixture coverage passes,
the opt-in matrix can exercise all built-ins through the same production
adapters and process transport:

```bash
QUICK_CHAT_LIVE_HARNESSES=1 ./test/all
```

This makes six real provider requests and may consume account quota. Success
requires a parsed CLI version, non-interactive authentication, a discovered
model, normalized `QUICK_CHAT_OK` assistant text, a normalized completion event,
zero exit status, and no file created in the fresh working directory.
