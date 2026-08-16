# Omarchy Quick Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Omarchy shell plugin that opens a native quick-chat popup, connects safely to six installed agent CLIs, and attaches explicitly approved desktop context.

**Architecture:** A `menu` entry point renders the QML interface while a `service` entry point owns global shortcuts. Both call a bundled Python 3.12+ bridge over JSON Lines; the bridge validates profiles, persists local state, captures context, and normalizes capability-aware CLI adapters. Process transports ship first, behind a transport protocol that later accepts persistent ACP connections without changing QML or profile schemas.

**Tech Stack:** Omarchy Quattro plugin manifest, Qt 6 QML, Quickshell, Python 3.12 standard library, Bash 5 test runners, Node.js for pure QML JavaScript model tests, Hyprland global shortcuts.

## Global Constraints

- The repository is a third-party plugin with manifest id `community.quick-chat`; never use the reserved `omarchy.*` namespace.
- Runtime Python uses the standard library only; installation must not run hooks, package managers, `sudo`, or `pkexec`.
- QML entry points are `Item`s, accept `omarchyPath`, `shell`, `manifest`, and `pluginRegistry`, and implement `open(payloadJson)` and `close()` when they expose a menu surface.
- Use two-space indentation in QML, JavaScript, JSON, and Bash; use four-space indentation in Python.
- Launch subprocesses with argument arrays and `shell=False`; never interpolate prompts, paths, or profile values into a shell command.
- Every built-in adapter defaults to read-only behavior and never passes auto-approve, force, dangerous-bypass, or equivalent flags.
- Screen or app context is captured only after a user action, remains previewed until submission, and is deleted after completion, cancellation, failure, or preview removal.
- Persist no credentials. Reuse each CLI's existing authentication.
- Persist the latest 20 conversations by default; accept any positive finite limit or `null` for unlimited retention.
- Private conversations persist no Quick Chat messages, attachment paths, or CLI session mapping.
- One bridge/UI instance runs at most one CLI turn at a time.
- Run visual acceptance only in a disposable Omarchy environment, never by disrupting the active desktop session.

---

## Planned File Structure

```text
manifest.json                         Omarchy plugin contract
LICENSE                               MIT license
README.md                             install, configure, use, troubleshoot
QuickChat.qml                         menu lifecycle and top-level window
Service.qml                           keep-loaded shortcut service
BridgeClient.qml                      JSONL bridge process client
ShortcutDelegate.qml                 one immutable Hyprland GlobalShortcut target
models/ChatModel.js                   pure conversation/event state transitions
models/ProfileModel.js                pure profile/default/shortcut projections
ui/ChatSurface.qml                    compact and expanded layout coordinator
ui/ChatHeader.qml                     profile, availability, privacy, history controls
ui/Composer.qml                       prompt and context controls
ui/MessageList.qml                    safe streamed message rendering
ui/AttachmentPreview.qml              image/text context consent surface
ui/HistoryDrawer.qml                  recent conversation list and clear action
ui/ProfileSettings.qml                profile editor and CLI capability display
ui/ApprovalCard.qml                   approve-once/deny operation card
ui/InlineError.qml                    actionable failure presentation
bridge/quick-chat-bridge              executable Python entry point
bridge/quick_chat/__init__.py          package version
bridge/quick_chat/main.py              JSONL loop and maintenance subcommands
bridge/quick_chat/protocol.py          request/event validation and serialization
bridge/quick_chat/models.py            typed config/profile/conversation records
bridge/quick_chat/paths.py             XDG path resolution
bridge/quick_chat/storage.py           atomic JSON persistence and quarantine
bridge/quick_chat/history.py           retention and private-mode policy
bridge/quick_chat/engine.py            one-turn orchestration
bridge/quick_chat/process.py           exact child process lifecycle
bridge/quick_chat/sanitize.py          ANSI/control stripping and diagnostics
bridge/quick_chat/transports/base.py   transport protocol
bridge/quick_chat/transports/process.py process-backed implementation
bridge/quick_chat/transports/acp.py    phase-2 persistent ACP implementation
bridge/quick_chat/adapters/base.py     adapter capability and invocation types
bridge/quick_chat/adapters/registry.py adapter lookup and version cache
bridge/quick_chat/adapters/codex.py    Codex command/events
bridge/quick_chat/adapters/claude.py   Claude Code command/events
bridge/quick_chat/adapters/opencode.py OpenCode command/events
bridge/quick_chat/adapters/grok.py     Grok command/events
bridge/quick_chat/adapters/cursor.py   Cursor command/events
bridge/quick_chat/adapters/pi.py       Pi command/events
bridge/quick_chat/adapters/custom.py   typed custom command templates
bridge/quick_chat/context/base.py      context provider interface
bridge/quick_chat/context/capture.py   active-window/full-screen capture
bridge/quick_chat/context/app.py       active app/window metadata
bridge/quick_chat/context/selection.py explicit primary-selection text
bridge/quick_chat/context/ocr.py       explicit OCR conversion
bridge/quick_chat/context/omarchy.py   allowlisted Omarchy CLI queries
bridge/quick_chat/shortcuts.py         conflict detection and live Hypr binds
test/all                               aggregate non-graphical runner
test/manifest-test.sh                  plugin contract checks
test/qml-model-test.js                 pure JS state tests
test/qml-static-test.sh                QML lifecycle/static checks
tests/fixtures/                        synthetic CLI JSONL and fake executables
tests/test_protocol.py                 bridge protocol tests
tests/test_models.py                   config/profile validation tests
tests/test_storage.py                  state, retention, private-mode tests
tests/test_process.py                  process lifecycle tests
tests/test_adapters.py                 six adapter contract tests
tests/test_context.py                  capture and cleanup tests
tests/test_shortcuts.py                conflict and binding tests
tests/test_engine.py                   end-to-end fake CLI tests
test/acceptance/quick-chat-test.sh      disposable desktop acceptance flow
docs/bridge-protocol.md                 request/event wire contract
docs/adapter-authoring.md               custom/built-in adapter guide
docs/acp-transport.md                   phase-2 ACP lifecycle
```

### Task 1: Establish the installable plugin contract and test harness

**Files:**
- Create: `manifest.json`
- Create: `LICENSE`
- Create: `QuickChat.qml`
- Create: `Service.qml`
- Create: `test/all`
- Create: `test/manifest-test.sh`
- Create: `test/qml-static-test.sh`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: Omarchy manifest schema version 1 and menu/service entry-point injection.
- Produces: plugin id `community.quick-chat`, entry points `QuickChat.qml` and `Service.qml`, and aggregate command `./test/all`.

- [ ] **Step 1: Write the failing manifest contract test**

```bash
#!/bin/bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
assert manifest["schemaVersion"] == 1
assert manifest["id"] == "community.quick-chat"
assert manifest["kinds"] == ["menu", "service"]
assert manifest["keepLoaded"] is True
assert manifest["entryPoints"] == {"menu": "QuickChat.qml", "service": "Service.qml"}
for path in manifest["entryPoints"].values():
    assert (root / path).is_file(), path
PY
```

