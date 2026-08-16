# Adapter authoring

An adapter translates one CLI into Quick Chat's normalized event model. It
provides an immutable `id`, `Capabilities`, `detect()`,
`discover_models(cwd)`, `start(context)`, and `parse_event(event)`.

## Detection and capabilities

`detect()` must invoke `<executable> --version` with `shell=False` and a short
timeout. Report availability and the parsed version without triggering login or
configuration. Capabilities declare streaming, resume, model selection, native
images, enforced read-only behavior, and relayable approvals.

New process adapters must ship with `relayable_approvals=false` until a stable,
tested bidirectional protocol exists. A tool request that cannot be relayed is
denied, never guessed or auto-approved.

`discover_models(cwd)` returns immutable `ModelOption` values. Prefer the CLI's
native, non-interactive catalog command. Run a fixed argument tuple with
`shell=False`, cap time and output, strip terminal control sequences, and never
surface raw stderr in the UI. If the CLI has no catalog operation, expose only
documented aliases or return an empty tuple so manual model entry remains
available.

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