- [ ] **Step 2: Run the manifest test and verify it fails**

Run: `bash test/manifest-test.sh`  
Expected: FAIL because `manifest.json` does not exist.

- [ ] **Step 3: Add the manifest and minimal QML lifecycle**

```json
{
  "schemaVersion": 1,
  "id": "community.quick-chat",
  "name": "Quick Chat",
  "version": "0.1.0",
  "author": "Omarchy Quick Chat contributors",
  "license": "MIT",
  "description": "Quick Q&A through locally installed agent CLIs",
  "kinds": ["menu", "service"],
  "keepLoaded": true,
  "entryPoints": {"menu": "QuickChat.qml", "service": "Service.qml"}
}
```

`QuickChat.qml` must expose injected properties plus `open(payloadJson)` and `close()`; `Service.qml` must expose the same injected properties and remain an inert `Item` until Task 10.

- [ ] **Step 4: Add static and aggregate runners**

```bash
#!/bin/bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/test/manifest-test.sh"
bash "$ROOT/test/qml-static-test.sh"
python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py'
```

`test/qml-static-test.sh` must assert both QML roots are `Item`s, the menu lifecycle functions exist, and run `qmllint` only when `qmllint` is present.

- [ ] **Step 5: Run the initial suite**

Run: `./test/all`  
Expected: PASS with manifest and QML lifecycle checks; Python discovers zero tests successfully.

- [ ] **Step 6: Commit the plugin contract**

```bash
git add manifest.json LICENSE QuickChat.qml Service.qml test tests/__init__.py
git commit -m "feat: establish quick chat plugin contract"
```

### Task 2: Define the bridge protocol and typed domain model

**Files:**
- Create: `bridge/quick-chat-bridge`
- Create: `bridge/quick_chat/__init__.py`
- Create: `bridge/quick_chat/main.py`
- Create: `bridge/quick_chat/protocol.py`
- Create: `bridge/quick_chat/models.py`
- Create: `tests/test_protocol.py`
- Create: `tests/test_models.py`
- Create: `docs/bridge-protocol.md`

**Interfaces:**
- Consumes: newline-delimited UTF-8 JSON objects on stdin.
- Produces: `Request.from_dict(dict) -> Request`, `Event.to_json() -> str`, and events with types `ready`, `status`, `text_delta`, `tool_request`, `session`, `complete`, and `error`.

- [ ] **Step 1: Write failing request and event tests**

```python
def test_run_request_requires_profile_prompt_and_conversation():
    request = Request.from_dict({
        "type": "run",
        "requestId": "req-1",
        "conversationId": "conv-1",
        "profileId": "default",
        "prompt": "Explain this",
        "attachments": [],
        "private": False,
    })
    self.assertEqual(request.profile_id, "default")

def test_event_json_is_one_sanitized_line():
    encoded = Event("text_delta", "req-1", {"text": "hello\nworld"}).to_json()
    self.assertEqual(len(encoded.splitlines()), 1)
    self.assertEqual(json.loads(encoded)["data"]["text"], "hello\nworld")
```

- [ ] **Step 2: Run protocol tests and verify they fail**

Run: `python3 -m unittest tests.test_protocol tests.test_models -v`  
Expected: FAIL because `Request`, `Event`, and profile types do not exist.

- [ ] **Step 3: Implement exact protocol dataclasses**

```python
@dataclass(frozen=True)
class Attachment:
    id: str
    kind: Literal["image", "text", "metadata"]
    path: str | None
    text: str | None
    mime_type: str

@dataclass(frozen=True)
class Request:
    type: str
    request_id: str
    conversation_id: str | None = None
    profile_id: str | None = None
    prompt: str | None = None
    attachments: tuple[Attachment, ...] = ()
    private: bool = False

@dataclass(frozen=True)
class Event:
    type: str
    request_id: str
    data: dict[str, object]

REQUEST_TYPES = frozenset({
    "run", "cancel", "approve", "deny", "probe", "profiles",
    "history.list", "history.get", "history.clear",
    "context.capture", "context.ocr", "context.remove",
})
```

Reject request types outside `REQUEST_TYPES`, empty IDs, non-string prompts, attachments outside the runtime capture root, and request bodies above 1 MiB.

- [ ] **Step 4: Implement the JSONL loop**

`bridge/quick-chat-bridge` is a Python executable with `#!/usr/bin/python3`; it prepends its own `bridge/` directory to `sys.path` and calls `quick_chat.main.run(sys.stdin, sys.stdout)`. `run` must emit `{"type":"ready","requestId":"bridge","data":{"protocolVersion":1}}` once, parse each input line independently, and emit a typed `error` without terminating on a bad request.

- [ ] **Step 5: Document the wire examples and run tests**

Run: `python3 -m unittest tests.test_protocol tests.test_models -v`  
Expected: PASS, including maximum-size and invalid-attachment cases.

- [ ] **Step 6: Commit the bridge contract**

```bash
git add bridge tests/test_protocol.py tests/test_models.py docs/bridge-protocol.md
git commit -m "feat: define quick chat bridge protocol"
```

### Task 3: Add XDG configuration, profiles, history, and private-mode persistence

**Files:**
- Create: `bridge/quick_chat/paths.py`
- Create: `bridge/quick_chat/storage.py`
- Create: `bridge/quick_chat/history.py`
- Modify: `bridge/quick_chat/models.py`
- Modify: `bridge/quick_chat/main.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `PathSet.from_env(env)`, schema-versioned JSON, and validated `Profile`/`Conversation` records.
- Produces: `ConfigStore.load() -> Config`, `ConfigStore.save(Config)`, `HistoryStore.upsert(Conversation, private)`, `HistoryStore.clear()`, and `HistoryStore.list() -> list[Conversation]`.

- [ ] **Step 1: Write failing storage and retention tests**

```python
def test_default_config_has_six_profiles_and_twenty_item_retention(self):
    config = ConfigStore(self.paths).load()
    self.assertEqual(config.history_limit, 20)
    self.assertEqual([p.adapter_id for p in config.profiles],
                     ["codex", "claude", "opencode", "grok", "cursor", "pi"])

def test_private_conversation_writes_nothing(self):
    self.history.upsert(sample_conversation(), private=True)
    self.assertFalse(self.paths.history_file.exists())

def test_null_retention_keeps_all_conversations(self):
    self.config = dataclasses.replace(self.config, history_limit=None)
    self.history = HistoryStore(self.paths, self.config)
    for index in range(25):
        self.history.upsert(sample_conversation(str(index)), private=False)
    self.assertEqual(len(self.history.list()), 25)
```

- [ ] **Step 2: Run storage tests and verify they fail**

Run: `python3 -m unittest tests.test_storage -v`  
Expected: FAIL because XDG paths and stores do not exist.

- [ ] **Step 3: Implement XDG paths and atomic JSON writes**

`PathSet.from_env` must resolve config under `$XDG_CONFIG_HOME/omarchy/quick-chat` or `~/.config/omarchy/quick-chat`, state under `$XDG_STATE_HOME/omarchy/quick-chat` or `~/.local/state/omarchy/quick-chat`, and captures under `$XDG_RUNTIME_DIR/omarchy-quick-chat`. `atomic_write_json(path, value)` must write mode `0600`, `fsync`, and `os.replace` a sibling temporary file.

- [ ] **Step 4: Implement schema version 1 defaults and validation**

```python
@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    adapter_id: str
    model: str | None = None
    system_instructions: str = ""
    working_directory_strategy: Literal["home", "fixed", "active-project"] = "home"
    working_directory: str | None = None
    context_providers: tuple[str, ...] = ()
    permission_policy: Literal["read-only", "ask"] = "read-only"
    shortcut: str | None = None
    history_limit: int | None = None
    private_by_default: bool = False
    advanced_args: tuple[str, ...] = ()

def default_profile(profile_id: str, name: str) -> Profile:
    return Profile(id=profile_id, name=name, adapter_id=profile_id)

DEFAULT_PROFILES = (
    default_profile("codex", "Codex"),
    default_profile("claude", "Claude Code"),
    default_profile("opencode", "OpenCode"),
    default_profile("grok", "Grok"),
    default_profile("cursor", "Cursor"),
    default_profile("pi", "Pi"),
)
```

The first profile is selected by default. Fixed working directories must exist; profile IDs must match `[a-z0-9][a-z0-9._-]{0,63}`; history limits are positive integers or `None`.

- [ ] **Step 5: Implement retention, session mapping, clear, and corruption quarantine**

Sort conversations by `updated_at` descending before applying the global or profile override. Save CLI session mappings inside each persisted conversation. On JSON decode or schema failure, rename the file to `<name>.corrupt-YYYYMMDDTHHMMSSZ` and return defaults with a recovery diagnostic.

- [ ] **Step 6: Run storage tests**

Run: `python3 -m unittest tests.test_models tests.test_storage -v`  
Expected: PASS for default profiles, finite/unlimited retention, private mode, clear, permissions, atomic replace, and quarantine.

- [ ] **Step 7: Commit persistence**

```bash
git add bridge/quick_chat tests/test_models.py tests/test_storage.py
git commit -m "feat: persist quick chat profiles and history"
```

### Task 4: Build the safe process transport and adapter interface

**Files:**
- Create: `bridge/quick_chat/sanitize.py`
- Create: `bridge/quick_chat/process.py`
- Create: `bridge/quick_chat/transports/__init__.py`
- Create: `bridge/quick_chat/transports/base.py`
- Create: `bridge/quick_chat/transports/process.py`
- Create: `bridge/quick_chat/adapters/__init__.py`
- Create: `bridge/quick_chat/adapters/base.py`
- Create: `bridge/quick_chat/adapters/registry.py`
- Create: `bridge/quick_chat/engine.py`
- Create: `tests/fixtures/fake_stream_cli.py`
- Create: `tests/test_process.py`
- Create: `tests/test_engine.py`

**Interfaces:**
- Consumes: `Invocation(argv, cwd, env, stdin_text)`, `Adapter`, and a validated `Request`.
- Produces: `Transport.run(request_id, invocation, emit) -> RunResult`, `Transport.cancel(request_id)`, `Adapter.start(context) -> Invocation`, and `Engine.handle(Request) -> Iterator[Event]`.

- [ ] **Step 1: Write failing process isolation tests**

```python
def test_prompt_is_stdin_and_never_shell_syntax(self):
    invocation = Invocation(
        argv=(sys.executable, str(FAKE_CLI), "stream"),
        cwd=self.tempdir,
        env={"PATH": os.environ["PATH"]},
        stdin_text="$(touch should-not-exist); `id`",
    )
    result = self.transport.run("req-1", invocation, self.events.append)
    self.assertEqual(result.exit_code, 0)
    self.assertFalse((Path(self.tempdir) / "should-not-exist").exists())

def test_second_concurrent_run_is_rejected(self):
    with self.running_request("req-1"):
        with self.assertRaises(BusyError):
            self.engine.start(request("req-2"))
```

- [ ] **Step 2: Run process tests and verify they fail**

Run: `python3 -m unittest tests.test_process tests.test_engine -v`  
Expected: FAIL because the process transport and engine do not exist.

- [ ] **Step 3: Define invocation, capabilities, adapter, and transport types**

```python
@dataclass(frozen=True)
class Capabilities:
    streaming: bool
    resume: bool
    model: bool
    native_images: bool
    read_only_enforced: bool
    relayable_approvals: bool

@dataclass(frozen=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    stdin_text: str | None

class Transport(Protocol):
    def run(self, request_id: str, invocation: Invocation,
            emit: Callable[[AdapterEvent], None]) -> RunResult: ...
    def cancel(self, request_id: str) -> bool: ...
```

- [ ] **Step 4: Implement exact child lifecycle and sanitization**

Use `subprocess.Popen(..., shell=False, start_new_session=True, text=True, bufsize=1)`. Read stdout and stderr concurrently, cap diagnostics at 256 KiB, strip C0 controls except tab/newline, and on cancellation send `SIGINT`, wait 1 second, send `SIGTERM`, wait 2 seconds, then `SIGKILL` only to the recorded process group.

- [ ] **Step 5: Implement registry and one-turn engine**

Registry keys are exactly `codex`, `claude`, `opencode`, `grok`, `cursor`, `pi`, and `custom`. Cache `detect()` results for the bridge lifetime and invalidate one key on a probe request. The engine must emit `status: starting`, adapter deltas, a `session` event when available, and exactly one terminal `complete` or `error` event.

- [ ] **Step 6: Run process and engine tests**

Run: `python3 -m unittest tests.test_process tests.test_engine -v`  
Expected: PASS for stdin isolation, stderr separation, ANSI stripping, timeout, exact process-group cancellation, and busy rejection.

- [ ] **Step 7: Commit the process transport**

```bash
git add bridge/quick_chat tests/fixtures/fake_stream_cli.py tests/test_process.py tests/test_engine.py
git commit -m "feat: add safe process transport"
```

### Task 5: Implement the Codex and Claude Code vertical slice

**Files:**
- Create: `bridge/quick_chat/adapters/codex.py`
- Create: `bridge/quick_chat/adapters/claude.py`
- Modify: `bridge/quick_chat/adapters/registry.py`
- Create: `tests/fixtures/codex-stream.jsonl`
- Create: `tests/fixtures/claude-stream.jsonl`
- Create: `tests/test_adapters.py`

**Interfaces:**
- Consumes: base `AdapterContext(prompt, model, cwd, attachments, session_id, system_instructions)`.
- Produces: `CodexAdapter` and `ClaudeAdapter`, each returning safe `Invocation`s and normalized `AdapterEvent`s.

- [ ] **Step 1: Write failing Codex and Claude invocation tests**

```python
def test_codex_is_read_only_and_accepts_prompt_on_stdin(self):
    call = CodexAdapter().start(context(prompt="explain", model="gpt-5"))
    self.assertEqual(call.argv[:4], ("codex", "exec", "--json", "--sandbox"))
    self.assertIn("read-only", call.argv)
    self.assertNotIn("--full-auto", call.argv)
    self.assertEqual(call.stdin_text, "explain")

def test_claude_uses_plan_mode_and_disallows_mutation_tools(self):
    call = ClaudeAdapter().start(context(prompt="explain"))
    self.assertIn(("--permission-mode", "plan"), adjacent_pairs(call.argv))
    self.assertIn("Edit", call.argv)
    self.assertNotIn("--dangerously-skip-permissions", call.argv)
```

- [ ] **Step 2: Run adapter tests and verify they fail**

Run: `python3 -m unittest tests.test_adapters -v`  
Expected: FAIL because both adapters are missing.

- [ ] **Step 3: Implement Codex start, resume, images, and JSONL parsing**

New session arguments are `codex exec --json --sandbox read-only --skip-git-repo-check --cd <cwd> [--model <model>] [--image <path> ...] -`. Resume arguments insert `resume <session-id> -` after global exec flags. Parse the thread/session-start event into `session`, assistant text deltas into `text_delta`, and turn completion into `complete`; ignore unknown JSON keys.

- [ ] **Step 4: Implement Claude start, resume, and stream parsing**

Use `claude -p --verbose --output-format stream-json --permission-mode plan --disallowedTools Bash Edit Write NotebookEdit [--model <model>] [--resume <session-id>] <prompt>`. Mark native images false so the context layer offers OCR. Parse `system.init.session_id`, assistant content deltas, and result/error records. Never pass `--allowedTools`, because user settings must not broaden the explicit disallow list.

- [ ] **Step 5: Add version probes and degraded mode**

Run `<executable> --version` with a 2-second timeout. A recognized non-empty version enables structured parsing. A parse failure changes the cached capability to plain text with `resume=false`, `native_images=false`, and `relayable_approvals=false`; read-only flags remain mandatory.

- [ ] **Step 6: Run adapter and engine tests**

Run: `python3 -m unittest tests.test_adapters tests.test_engine -v`  
Expected: PASS for new/resume invocations, image capability, unknown fields, degraded text, and no dangerous flags.

- [ ] **Step 7: Commit the first adapters**

```bash
git add bridge/quick_chat/adapters tests/fixtures tests/test_adapters.py
git commit -m "feat: connect Codex and Claude Code"
```

### Task 6: Connect QML to the bridge and render the compact chat surface

**Files:**
- Create: `BridgeClient.qml`
- Create: `models/ChatModel.js`
- Create: `ui/ChatSurface.qml`
- Create: `ui/ChatHeader.qml`
- Create: `ui/Composer.qml`
- Create: `ui/MessageList.qml`
- Create: `ui/InlineError.qml`
- Modify: `QuickChat.qml`
- Create: `test/qml-model-test.js`
- Modify: `test/qml-static-test.sh`
- Modify: `test/all`

**Interfaces:**
- Consumes: bridge JSONL events and menu payload `{ "profileId": string?, "conversationId": string? }`.
- Produces: `BridgeClient.send(object)`, signals `eventReceived(var)`/`bridgeFailed(string)`, and pure `ChatModel.reduce(state, event) -> state`.

- [ ] **Step 1: Write failing JavaScript reducer tests**

```javascript
const state = ChatModel.initialState("conv-1", "codex")
const streamed = ChatModel.reduce(state, {
  type: "text_delta", requestId: "req-1", data: { text: "Hello" }
})
assert.equal(streamed.messages.at(-1).role, "assistant")
assert.equal(streamed.messages.at(-1).text, "Hello")
assert.equal(ChatModel.reduce(streamed, { type: "complete", requestId: "req-1", data: {} }).running, false)
```

- [ ] **Step 2: Run the JS test and verify it fails**

Run: `node test/qml-model-test.js`  
Expected: FAIL because `models/ChatModel.js` does not exist.

- [ ] **Step 3: Implement the pure chat reducer**

Export `initialState`, `beginRun`, `reduce`, `retryRun`, and `clearError` under CommonJS when `module` exists. Ignore events whose `requestId` is not the active run, append deltas to one assistant message, store run attempts under the originating user message, and make Retry reuse the message instead of appending it.

- [ ] **Step 4: Implement the bridge client**

`BridgeClient.qml` uses one `Process` with command `[manifest.__sourceDir + "/bridge/quick-chat-bridge"]`, `stdinEnabled: true`, a `SplitParser` for stdout, and a separate stderr collector. `send(object)` calls `process.write(JSON.stringify(object) + "\n")`; it queues messages until the `ready` event, restarts once after an unexpected exit, and never interprets stderr as assistant text.

- [ ] **Step 5: Implement the centered popup shell**

Use a card-sized centered `PanelWindow` on the overlay layer with exclusive keyboard focus and `HyprlandFocusGrab` outside-click dismissal. Do not create a full-screen scrim or transparent mouse target. Render the card and every control from live `Color.*`, `Style.*`, and `Border.*` tokens. Compact width is capped at `Style.space(620)` and compact height at 70% of the monitor.

- [ ] **Step 6: Implement keyboard-first compact chat controls**

Header shows the active profile, CLI state, and private toggle. Composer supports `Ctrl+Enter` to send, plain Enter for a newline, and disables Send during a run. Message list renders text with selectable `Text`, never rich-text links that execute automatically. Stop sends `{type:"cancel", requestId:<active>}`. `Esc` hides the window without cancelling and reopening restores state.

- [ ] **Step 7: Run model and static tests**

Run: `./test/all`  
Expected: PASS for reducer behavior, lifecycle presence, QML imports, and all Python tests.

- [ ] **Step 8: Commit the first usable popup**

```bash
git add QuickChat.qml BridgeClient.qml models ui test
git commit -m "feat: add streaming quick chat popup"
```

### Task 7: Add resumable history, expanded mode, and profile selection

**Files:**
- Create: `models/ProfileModel.js`
- Create: `ui/HistoryDrawer.qml`
- Create: `ui/ProfileSettings.qml`
- Modify: `ui/ChatHeader.qml`
- Modify: `ui/ChatSurface.qml`
- Modify: `ui/MessageList.qml`
- Modify: `QuickChat.qml`
- Modify: `test/qml-model-test.js`
- Modify: `tests/test_engine.py`

**Interfaces:**
- Consumes: bridge profile/history responses and `ChatModel` state.
- Produces: `ProfileModel.defaults(config)`, `ProfileModel.update(config, patch)`, compact/expanded modes, and bridge requests `profiles`, `history.list`, `history.get`, and `history.clear`.

- [ ] **Step 1: Write failing profile and history UI-model tests**

```javascript
const profiles = ProfileModel.normalize({
  historyLimit: 20,
  profiles: [{ id: "work", name: "Work", adapterId: "codex" }]
})
assert.equal(profiles.selectedId, "work")
assert.equal(ProfileModel.setHistoryLimit(profiles, null).historyLimit, null)
assert.throws(() => ProfileModel.setHistoryLimit(profiles, 0))

const retried = ChatModel.retryRun(ChatModel.withFailedRun("question", "timeout"))
assert.equal(retried.messages.filter(message => message.role === "user").length, 1)
assert.equal(retried.messages[0].attempts.length, 2)
```

- [ ] **Step 2: Run the model test and verify it fails**

Run: `node test/qml-model-test.js`  
Expected: FAIL because `ProfileModel` and history transitions are absent.

- [ ] **Step 3: Add bridge profile and history commands**

`profiles` returns the schema-versioned config with adapter capability states. `history.list` returns summaries sorted by `updatedAt` descending. `history.get` returns one conversation. `history.clear` requires `confirm: true`, clears mappings and Quick Chat history, and leaves underlying CLI-owned sessions untouched.

- [ ] **Step 4: Implement the history drawer and profile selector**

History rows show title, profile name, update time, and private conversations never appear. Selecting a row requests its full conversation and maps the stored adapter session ID for the next turn. The header profile selector is keyboard navigable and disables unavailable profiles only for submission, not for viewing their history.

- [ ] **Step 5: Implement expanded mode and settings shell**

Expand toggles `compact` to `expanded` on the same root state. Expanded width is `min(Style.space(1040), panel.width - Style.gapsOut * 2)` and height is `min(Style.space(760), panel.height - Style.gapsOut * 2)`. It adds the history drawer and profile-settings pane without spawning another window or bridge.

- [ ] **Step 6: Implement clear history and retention controls**

Use Omarchy's `ConfirmDialog` for Clear History. The retention field accepts any positive integer and an Unlimited toggle that serializes `null`. A successful clear resets the visible conversation and session mapping; cancellation changes no state.

- [ ] **Step 7: Run focused and aggregate tests**

Run: `node test/qml-model-test.js && python3 -m unittest tests.test_storage tests.test_engine -v && ./test/all`  
Expected: PASS for resume mapping, retry identity, finite/unlimited retention, clear confirmation, and compact/expanded state.

- [ ] **Step 8: Commit history and expanded mode**

```bash
git add models ui QuickChat.qml test/qml-model-test.js tests/test_engine.py
git commit -m "feat: add quick chat history and expanded mode"
```

### Task 8: Add explicit active-window, full-screen, metadata, and OCR context

**Files:**
- Create: `bridge/quick_chat/context/__init__.py`
- Create: `bridge/quick_chat/context/base.py`
- Create: `bridge/quick_chat/context/capture.py`
- Create: `bridge/quick_chat/context/app.py`
- Create: `bridge/quick_chat/context/ocr.py`
- Create: `bridge/quick_chat/context/selection.py`
- Create: `bridge/quick_chat/context/omarchy.py`
- Create: `ui/AttachmentPreview.qml`
- Modify: `ui/Composer.qml`
- Modify: `ui/ChatSurface.qml`
- Modify: `bridge/quick_chat/engine.py`
- Create: `tests/fixtures/fake-capture`
- Create: `tests/test_context.py`

**Interfaces:**
- Consumes: context requests `context.capture`, `context.ocr`, `context.remove`, and adapter `native_images` capability.
- Produces: `ContextProvider.capture(ContextRequest) -> Attachment`, runtime-owned files, and visible preview records `{id, kind, path, mimeType, appName, windowTitle, size}`.

- [ ] **Step 1: Write failing capture consent and cleanup tests**

```python
def test_fullscreen_capture_uses_omarchy_and_returns_runtime_file(self):
    attachment = self.capture.fullscreen()
    self.assertEqual(self.calls[0], ["omarchy", "capture", "screenshot", "fullscreen", "save"])
    self.assertTrue(attachment.path.is_relative_to(self.paths.capture_dir))

def test_remove_and_private_completion_delete_capture(self):
    attachment = self.capture.active_window()
    self.assertTrue(attachment.path.exists())
    self.manager.remove(attachment.id)
    self.assertFalse(attachment.path.exists())
```

- [ ] **Step 2: Run context tests and verify they fail**

Run: `python3 -m unittest tests.test_context -v`  
Expected: FAIL because context providers do not exist.

- [ ] **Step 3: Implement capture and metadata providers**

Invoke Omarchy capture with argument arrays. Use `omarchy capture screenshot windows save` for active-window capture and `omarchy capture screenshot fullscreen save` for full-screen capture; parse the final non-empty stdout line as the saved path, copy it into the mode-`0700` runtime directory with mode `0600`, then delete only the plugin's copied file. Read active app metadata from `hyprctl -j activewindow`, extracting `class` and `title` without executing them.

- [ ] **Step 4: Implement explicit OCR, selected text, and allowlisted Omarchy queries**

OCR runs only after `context.ocr` on a selected image, using `tesseract <path> stdout`. Store returned text in memory as a new text attachment and leave the image preview selected until the user removes it. Selected Text runs `wl-paste --primary --no-newline` only after its composer button is pressed, caps the result at 256 KiB, and previews it as text. Omarchy queries are enum values mapped to fixed argv arrays; version 1 includes `commands` (`omarchy commands --json`) and `debug` (`omarchy debug --no-sudo --print`) only.

- [ ] **Step 5: Resolve the active-project working directory without shell execution**

For `working_directory_strategy == "active-project"`, read the active window PID from `hyprctl -j activewindow`, resolve `/proc/<pid>/cwd`, and fall back to the user's home directory with an inline diagnostic when the PID or cwd is unavailable. Fixed directories remain validation errors rather than falling back.

- [ ] **Step 6: Implement preview-first QML behavior**

Context buttons for Window, Screen, App, and Selected Text request context but never submit. `AttachmentPreview.qml` displays images or text plus app name, window title, and byte size; Remove deletes it through the bridge. Send includes only attachment IDs still present in the preview model. When `native_images=false`, Send opens a choice between Convert to text and Switch profile.

- [ ] **Step 7: Add cleanup on every terminal path**

The engine owns attachment IDs per request and removes their files after `complete`, `error`, timeout, cancellation, bridge shutdown, and preview removal. A startup sweep removes files older than 24 hours from the plugin runtime directory and never follows symlinks.

- [ ] **Step 8: Run context and engine tests**

Run: `python3 -m unittest tests.test_context tests.test_engine -v && ./test/all`  
Expected: PASS for active/full capture argv, metadata and active-project parsing, selected text, explicit OCR, query allowlist, symlink refusal, and all cleanup paths.

- [ ] **Step 9: Commit desktop context**

```bash
git add bridge/quick_chat/context bridge/quick_chat/engine.py ui tests test
git commit -m "feat: attach consented desktop context"
```

### Task 9: Add OpenCode, Grok, Cursor, and Pi adapters

**Files:**
- Create: `bridge/quick_chat/adapters/opencode.py`
- Create: `bridge/quick_chat/adapters/grok.py`
- Create: `bridge/quick_chat/adapters/cursor.py`
- Create: `bridge/quick_chat/adapters/pi.py`
- Modify: `bridge/quick_chat/adapters/registry.py`
- Create: `tests/fixtures/opencode-stream.jsonl`
- Create: `tests/fixtures/grok-stream.jsonl`
- Create: `tests/fixtures/cursor-stream.jsonl`
- Create: `tests/fixtures/pi-stream.jsonl`
- Modify: `tests/test_adapters.py`

**Interfaces:**
- Consumes: the `Adapter`/`AdapterContext` contract from Task 4.
- Produces: four registered adapters with exact capabilities and normalized events.

- [ ] **Step 1: Write failing invocation safety tests for all four adapters**

```python
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

def test_pi_uses_only_read_tools(self):
    call = PiAdapter().start(context())
    self.assertIn("read,grep,find,ls", call.argv)
```

- [ ] **Step 2: Run adapter tests and verify they fail**

Run: `python3 -m unittest tests.test_adapters -v`  
Expected: FAIL because the four adapters do not exist.

- [ ] **Step 3: Implement OpenCode**

Use `opencode run --format json --dir <cwd> [--model <model>] [--session <session-id>] <prompt>`. Never pass `--auto`; OpenCode non-interactive mode rejects permission requests by default. Support native files with repeated `--file <path>`, structured streaming, and session IDs. Set `relayable_approvals=false` for process mode.

- [ ] **Step 4: Implement Grok**

Use `grok -p <prompt> --output-format streaming-json --cwd <cwd> --tools read_file,grep,list_dir --disallowed-tools Agent [--model <model>] [--session-id <id>]`. Parse `text`, `end`, and error records. Mark native image false in process mode and `relayable_approvals=false`; do not use `--always-approve`.

- [ ] **Step 5: Implement Cursor**

Use `cursor-agent -p <prompt> --output-format stream-json [--model <model>] [--resume=<session-id>]` with the child working directory set to the profile cwd. Never pass `--force`. Parse assistant deltas, session IDs, result, and non-zero stderr. Mark native image false and relayable approvals false.

- [ ] **Step 6: Implement Pi**

Use `pi -p --mode json --tools read,grep,find,ls [--provider <provider-from-model>] [--model <model-name>] --session <state-session-path> [@<image-path> ...] <prompt>`. Split a configured `provider/model` value once at `/`; a model without `/` supplies only `--model`. Store session files under the Quick Chat state directory, not the profile working directory. Pi supports native images and JSON event streaming; never include `bash`, `edit`, or `write` in tools.

- [ ] **Step 7: Run six-adapter contract tests**

Run: `python3 -m unittest tests.test_adapters tests.test_engine -v`  
Expected: PASS for detection, models, sessions, images, unknown fields, degraded parsing, read-only enforcement, and forbidden flag absence across all six presets.

- [ ] **Step 8: Commit the remaining default adapters**

```bash
git add bridge/quick_chat/adapters tests/fixtures tests/test_adapters.py
git commit -m "feat: add OpenCode Grok Cursor and Pi adapters"
```

### Task 10: Add named profile editing and per-profile global shortcuts

**Files:**
- Create: `ShortcutDelegate.qml`
- Create: `bridge/quick_chat/shortcuts.py`
- Modify: `Service.qml`
- Modify: `models/ProfileModel.js`
- Modify: `ui/ProfileSettings.qml`
- Modify: `bridge/quick_chat/main.py`
- Create: `tests/fixtures/fake-hyprctl`
- Create: `tests/test_shortcuts.py`
- Modify: `test/qml-model-test.js`

**Interfaces:**
- Consumes: profile shortcut strings in normalized `MODIFIERS, KEY` form and `hyprctl -j binds`.
- Produces: immutable global targets `community.quick-chat:profile-<profile-id>`, live Hyprland `bindd` entries, conflict diagnostics, and menu payload `{profileId:<id>}`.

- [ ] **Step 1: Write failing shortcut normalization and conflict tests**

```python
def test_default_shortcut_is_super_alt_space(self):
    config = Config.default()
    self.assertEqual(config.default_shortcut, "SUPER ALT, SPACE")

def test_existing_foreign_binding_is_not_overwritten(self):
    result = sync_shortcuts(self.config, self.fake_hyprctl)
    self.assertEqual(result.conflicts[0].profile_id, "work")
    self.assertNotIn("keyword bindd", " ".join(self.calls))
```

- [ ] **Step 2: Run shortcut tests and verify they fail**

Run: `python3 -m unittest tests.test_shortcuts -v`  
Expected: FAIL because shortcut syncing does not exist.

- [ ] **Step 3: Implement shortcut parsing and safe live binding sync**

Accept uppercase modifiers from `{SUPER, ALT, CTRL, SHIFT}` and one Hyprland key token matching `[A-Z0-9_]+`. Read existing bindings with `hyprctl -j binds`. Refuse a chord owned by another command. Apply owned entries with `hyprctl keyword bindd "<mods>,<key>,Quick Chat: <profile>,global,community.quick-chat:profile-<id>"`; remove only previously recorded Quick Chat entries with the exact matching chord and target.

- [ ] **Step 4: Implement the keep-loaded shortcut service**

`Service.qml` imports `Quickshell.Hyprland`, loads profile shortcut targets through `ShortcutDelegate.qml`, and starts shortcut sync after delegates exist. Each delegate has immutable `appid: "community.quick-chat"`, `name: "profile-" + profileId`, and on press executes `omarchy-shell shell summon community.quick-chat <payload-json>` with an argument array.

- [ ] **Step 5: Implement profile CRUD and settings validation**

Profile settings cover name, icon, adapter, model, system instructions, working-directory strategy, fixed path, allowed context providers, permission policy, shortcut, history override, private default, and advanced adapter arguments. Duplicate creates a new stable ID with `-copy` plus a numeric suffix. Remove requires confirmation and leaves existing history readable with profile label `Deleted profile`.

- [ ] **Step 6: Refresh shortcut service after profile saves**

The config file is watched with `FileView.watchChanges`. On a valid reload, rebuild shortcut delegates, run `shortcuts sync`, and expose per-profile conflicts to the settings UI. Invalid config keeps the last valid delegates and displays the bridge validation error.

- [ ] **Step 7: Run shortcut, profile, and aggregate tests**

Run: `python3 -m unittest tests.test_shortcuts tests.test_storage -v && node test/qml-model-test.js && ./test/all`  
Expected: PASS for default shortcut, profile-specific targets, conflicts, duplicate IDs, removal confirmation, and invalid-config preservation.

- [ ] **Step 8: Commit profiles and keybindings**

```bash
git add Service.qml ShortcutDelegate.qml bridge/quick_chat models ui tests test
git commit -m "feat: add profile shortcuts and settings"
```

### Task 11: Add approval UI, custom commands, and recovery states

**Files:**
- Create: `bridge/quick_chat/adapters/custom.py`
- Create: `ui/ApprovalCard.qml`
- Modify: `bridge/quick_chat/engine.py`
- Modify: `bridge/quick_chat/protocol.py`
- Modify: `ui/ChatSurface.qml`
- Modify: `ui/InlineError.qml`
- Modify: `ui/ProfileSettings.qml`
- Create: `tests/fixtures/fake-approval-cli.py`
- Modify: `tests/test_adapters.py`
- Modify: `tests/test_engine.py`

**Interfaces:**
- Consumes: normalized `tool_request` with `{approvalId, title, operation, details}` and custom adapter `{executable, args, stdin, readOnlyArgs, output}`.
- Produces: approve-once/deny protocol responses, denial of unrelayable operations, typed custom placeholder expansion, and actionable recovery codes.

- [ ] **Step 1: Write failing approval and custom-template tests**

```python
def test_unrelayable_tool_request_is_denied(self):
    events = list(self.engine.handle(tool_request_from_adapter(relayable=False)))
    self.assertEqual(events[-1].data["code"], "approval_not_relayable")

def test_custom_arguments_are_individual_values(self):
    adapter = CustomAdapter(executable="ask", args=("--cwd", "{cwd}", "{prompt}"))
    call = adapter.start(context(prompt="$(touch nope)", cwd="/tmp/work"))
    self.assertEqual(call.argv, ("ask", "--cwd", "/tmp/work", "$(touch nope)"))
```

- [ ] **Step 2: Run approval tests and verify they fail**

Run: `python3 -m unittest tests.test_adapters tests.test_engine -v`  
Expected: FAIL because approval state and custom adapter are absent.

- [ ] **Step 3: Implement typed custom-command expansion**

Allowed whole-argument placeholders are `{prompt}`, `{cwd}`, `{model}`, `{session}`, and repeated `{attachments}`. Reject partial placeholders such as `--prompt={prompt}`, unknown names, an empty executable, and `shell`, redirection, or pipeline configuration. Custom adapters default to `read_only_enforced=false`; they may run only in Q&A mode unless the profile supplies explicit `readOnlyArgs`, which are appended as individual arguments.

- [ ] **Step 4: Implement generic approval state with deny-safe fallback**

When `relayable_approvals=true`, emit one `tool_request`, pause that adapter transport, and accept only a matching `approve` or `deny` request. Approval expires after 60 seconds and becomes Deny. When false, immediately deny, emit `approval_not_relayable`, and include a `continueCommand` argument array for opening the native CLI session in a terminal.

- [ ] **Step 5: Implement the visible approval card**

`ApprovalCard.qml` displays the adapter name, exact operation, working directory or target, and expandable details. Buttons are `Approve once` and `Deny`; there is no approve-always control. `Esc` while the card has focus denies the request before hiding the popup.

- [ ] **Step 6: Map recovery codes to exact actions**

Support `not_installed` (switch profile), `authentication_required` (copy login command), `unsupported_version` (refresh probe), `invalid_working_directory` (edit profile), `capture_failed` (send without context), `timeout` (retry), `bridge_exited` (restart bridge), `approval_not_relayable` (open terminal), and `history_recovered` (open quarantined path). No action executes a login or mutating command automatically.

- [ ] **Step 7: Run approval, custom, and recovery tests**

Run: `python3 -m unittest tests.test_adapters tests.test_engine -v && ./test/all`  
Expected: PASS for approve once, deny, timeout-to-deny, unrelayable denial, safe placeholder expansion, and every recovery code.

- [ ] **Step 8: Commit approvals and custom adapters**

```bash
git add bridge/quick_chat ui tests
git commit -m "feat: add safe approvals and custom adapters"
```

### Task 12: Finish installation documentation and Omarchy acceptance coverage

**Files:**
- Create: `README.md`
- Create: `docs/adapter-authoring.md`
- Create: `test/acceptance/quick-chat-test.sh`
- Modify: `test/all`
- Modify: `manifest.json`

**Interfaces:**
- Consumes: completed process-backed plugin and Omarchy third-party installation flow.
- Produces: release candidate `0.1.0`, reproducible install/use docs, and a disposable-desktop acceptance script.

- [ ] **Step 1: Write the acceptance script assertions**

```bash
#!/bin/bash
set -euo pipefail

PLUGIN_ID="community.quick-chat"
omarchy plugin add "$QUICK_CHAT_REPO" --enable --yes
omarchy-shell shell listPlugins | jq -e --arg id "$PLUGIN_ID" '.[] | select(.id == $id and .enabled == true)'
omarchy-shell shell summon "$PLUGIN_ID" '{"profileId":"codex"}'
wtype "Explain this window"
wtype -M ctrl -k Return -m ctrl
```

The disposable harness must take named screenshots for compact, attachment preview, streamed answer, approval card fixture, expanded settings, and error state; it must close the plugin and restore test-owned config in a trap.

- [ ] **Step 2: Run the non-graphical release suite**

Run: `./test/all`  
Expected: PASS for manifest, static QML, models, protocol, storage, process, adapters, context, shortcuts, and engine.

- [ ] **Step 3: Write README installation and operation sections**

Document local development installation with `omarchy plugin add file:///home/g2v/Projects/omarchy/omarchy-quick-chat --enable`, and document published installation using the exact URL returned by `git remote get-url origin` once a remote is configured. Cover default `SUPER+ALT+SPACE`, six preset prerequisites, profile creation, context previews, history/private behavior, CLI-native authentication, updating/removing, logs, and compatibility states. State plainly that plugins execute unsandboxed inside Omarchy shell and that process-mode approvals may require continuing in a terminal.

- [ ] **Step 4: Write adapter authoring documentation**

Document `detect`, `capabilities`, `start`, `resume`, `parse_event`, safe argv construction, fixture format, degraded mode, attachment behavior, session mapping, cancellation, and the rule that new adapters ship with `relayable_approvals=false` until a stable bidirectional protocol is tested.

- [ ] **Step 5: Validate plugin installation in a disposable Omarchy environment**

Run inside the disposable Omarchy guest after the harness mounts this repository: `QUICK_CHAT_REPO="file://$PWD" bash test/acceptance/quick-chat-test.sh`  
Expected: acceptance test passes and produces all named screenshots. The ISO harness must mount `/home/g2v/Projects/omarchy/omarchy-quick-chat` as the guest's current directory; do not build or alter the active desktop.

- [ ] **Step 6: Inspect every acceptance screenshot**

Verify no clipping, overlap, stale attachment, unreadable theme contrast, focus loss, or incorrect compact/expanded geometry. Record the inspected artifact directory in the implementation handoff.

- [ ] **Step 7: Commit the process-backed release candidate**

```bash
git add README.md docs/adapter-authoring.md test/acceptance test/all manifest.json
git commit -m "docs: prepare quick chat plugin release"
```

### Task 13: Add the planned persistent ACP transport

**Files:**
- Modify: `bridge/quick_chat/transports/base.py`
- Create: `bridge/quick_chat/transports/acp.py`
- Modify: `bridge/quick_chat/adapters/grok.py`
- Modify: `bridge/quick_chat/adapters/registry.py`
- Modify: `bridge/quick_chat/engine.py`
- Create: `tests/fixtures/fake_acp_agent.py`
- Create: `tests/test_acp.py`
- Create: `docs/acp-transport.md`

**Interfaces:**
- Consumes: ACP protocol version 1 over newline-delimited JSON-RPC 2.0 stdio, adapter command `grok agent stdio`, and the existing normalized bridge events.
- Produces: `AcpTransport`, negotiated capabilities, persistent session load/new, prompt updates, permission requests, cancellation, reconnect, and process fallback.

- [ ] **Step 1: Write failing ACP negotiation and reconnect tests**

```python
def test_acp_initializes_version_one_and_starts_session(self):
    transport = AcpTransport(self.fake_agent_argv)
    session = transport.open_session(Path("/tmp/project"), existing_id=None)
    self.assertEqual(transport.protocol_version, 1)
    self.assertEqual(session.id, "session-1")

def test_disconnect_reconnects_once_and_loads_session(self):
    session = self.transport.open_session(self.cwd, None)
    self.agent.disconnect()
    result = self.transport.prompt(session.id, [text_block("continue")], self.events.append)
    self.assertEqual(self.agent.loaded_session_id, session.id)
    self.assertEqual(result.stop_reason, "end_turn")
```

- [ ] **Step 2: Run ACP tests and verify they fail**

Run: `python3 -m unittest tests.test_acp -v`  
Expected: FAIL because `AcpTransport` does not exist.

- [ ] **Step 3: Implement JSON-RPC correlation and initialization**

Start the agent with `shell=False`, send `initialize` with `protocolVersion: 1` and client capabilities, correlate integer request IDs, route `session/update` notifications, and reject an incompatible negotiated version. Keep one ACP process per adapter executable/model tuple and close it after 10 idle minutes.

- [ ] **Step 4: Implement ACP session lifecycle and prompt content**

Use `session/new` with absolute `cwd` and `mcpServers: []`, or `session/load` for a mapped ID. Send `session/prompt` with text and approved image content blocks. Normalize agent message chunks to `text_delta`, tool-call updates to status, and the final `stopReason` to `complete` or `error`.

- [ ] **Step 5: Implement permission requests and cancellation**

Translate ACP client-side permission requests into existing `tool_request` events and return only the user's Approve Once or Deny outcome. On Stop, send `session/cancel` for the active session and wait for the prompt response with stop reason `cancelled` before terminating the process.

- [ ] **Step 6: Implement capability preference and safe fallback**

Registry prefers ACP only when the profile enables `transport: "auto"` and the adapter probe confirms a working ACP command. On initialization, protocol, or reconnect failure, emit a degraded status and use the process transport for the next turn; never replay a partially submitted prompt automatically.

- [ ] **Step 7: Add Grok ACP and adapter-neutral contract coverage**

Grok returns `grok agent stdio` as its ACP invocation. Test initialize, new/load, text/image prompt, session update, permission allow/deny, cancel, one reconnect, protocol mismatch, partial-stream disconnect, idle shutdown, and process fallback with the fake agent.

- [ ] **Step 8: Document the ACP lifecycle and run the full suite**

Run: `python3 -m unittest tests.test_acp -v && ./test/all`  
Expected: PASS for ACP contracts plus every process-backed regression test. `docs/acp-transport.md` must include the state machine `stopped -> initializing -> ready -> prompting -> ready`, with `reconnecting` and `failed` transitions.

- [ ] **Step 9: Commit ACP support**

```bash
git add bridge/quick_chat/transports bridge/quick_chat/adapters bridge/quick_chat/engine.py tests docs/acp-transport.md
git commit -m "feat: add persistent ACP transport"
```

### Task 14: Add configurable relative placement in the Omarchy root menu

**Dependency:** Omarchy's menu extension schema must first expose stable
relative ordering. The current merger fixes every stock item before every user
extension item and ignores `order`, `before`, and `after` metadata; Quick Chat
therefore remains the first custom root row without patching stock files.

**Files:**
- Upstream Omarchy: `shell/plugins/menu/MenuModel.js`
- Upstream Omarchy: root-menu schema documentation and tests
- Modify: `bridge/quick_chat/menu.py`
- Modify: `bridge/quick_chat/models.py`
- Modify: `ui/ProfileSettings.qml`
- Modify: `tests/test_menu.py`

- [ ] **Step 1: Add and upstream-test a relative-order contract**

Support `after: "apps"` and `before: <id>` for user extension rows while
preserving declaration order for rows without placement metadata. Missing or
hidden anchors fall back deterministically without dropping the extension row.

- [ ] **Step 2: Ask for placement on first run**

Offer After Apps (default), Top, and Bottom. Persist the choice in Quick Chat's
global configuration; never edit or reorder unrelated user entries.

- [ ] **Step 3: Apply placement idempotently**

Write only Quick Chat's namespaced root entry, update its placement metadata
when the preference changes, preserve comments and custom fields, and hot-refresh
`omarchy.menu`.

- [ ] **Step 4: Keep a compatibility fallback**

Detect shells without the relative-order contract and install Quick Chat as the
first custom root row. Show the limitation next to the placement setting rather
than modifying `/usr/share/omarchy`.

- [ ] **Step 5: Verify all placement modes**

Test After Apps, Top, Bottom, a missing anchor, disabled-plugin visibility,
idempotent reinstall, user-customized rows, and upgrade from the current entry.

## Final Verification

- [ ] Run `./test/all` and confirm every non-graphical suite passes.
- [ ] Run `git status --short` and confirm only intentional acceptance artifacts, if any, remain untracked.
- [ ] Verify `manifest.json` parses and version remains `0.1.0` until release tagging.
- [ ] Inspect the disposable Omarchy screenshots and record their absolute artifact directory.
- [ ] Confirm a private image conversation leaves no history entry, session mapping, or capture file.
- [ ] Confirm all six process adapters contain no forbidden approval-bypass flag.
- [ ] Confirm the ACP transport falls back without replaying a partial prompt.
