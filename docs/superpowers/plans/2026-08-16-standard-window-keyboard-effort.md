# Quick Chat Standard Window, Keyboard Control, and Thinking Effort Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Quick Chat into a theme-native standard Omarchy window, make every chat action keyboard-operable and configurable, add model-aware thinking-effort controls, and prove all six default CLI harnesses with real read-only prompts.

**Architecture:** Keep the existing QML-to-Python JSONL bridge and six process adapters. Replace the layer-shell `PanelWindow` with one Quickshell `FloatingWindow`; bind it to its exact Hyprland toplevel address for one-shot initial placement and address-scoped maximize/restore, then leave layout ownership to the compositor. Upgrade configuration to schema version 2, with Python as the persistence authority and mirrored pure-JavaScript projections for immediate UI feedback. Carry effort metadata from adapter/model discovery through the bridge into one adjacent effort picker, and validate a saved effort again before constructing any process invocation.

**Tech Stack:** Omarchy Quattro plugin manifest, Qt 6 QML, Quickshell `FloatingWindow`, Quickshell Hyprland IPC, Omarchy `qs.Commons`/`qs.Ui`, Python 3.12 standard library, Node.js pure-model tests, Bash acceptance runners, Hyprland IPC.

## Global Constraints

- Follow the approved design in `docs/superpowers/specs/2026-08-16-standard-window-keyboard-effort-design.md`.
- Run every repository command through `rtk`; do not invoke shell commands without the `rtk` prefix.
- Use test-driven development for every production change: add one focused failing assertion, run it and observe the expected failure, add the smallest implementation, then run the focused test and the broader suite.
- Preserve the plugin id `community.quick-chat`, existing menu integration, six default profiles, 20-item default history, unlimited history via `null`, private-mode non-persistence, explicit approval cards, and read-only adapter behavior.
- Preserve existing per-profile global summon shortcuts during migration. Fresh schema-2 configs use `SUPER ALT, C`, which is free in the inspected Omarchy bind set; the legacy `SUPER ALT, SPACE` value collides with Omarchy's Apps menu and is reported for existing users instead of being silently rewritten.
- Never add a layer-shell keyboard grab, background overlay, QML opacity override, persistent Hyprland float rule, always-on-top rule, or page-driven resize.
- Never synthesize an effort choice. A choice must come from explicit CLI help, an explicit model-catalog field, or an explicit variant/parameter in a discovered model row.
- A non-null effort is accepted only if it is syntactically safe and present in the active adapter/model catalog at invocation time.
- Keep prompts, model ids, effort ids, paths, and shortcuts as structured values. Subprocesses continue to use argument arrays with `shell=False`.
- Cursor process mode always includes `--mode ask`; no adapter gains force, auto-approve, yolo, bypass, or equivalent behavior.
- The installed plugin is updated only after the repository suite passes. Back up the user config before active-desktop acceptance and restore it if acceptance changes fixture data.
- A live harness is successful only when its real executable, authentication, model discovery, normalized `QUICK_CHAT_OK` text, and terminal completion all succeed. Missing or unauthenticated harnesses are failures, not skips.
- Use two-space indentation in QML, JavaScript, JSON, and Bash; use four-space indentation in Python.

---

### Task 1: Migrate configuration to schema version 2

**Files:**
- Modify: `bridge/quick_chat/models.py`
- Modify: `bridge/quick_chat/storage.py`
- Modify: `models/ProfileModel.js`
- Modify: `Service.qml`
- Modify: `tests/test_models.py`
- Modify: `tests/test_storage.py`
- Modify: `test/qml-model-test.js`

**Interfaces:**
- Produces `DEFAULT_UI_SHORTCUTS: Mapping[str, str]` with the seven action defaults.
- Produces `canonicalize_ui_shortcut(value: object) -> str` and `validate_ui_shortcuts(value: object) -> dict[str, str]`.
- Adds `Profile.thinking_effort: str | None`, serialized as `thinkingEffort`.
- Makes `Config.schema_version` equal to `2` and adds `Config.ui_shortcuts`, serialized as `uiShortcuts`.
- Changes only the fresh-config global summon default to `SUPER ALT, C`; explicit schema-1 `defaultShortcut` and profile `shortcut` values remain byte-for-byte unchanged.
- `Config.from_dict()` accepts schema 1 or 2 and always returns an in-memory schema-2 `Config`.
- `ConfigStore.load()` atomically rewrites a valid schema-1 file as schema 2 after loading it.

- [ ] **Step 1: Add failing Python schema and validation tests**

Add these cases to `tests/test_models.py`:

```python
def test_v1_config_migrates_without_losing_user_values(self):
    legacy = Config.default().to_dict()
    legacy["schemaVersion"] = 1
    legacy.pop("uiShortcuts", None)
    legacy["defaultShortcut"] = "SUPER ALT, SPACE"
    legacy["selectedProfileId"] = "claude"
    legacy["historyLimit"] = None
    legacy["profiles"][1]["model"] = "opus"

    migrated = Config.from_dict(legacy)

    self.assertEqual(migrated.schema_version, 2)
    self.assertEqual(migrated.selected_profile_id, "claude")
    self.assertIsNone(migrated.history_limit)
    self.assertEqual(migrated.default_shortcut, "SUPER ALT, SPACE")
    self.assertEqual(migrated.profile("claude").model, "opus")
    self.assertIsNone(migrated.profile("claude").thinking_effort)
    self.assertEqual(migrated.ui_shortcuts["model"], "Ctrl+K")

def test_ui_shortcuts_are_canonical_unique_and_not_reserved(self):
    config = Config.default().to_dict()
    config["uiShortcuts"]["private"] = "control+shift+p"
    parsed = Config.from_dict(config)
    self.assertEqual(parsed.ui_shortcuts["private"], "Ctrl+Shift+P")

    for value in ("Ctrl", "Enter", "Ctrl+Enter", "Escape", "Alt+Left", "Tab"):
        invalid = Config.default().to_dict()
        invalid["uiShortcuts"]["model"] = value
        with self.subTest(value=value), self.assertRaises(ValueError):
            Config.from_dict(invalid)

    duplicate = Config.default().to_dict()
    duplicate["uiShortcuts"]["history"] = duplicate["uiShortcuts"]["model"]
    with self.assertRaises(ValueError):
        Config.from_dict(duplicate)
```

Add to `tests/test_storage.py`:

```python
def test_loading_v1_config_persists_one_time_v2_migration(self):
    legacy = Config.default().to_dict()
    legacy["schemaVersion"] = 1
    legacy.pop("uiShortcuts", None)
    for profile in legacy["profiles"]:
        profile.pop("thinkingEffort", None)
    atomic_write_json(self.paths.config_file, legacy)

    loaded = ConfigStore(self.paths).load()
    persisted = json.loads(self.paths.config_file.read_text())

    self.assertEqual(loaded.schema_version, 2)
    self.assertEqual(persisted["schemaVersion"], 2)
    self.assertIn("uiShortcuts", persisted)
    self.assertTrue(all("thinkingEffort" in item for item in persisted["profiles"]))
```

- [ ] **Step 2: Add failing JavaScript migration tests**

Append to `test/qml-model-test.js`:

```javascript
const migratedProfiles = ProfileModel.normalize({
  schemaVersion: 1,
  selectedProfileId: "work",
  historyLimit: 20,
  profiles: [{ id: "work", name: "Work", adapterId: "codex" }]
})
assert.equal(migratedProfiles.schemaVersion, 2)
assert.equal(migratedProfiles.profiles[0].thinkingEffort, null)
assert.equal(migratedProfiles.uiShortcuts.effort, "Ctrl+.")
assert.equal(
  ProfileModel.setUiShortcut(migratedProfiles, "private", "control+shift+p")
    .uiShortcuts.private,
  "Ctrl+Shift+P"
)
assert.throws(() => ProfileModel.setUiShortcut(migratedProfiles, "model", "Enter"))
assert.throws(() => ProfileModel.setUiShortcut(migratedProfiles, "history", "Ctrl+K"))
```

- [ ] **Step 3: Run the focused tests and observe schema-1 failures**

Run: `rtk python3 -m unittest tests.test_models tests.test_storage -v`
Expected: FAIL because schema 1 is rejected and schema-2 fields do not exist.

Run: `rtk node test/qml-model-test.js`
Expected: FAIL because `uiShortcuts`, `thinkingEffort`, and `setUiShortcut` do not exist.

- [ ] **Step 4: Implement strict schema-2 records and migration**

Use these constants and validators in `bridge/quick_chat/models.py`:

```python
UI_SHORTCUT_ACTIONS = (
    "focusInput", "model", "effort", "history", "settings", "private", "newChat",
)
DEFAULT_UI_SHORTCUTS = {
    "focusInput": "Ctrl+L",
    "model": "Ctrl+K",
    "effort": "Ctrl+.",
    "history": "Ctrl+H",
    "settings": "Ctrl+,",
    "private": "Ctrl+Shift+P",
    "newChat": "Ctrl+N",
}
RESERVED_UI_SHORTCUTS = {
    "Enter", "Ctrl+Enter", "Escape", "Alt+Left", "Tab", "Shift+Tab",
}
EFFORT_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}\\Z")

def validate_thinking_effort(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not EFFORT_ID_PATTERN.fullmatch(value):
        raise ValueError("thinking effort has an invalid format")
    return value
```

`canonicalize_ui_shortcut` must normalize modifier aliases and order to `Ctrl`, `Alt`, `Shift`, `Meta`, preserve one non-modifier key, and reject empty or modifier-only sequences. `validate_ui_shortcuts` must require exactly the seven action keys, reject reserved sequences and duplicates after canonicalization, and return a fresh dictionary.

Change the dataclasses to this shape:

```python
@dataclass(frozen=True)
class Profile:
    # existing fields remain unchanged
    thinking_effort: str | None = None

@dataclass(frozen=True)
class Config:
    schema_version: int = 2
    profiles: tuple[Profile, ...] = DEFAULT_PROFILES
    selected_profile_id: str = "codex"
    history_limit: int | None = 20
    default_shortcut: str = "SUPER ALT, C"
    ui_shortcuts: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_UI_SHORTCUTS)
    )
```

Use `default_shortcut="SUPER ALT, C"` in the schema-2 dataclass. While parsing a version-1 object, the absent-field fallback remains `SUPER ALT, SPACE`; while parsing version 2, it is `SUPER ALT, C`. Update the default-config assertion and Service's pre-load fallback to `SUPER ALT, C`.

`Config.from_dict` must inspect `schemaVersion` before construction. Version 1 injects default shortcuts and null effort values; version 2 validates supplied values; any other version raises. In `ConfigStore.load`, retain the decoded version and call `self.save(config)` only after a valid version-1 decode.

- [ ] **Step 5: Mirror normalization in the QML model and service**

`ProfileModel.normalize` must clone every profile with `thinkingEffort: null` when absent, return `schemaVersion: 2`, and canonicalize/validate `uiShortcuts`. `serialize` always emits schema 2. `Service.loadConfig` accepts versions 1 and 2 so the shortcut service does not reject the file during the migration write.

- [ ] **Step 6: Run focused and aggregate tests**

Run: `rtk python3 -m unittest tests.test_models tests.test_storage -v`
Expected: PASS for migration, preservation, canonicalization, reserved sequences, duplicates, and atomic rewrite.

Run: `rtk node test/qml-model-test.js`
Expected: PASS for mirrored migration and shortcut validation.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 7: Commit schema version 2**

```bash
rtk git add bridge/quick_chat/models.py bridge/quick_chat/storage.py models/ProfileModel.js Service.qml tests/test_models.py tests/test_storage.py test/qml-model-test.js
rtk git commit -m "feat: migrate quick chat config to schema v2"
```

---

### Task 2: Carry model-aware effort metadata through the bridge

**Files:**
- Modify: `bridge/quick_chat/adapters/base.py`
- Modify: `bridge/quick_chat/adapters/process_base.py`
- Modify: `bridge/quick_chat/adapters/registry.py`
- Modify: `bridge/quick_chat/model_discovery.py`
- Modify: `bridge/quick_chat/main.py`
- Modify: `bridge/quick_chat/engine.py`
- Modify: `tests/test_adapters.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_protocol.py`

**Interfaces:**
- Adds immutable `EffortOption(id, label, description)` with `to_dict()`.
- Extends `ModelOption` with `efforts: tuple[EffortOption, ...] | None` and `is_default: bool`.
- Extends `Capabilities` with `thinking_effort: bool = False`.
- Extends `AdapterContext` with `thinking_effort: str | None = None`.
- Adds `Adapter.effort_options(cwd=None) -> tuple[EffortOption, ...]`.
- Adds `AdapterRegistry.efforts(adapter_id, model, cwd) -> tuple[EffortOption, ...]`.
- A model `efforts=None` means “use the adapter-level catalog”; an empty tuple means “this model explicitly advertises no effort control.”

- [ ] **Step 1: Add failing metadata and engine-validation tests**

Update the mocked Codex row in `tests/test_adapters.py`:

```python
{
    "model": "gpt-5.6-sol",
    "displayName": "GPT-5.6 Sol",
    "description": "Fast coding model",
    "hidden": False,
    "isDefault": True,
    "supportedReasoningEfforts": [
        {"reasoningEffort": "low", "description": "Faster"},
        {"reasoningEffort": "high", "description": "Deeper"},
    ],
    "defaultReasoningEffort": "high",
}
```

Then assert:

```python
self.assertTrue(models[0].is_default)
self.assertEqual([item.id for item in models[0].efforts], ["low", "high"])
self.assertEqual(models[0].to_dict()["efforts"][1]["description"], "Deeper")
```

In `tests/test_engine.py`, construct a registry whose adapter exposes only `low` and assert a profile containing `thinking_effort="made-up"` yields one `unsupported_effort` error before the transport runs. Add a second case where `low` reaches `AdapterContext.thinking_effort`.

- [ ] **Step 2: Run the focused tests and observe missing-type failures**

Run: `rtk python3 -m unittest tests.test_adapters tests.test_engine tests.test_protocol -v`
Expected: FAIL because effort metadata, capabilities, registry resolution, and context propagation are absent.

- [ ] **Step 3: Define the metadata contracts**

Implement in `bridge/quick_chat/adapters/base.py`:

```python
@dataclass(frozen=True)
class EffortOption:
    id: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        validate_thinking_effort(self.id)
        if not self.label.strip():
            raise ValueError("effort label must be non-empty")

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "description": self.description}

@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    description: str = ""
    efforts: tuple[EffortOption, ...] | None = None
    is_default: bool = False
```

`ModelOption.to_dict()` returns `efforts: null` for adapter fallback or a serialized list for model-specific metadata, plus `isDefault`. Append `thinking_effort: bool = False` to `Capabilities` so existing positional test adapters remain source compatible. Add `thinking_effort` to `AdapterContext` after existing defaulted fields.

- [ ] **Step 4: Preserve Codex model metadata exactly**

In `discover_codex_models`, read `supportedReasoningEfforts` only when it is a list of objects with safe non-empty `reasoningEffort` ids. Preserve descriptions and `isDefault`; do not substitute the old generic Codex effort list when the server returns an empty list.

- [ ] **Step 5: Resolve and validate effective choices in the registry and engine**

`ProcessAdapterBase` gets `_effort_options = ()` and returns a tuple copy from `effort_options`. `AdapterRegistry.efforts` resolves an exact configured model, or the discovered `is_default` model when `model is None`; explicit model metadata wins, otherwise it returns adapter-level choices.

Before creating `AdapterContext`, `Engine.handle` must do:

```python
if profile.thinking_effort is not None:
    efforts = self.registry.efforts(profile.adapter_id, profile.model, cwd)
    if profile.thinking_effort not in {item.id for item in efforts}:
        yield Event("error", request.request_id, {
            "code": "unsupported_effort",
            "message": "The saved thinking effort is not supported by this model.",
            "resetTo": None,
        })
        return
```

For `adapter_id == "custom"`, any non-null effort yields the same `unsupported_effort` event without asking the registry for an unregistered built-in adapter. Adapter-state serialization uses `getattr(adapter, "effort_options", lambda _cwd=None: ())` so existing test doubles and future adapters safely advertise no choices until they implement the contract.

Then pass `thinking_effort=profile.thinking_effort` to `AdapterContext`. The `profiles` bridge response serializes adapter-level `efforts`; `models.list` carries model-level metadata through `ModelOption.to_dict()`.

- [ ] **Step 6: Run the focused and full suites**

Run: `rtk python3 -m unittest tests.test_adapters tests.test_engine tests.test_protocol -v`
Expected: PASS, including exact Codex effort metadata and rejection before transport.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 7: Commit the effort bridge contract**

```bash
rtk git add bridge/quick_chat/adapters bridge/quick_chat/model_discovery.py bridge/quick_chat/main.py bridge/quick_chat/engine.py tests/test_adapters.py tests/test_engine.py tests/test_protocol.py
rtk git commit -m "feat: carry model effort metadata through bridge"
```

---

### Task 3: Map effort safely into all six harnesses

**Files:**
- Modify: `bridge/quick_chat/model_discovery.py`
- Modify: `bridge/quick_chat/adapters/codex.py`
- Modify: `bridge/quick_chat/adapters/claude.py`
- Modify: `bridge/quick_chat/adapters/opencode.py`
- Modify: `bridge/quick_chat/adapters/grok.py`
- Modify: `bridge/quick_chat/adapters/cursor.py`
- Modify: `bridge/quick_chat/adapters/pi.py`
- Modify: `tests/test_adapters.py`

**Interfaces:**
- Produces `discover_help_efforts(argv, flag, cwd=None) -> tuple[EffortOption, ...]`, accepting only values explicitly listed next to that flag.
- Produces `merge_cursor_effort(model: str, effort: str) -> str`, preserving every non-effort bracket parameter and replacing at most one effort entry.
- Every built-in `start()` translates `AdapterContext.thinking_effort` into its native distinct argv value.

- [ ] **Step 1: Write failing exact-argv tests**

Add to `tests/test_adapters.py`:

```python
def test_each_adapter_maps_native_thinking_effort(self):
    cases = (
        (CodexAdapter(), context(thinking_effort="high"),
         ("-c", 'model_reasoning_effort="high"')),
        (ClaudeAdapter(), context(thinking_effort="high"), ("--effort", "high")),
        (OpenCodeAdapter(), context(thinking_effort="high"), ("--variant", "high")),
        (GrokAdapter(), context(thinking_effort="high"),
         ("--reasoning-effort", "high")),
        (PiAdapter(), context(thinking_effort="high"), ("--thinking", "high")),
    )
    for adapter, adapter_context, pair in cases:
        with self.subTest(adapter=adapter.id):
            self.assertIn(pair, adjacent_pairs(adapter.start(adapter_context).argv))

def test_codex_config_override_precedes_exec(self):
    argv = CodexAdapter().start(context(thinking_effort="high")).argv
    self.assertEqual(argv[:4], (
        "codex", "-c", 'model_reasoning_effort="high"', "exec",
    ))

def test_cursor_is_ask_only_and_merges_model_parameters(self):
    call = CursorAdapter().start(context(
        model="claude-opus-4-8[context=1m,fast=false]",
        thinking_effort="high",
    ))
    self.assertIn(("--mode", "ask"), adjacent_pairs(call.argv))
    self.assertIn((
        "--model", "claude-opus-4-8[context=1m,fast=false,effort=high]",
    ), adjacent_pairs(call.argv))
    self.assertNotIn("--force", call.argv)
    self.assertNotIn("--yolo", call.argv)

def test_cursor_effort_replaces_only_existing_effort(self):
    self.assertEqual(
        merge_cursor_effort("model[effort=low,context=1m]", "high"),
        "model[effort=high,context=1m]",
    )
```

Extend the local `context()` helper with `thinking_effort=None` and pass it to `AdapterContext`.

- [ ] **Step 2: Add failing discovery-source tests**

Mock explicit help output for Claude and Pi and assert only the listed values are returned. Add catalog fixtures where OpenCode explicitly prints `variants: low, high` under a model and Cursor returns parameterized model rows. Assert a Grok help response containing only `--reasoning-effort <EFFORT>` produces no selectable choices because it provides no enum.

- [ ] **Step 3: Run adapter tests and observe missing mapping failures**

Run: `rtk python3 -m unittest tests.test_adapters -v`
Expected: FAIL on all six effort mappings, Cursor Ask mode, parameter merging, and discovery metadata.

- [ ] **Step 4: Implement native argv translations**

- Codex builds `arguments = ["codex"]`, appends `("-c", f'model_reasoning_effort="{effort}"')`, then appends `"exec"` and its existing read-only flags.
- Claude appends `("--effort", effort)` while retaining plan mode and mutation-tool denials.
- OpenCode appends `("--variant", effort)` while retaining JSON output and no auto flag.
- Grok appends `("--reasoning-effort", effort)` while retaining its read-only tool allowlist.
- Cursor always appends `("--mode", "ask")`. A non-null effort requires a non-null model and passes the result of `merge_cursor_effort` to `--model`.
- Pi appends `("--thinking", effort)` while retaining `read,grep,find,ls`.

`merge_cursor_effort` rejects malformed or nested brackets, splits only the final bracket block, preserves parameter order, replaces an existing `effort=...` in place, and otherwise appends it.

- [ ] **Step 5: Implement explicit discovery sources**

`discover_help_efforts` runs the existing safe `_run` path and extracts comma-separated values only from explicit `choices`, `possible values`, or `Set thinking level:` text associated with the requested flag. Claude and Pi use it as adapter-level choices. OpenCode attaches explicit `variants:` rows to the preceding model. Cursor turns explicitly parameterized discovered rows into effort metadata without inventing additional values. Codex retains its app-server metadata. Grok returns no UI choices until its installed CLI or model response explicitly lists them, while its native mapping remains covered and ready.

- [ ] **Step 6: Re-run safety and aggregate tests**

Run: `rtk python3 -m unittest tests.test_adapters -v`
Expected: PASS for exact argv order, Ask mode, explicit discovery, and existing read-only/stream fixtures.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 7: Commit six-harness effort support**

```bash
rtk git add bridge/quick_chat/model_discovery.py bridge/quick_chat/adapters tests/test_adapters.py
rtk git commit -m "feat: map thinking effort across harnesses"
```

---

### Task 4: Add the adjacent thinking-effort picker

**Files:**
- Create: `models/EffortModel.js`
- Create: `ui/ThinkingEffortPicker.qml`
- Modify: `ui/Composer.qml`
- Modify: `ui/ChatSurface.qml`
- Modify: `ui/ProfileSettings.qml`
- Modify: `test/qml-model-test.js`
- Modify: `test/qml-static-test.sh`

**Interfaces:**
- `EffortModel.choices(profile, adapterStates, catalogs) -> array` returns only active model/adapter choices.
- `EffortModel.reconcile(value, choices) -> { value, reset }` resets unsupported non-null values to `null`.
- `ThinkingEffortPicker.open()`, `close()`, `focusTrigger()`, `popupOpen`, and `selectionRequested(string|null)`.
- `Composer.openEffortPicker()` and `effortSelected(string|null)`.
- `ChatSurface.selectThinkingEffort(value)` persists the profile-level value.

- [ ] **Step 1: Add failing pure-model tests**

Append to `test/qml-model-test.js`:

```javascript
const EffortModel = require("../models/EffortModel.js")
const effortProfile = {
  id: "codex", adapterId: "codex", model: "gpt-5.6-sol", thinkingEffort: "high"
}
const effortCatalogs = {
  codex: [{
    id: "gpt-5.6-sol", isDefault: true,
    efforts: [{ id: "low", label: "Low" }, { id: "high", label: "High" }]
  }]
}
assert.deepEqual(
  EffortModel.choices(effortProfile, [], effortCatalogs).map(item => item.id),
  ["low", "high"]
)
assert.deepEqual(
  EffortModel.reconcile("xhigh", EffortModel.choices(effortProfile, [], effortCatalogs)),
  { value: null, reset: true }
)
assert.deepEqual(EffortModel.rows("high", [
  { id: "low", label: "Low" }, { id: "high", label: "High" }
]).map(row => row.id), [null, "low", "high"])
```

- [ ] **Step 2: Add failing QML structure assertions**

In `test/qml-static-test.sh`, require `ThinkingEffortPicker` immediately after `HarnessModelPicker` in `Composer.qml`, require a disabled Default state when no choices exist, require a non-modal anchored `QQC.Popup`, and assert `ProfileSettings.values()` serializes `thinkingEffort`.

- [ ] **Step 3: Run QML tests and observe missing-component failures**

Run: `rtk node test/qml-model-test.js`
Expected: FAIL because `EffortModel.js` does not exist.

Run: `rtk bash test/qml-static-test.sh`
Expected: FAIL because the effort picker and profile field do not exist.

- [ ] **Step 4: Implement the pure effort projection**

`EffortModel.choices` chooses the exact profile model; when the profile uses the CLI default, it chooses the `isDefault` row. A model `efforts` array takes precedence. When model effort metadata is `null`, use `adapterStates[].efforts`. Return cloned, safe rows. `rows` always prepends `{ id: null, label: "Default" }` when the control is supported.

- [ ] **Step 5: Implement the theme-native picker**

Build `ThinkingEffortPicker.qml` from `BorderSurface`, `CursorSurface`, `PanelToolTip`, and `QQC.Popup`, using only `Color`, `Style`, and `Border` tokens. It must:

- show `Default` or the selected native label;
- remain a disabled Default indicator with an explanatory tooltip when choices are empty;
- open upward beside the composer;
- support Up/Down, Home/End, Enter, Space, and Escape;
- expose visible latency/usage help text; and
- use one vertical list scrollbar only when content exceeds its bounded height.

- [ ] **Step 6: Wire selection, reconciliation, and settings**

After profiles load, request the active adapter catalog asynchronously so the effort button populates without blocking composer focus. On model/profile changes, call `EffortModel.reconcile`; if `reset` is true, persist `thinkingEffort: null` and show a short inline status explaining that the previous level was unsupported. `ProfileSettings` loads, edits, and saves the same field using the currently discovered choices.

- [ ] **Step 7: Run QML and full tests**

Run: `rtk node test/qml-model-test.js`
Expected: PASS for model-specific, adapter fallback, Default, and reset behavior.

Run: `rtk bash test/qml-static-test.sh`
Expected: PASS for adjacency, theme tokens, keyboard support, and serialization.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 8: Commit the effort selector**

```bash
rtk git add models/EffortModel.js ui/ThinkingEffortPicker.qml ui/Composer.qml ui/ChatSurface.qml ui/ProfileSettings.qml test/qml-model-test.js test/qml-static-test.sh
rtk git commit -m "feat: add model-aware effort picker"
```

---

### Task 5: Replace the overlay with one standard desktop window

**Files:**
- Modify: `QuickChat.qml`
- Modify: `ui/ChatHeader.qml`
- Modify: `ui/ChatSurface.qml`
- Modify: `test/qml-static-test.sh`
- Modify: `test/acceptance/quick-chat-test.sh`

**Interfaces:**
- `QuickChat.open(payloadJson)` increments `openingGeneration`, shows the window, and begins one bounded placement/focus handshake.
- `QuickChat.requestClose()` is the user-close path; `close()` remains the host-close path.
- `QuickChat.startHeaderMove()` delegates to `FloatingWindow.startSystemMove()`.
- `QuickChat.toggleMaximized()` dispatches address-scoped Hyprland maximized/normal state.
- `ChatHeader` emits `moveRequested()` and `maximizeRequested()` and consumes `maximized` for its icon and tooltip.

- [ ] **Step 1: Replace stale overlay assertions with failing window assertions**

Update `test/qml-static-test.sh` to require:

```python
assert "FloatingWindow {" in menu
assert "PanelWindow {" not in menu
assert "Quickshell.Wayland" not in menu
assert "WlrLayershell" not in menu
assert "WlrKeyboardFocus" not in menu
assert "opacity:" not in menu
assert 'title: "Quick Chat"' in menu
assert "implicitWidth: Style.space(620)" in menu
assert "implicitHeight: Style.space(620)" in menu
assert "minimumSize: Qt.size(" in menu
assert 'Hyprland.dispatch("setfloating address:"' in menu
assert 'Hyprland.dispatch("fullscreenstate "' in menu
assert "startSystemMove()" in menu
assert "property bool expanded" not in menu
assert "expandRequested" not in chat_surface
```

Also assert page opening contains no dispatch, size, maximize, or expand call.

- [ ] **Step 2: Run the static test and observe overlay failures**

Run: `rtk bash test/qml-static-test.sh`
Expected: FAIL because `QuickChat.qml` still uses `PanelWindow`, Wlr focus priming, and pseudo-expansion.

- [ ] **Step 3: Implement first-party-style `FloatingWindow` lifecycle**

Follow the host lifecycle used by Omarchy's dev-gallery window:

```qml
property bool closingFromHost: false
property int openingGeneration: 0
property int placedGeneration: -1
property bool focusPending: false
property var quickToplevel: null

function open(payloadJson) {
  openingGeneration += 1
  placedGeneration = -1
  focusPending = true
  window.visible = true
  Hyprland.refreshToplevels()
  placementTimeout.restart()
  Qt.callLater(tryBindToplevel)
}

function close() {
  closingFromHost = true
  window.visible = false
  closingFromHost = false
}

function requestClose() {
  if (shell && typeof shell.hide === "function")
    shell.hide((manifest && manifest.id) || "community.quick-chat")
  else
    window.visible = false
}
```

The window is:

```qml
FloatingWindow {
  id: window
  title: "Quick Chat"
  color: Color.popups.background
  implicitWidth: Style.space(620)
  implicitHeight: Style.space(620)
  minimumSize: Qt.size(Style.space(480), Style.space(520))
}
```

Do not bind `opacity`, `maximized`, or `fullscreen` on the QML window.

- [ ] **Step 4: Implement exact-address placement and bounded focus**

`tryBindToplevel` searches `Hyprland.toplevels.values` for title exactly equal to `Quick Chat`, prefers the newly active match, and records only a non-empty address. For the current generation only, dispatch:

```qml
Hyprland.dispatch("setfloating address:" + quickToplevel.address)
Hyprland.dispatch("resizewindowpixel exact 620 620,address:" + quickToplevel.address)
Hyprland.dispatch("centerwindow 1,address:" + quickToplevel.address)
```

Mark the generation placed immediately so later Hyprland updates cannot refloat it. If matching times out, stop without dispatching to another window. Activate once through `quickToplevel.wayland.activate()`. Only after the toplevel reports activated, call `chat.focusComposer()` on the next QML turn and clear `focusPending`. A short retry timer may run only while `focusPending` is true and the placement timeout is active.

- [ ] **Step 5: Implement real header drag and maximize state**

The unused identity/header region owns a `MouseArea` whose press calls `moveRequested` and whose double click calls `maximizeRequested`. It must not cover private, history, settings, or maximize buttons. `QuickChat.toggleMaximized` uses:

```qml
var target = quickToplevel.address
var next = isMaximized ? "0 0," : "1 1,"
Hyprland.dispatch("fullscreenstate " + next + "address:" + target)
```

Derive `isMaximized` from `Number(quickToplevel.lastIpcObject.fullscreen) === 1`, so Super+Alt+F and the header button remain synchronized. Header drag calls `window.startSystemMove()`.

- [ ] **Step 6: Remove pseudo-expansion and page resize coupling**

Delete `expanded`, `requestedWidth`, `requestedHeight`, `focusPrimed`, the Wlr focus timer, the expand icon, and `expandRequested`. `ChatSurface.openPage` changes only `activePage` and deferred focus. Acceptance fixtures for History and Settings no longer alter window size.

- [ ] **Step 7: Run QML and aggregate tests**

Run: `rtk bash test/qml-static-test.sh`
Expected: PASS for `FloatingWindow`, no overlay/focus grab/opacity override, exact-address placement, drag, real maximize, and geometry-independent pages.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 8: Commit the standard window**

```bash
rtk git add QuickChat.qml ui/ChatHeader.qml ui/ChatSurface.qml test/qml-static-test.sh test/acceptance/quick-chat-test.sh
rtk git commit -m "feat: make quick chat a standard window"
```

---

### Task 6: Add configurable window shortcuts and complete keyboard navigation

**Files:**
- Create: `ui/WindowShortcuts.qml`
- Create: `ui/ShortcutCapture.qml`
- Create: `ui/ShortcutEditor.qml`
- Modify: `models/ProfileModel.js`
- Modify: `QuickChat.qml`
- Modify: `ui/ChatSurface.qml`
- Modify: `ui/Composer.qml`
- Modify: `ui/HarnessModelPicker.qml`
- Modify: `ui/HistoryDrawer.qml`
- Modify: `ui/ProfileSettings.qml`
- Modify: `ui/ChatHeader.qml`
- Modify: `test/qml-model-test.js`
- Modify: `test/qml-static-test.sh`

**Interfaces:**
- `WindowShortcuts` exposes seven sequences and signals: `focusInputRequested`, `modelRequested`, `effortRequested`, `historyRequested`, `settingsRequested`, `privateRequested`, and `newChatRequested`.
- `ShortcutCapture.sequenceCaptured(string)` converts one key chord to canonical Qt-style text.
- `ShortcutEditor.shortcutsChanged(var)` emits one validated seven-action map and supports reset defaults.
- `ChatSurface.handleBack() -> bool` closes a subpage or transient and reports whether it consumed the key.
- `ChatSurface.hasBlockingTransient` prevents action shortcuts from firing through dialogs.

- [ ] **Step 1: Add failing shortcut wiring and precedence assertions**

Extend `test/qml-static-test.sh` to assert exactly one `Shortcut` exists for each of the seven actions, every sequence comes from `profileState.uiShortcuts`, and the defaults appear in settings labels/tooltips. Assert fixed Enter/Ctrl+Enter behavior remains in `Composer`, while Escape and Alt+Left are handled after focused popups/items.

Add pure-model cases verifying reset defaults and atomic multi-shortcut validation:

```javascript
const resetShortcuts = ProfileModel.resetUiShortcuts(migratedProfiles)
assert.deepEqual(resetShortcuts.uiShortcuts, ProfileModel.defaultUiShortcuts())
assert.throws(() => ProfileModel.setUiShortcuts(migratedProfiles, {
  focusInput: "Ctrl+L", model: "Ctrl+K", effort: "Ctrl+.",
  history: "Ctrl+K", settings: "Ctrl+,", private: "Ctrl+Shift+P", newChat: "Ctrl+N"
}))
```

- [ ] **Step 2: Run QML tests and observe missing shortcut components**

Run: `rtk node test/qml-model-test.js`
Expected: FAIL because reset and bulk shortcut functions are absent.

Run: `rtk bash test/qml-static-test.sh`
Expected: FAIL because configurable action shortcuts and capture UI are absent.

- [ ] **Step 3: Implement the window-local action router**

`WindowShortcuts.qml` owns seven `Shortcut { context: Qt.WindowShortcut }` objects. Bind `enabled` to window visibility and `!chat.hasBlockingTransient`. Wire actions exactly:

- Ctrl+L: `chat.focusComposer()`;
- Ctrl+K: `chat.openAgentPicker()`;
- Ctrl+.: `chat.openEffortPicker()`;
- Ctrl+H: `chat.togglePage("history")`;
- Ctrl+,: `chat.togglePage("profiles")`;
- Ctrl+Shift+P: `chat.togglePrivate()`;
- Ctrl+N: `chat.newConversation()`.

Use the configured sequences, not literal defaults, in the QML `Shortcut` objects. Literal defaults live only in schema/model defaults and presentation hints.

- [ ] **Step 4: Implement capture, conflict feedback, and reset**

`ShortcutCapture` ignores auto-repeat, consumes one non-modifier key with its active Ctrl/Alt/Shift/Meta modifiers, and emits the canonical sequence. Escape cancels capture without changing the value. `ShortcutEditor` renders all seven actions, validates the entire candidate map through `ProfileModel.setUiShortcuts`, shows the thrown conflict/reserved message without emitting, and offers “Reset shortcuts” using `resetUiShortcuts`.

Add a `SHORTCUTS` section to `ProfileSettings`; saving it calls a separate `uiShortcutsChanged` signal so profile field edits are not required. The bridge remains authoritative and returns any validation failure without overwriting the last valid local state.

- [ ] **Step 5: Implement deepest-first Escape and page back behavior**

Focused picker popups and dialogs consume Escape themselves. At `Keys.AfterItem`, call `chat.handleBack()`; it closes any remaining picker, then returns History/Settings to chat, then returns `false` so `QuickChat.requestClose()` hides the window. Alt+Left returns History/Settings to chat and does not hide the window.

- [ ] **Step 6: Finish keyboard-only traversal**

- Add Right to expand and Left to collapse harness rows; keep Up/Down, Enter, Space, and typing-to-filter.
- Make all header/context/send/stop/history/settings controls `activeFocusOnTab`/focusable in visual order.
- Make Shift+Tab traverse backward without custom interception.
- Make History Home/End and Space/Enter activate the cursor row; Ctrl+N remains the action shortcut.
- Make Settings focus its first editable control and scroll focused fields into view.
- Keep Enter send and Ctrl+Enter selection-aware newline insertion exactly as implemented.
- Add shortcut hints to tooltips and accessible labels without changing icon-only header design.

- [ ] **Step 7: Run QML and full suites**

Run: `rtk node test/qml-model-test.js`
Expected: PASS for default, capture-normalized, conflicting, reserved, and reset maps.

Run: `rtk bash test/qml-static-test.sh`
Expected: PASS for exactly-once shortcut wiring, deepest-first Escape, Alt+Left, picker tree arrows, complete tab order, and unchanged send/newline semantics.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 8: Commit complete keyboard control**

```bash
rtk git add ui models/ProfileModel.js QuickChat.qml test/qml-model-test.js test/qml-static-test.sh
rtk git commit -m "feat: add configurable keyboard control"
```

---

### Task 7: Add a real six-harness smoke matrix

**Files:**
- Create: `test/live-harness-smoke.py`
- Modify: `test/all`
- Modify: `tests/test_adapters.py`
- Modify: `README.md`

**Interfaces:**
- `test/live-harness-smoke.py` runs only when `QUICK_CHAT_LIVE_HARNESSES=1`.
- `auth_probe(adapter_id, model) -> tuple[str, ...] | None` returns a non-interactive, non-secret-printing check.
- The script prints one JSON result per harness with `id`, `version`, `auth`, `model`, `efforts`, `answer`, `completed`, and `error`.
- Exit is nonzero unless all six harness rows have `auth=true`, a model, `QUICK_CHAT_OK` in normalized assistant text, and `completed=true`.

- [ ] **Step 1: Write failing smoke-runner unit seams**

Place the non-network functions behind importable helpers and add tests in `tests/test_adapters.py` that assert:

- Codex uses `codex login status`;
- Claude uses `claude auth status`;
- Cursor uses `cursor-agent status`;
- Pi uses `pi auth check --model <model> --json --no-refresh`;
- Grok and OpenCode use their authenticated model catalog when no dedicated status command exists;
- no auth probe includes a credential-printing flag; and
- the exact prompt is `Reply with exactly QUICK_CHAT_OK and nothing else.`.

- [ ] **Step 2: Run the unit seam and observe missing-runner failures**

Run: `rtk python3 -m unittest tests.test_adapters -v`
Expected: FAIL because the live smoke helpers do not exist.

- [ ] **Step 3: Implement the opt-in runner using production adapters**

For each id in `("codex", "claude", "opencode", "grok", "cursor", "pi")`:

1. call `adapter.detect()` and require a parsed version;
2. run its non-interactive auth probe with captured output and `shell=False`;
3. call `adapter.discover_models(tempdir)` and choose the configured model when present, otherwise `is_default`, otherwise the first row;
4. build `AdapterContext` with the exact prompt, `thinking_effort=None`, no attachments, a fresh temporary directory, and `private=True`;
5. call `adapter.start(context)` and run it through `ProcessTransport(timeout_seconds=180)`;
6. normalize every stdout event through `adapter.parse_event`;
7. require assistant text containing `QUICK_CHAT_OK`, a normalized completion event, exit code zero, and no timeout; and
8. compare directory contents before/after and fail on any created file.

Do not log raw auth output, tokens, environment variables, invocation environment, or full diagnostics. The error field contains only a bounded classification such as `not_installed`, `authentication_required`, `model_discovery_failed`, `timeout`, `nonzero_exit`, `missing_token`, or `missing_completion`.

- [ ] **Step 4: Wire the opt-in gate and documentation**

Append to `test/all`:

```bash
if [[ "${QUICK_CHAT_LIVE_HARNESSES:-}" == "1" ]]; then
  python3 "$ROOT/test/live-harness-smoke.py"
fi
```

Document that the matrix makes six real provider requests and may consume account quota.

- [ ] **Step 5: Run unit and offline suites**

Run: `rtk python3 -m unittest tests.test_adapters -v`
Expected: PASS for safe probes and exact prompt.

Run: `rtk ./test/all`
Expected: PASS without making provider requests.

- [ ] **Step 6: Commit the live harness matrix**

```bash
rtk git add test/live-harness-smoke.py test/all tests/test_adapters.py README.md
rtk git commit -m "test: add live harness smoke matrix"
```

---

### Task 8: Update desktop acceptance and user documentation

**Files:**
- Modify: `test/acceptance/quick-chat-test.sh`
- Modify: `README.md`
- Modify: `docs/bridge-protocol.md`
- Modify: `docs/adapter-authoring.md`
- Modify: `manifest.json`

**Interfaces:**
- Disposable acceptance records `hyprctl clients -j` snapshots before and after every window-state action.
- Acceptance artifacts include compact chat, model picker, effort picker, History, Settings, approval, and error states.
- Documentation reflects a standard window, schema 2, shortcuts, effort behavior, read-only Cursor Ask mode, and live-test commands.

- [ ] **Step 1: Add failing documentation/static assertions**

Update `test/qml-static-test.sh` to reject “expanded workspace”, “overlay”, and Ctrl+Return-to-send wording in the README. Require documentation for every default shortcut, Super+T tiling, Super+drag/header drag, standard maximize, inherited opacity, and all six effort mappings.

- [ ] **Step 2: Run the static test and observe stale-documentation failures**

Run: `rtk bash test/qml-static-test.sh`
Expected: FAIL because the README still describes compact/expanded popup behavior.

- [ ] **Step 3: Extend disposable desktop acceptance**

Keep the `QUICK_CHAT_DISPOSABLE=1` guard. Replace the stale Ctrl+Return send with Enter. Add helpers that resolve the exact `Quick Chat` address from `hyprctl clients -j`, record geometry/floating/fullscreen state, and fail if more than one address matches.

The script must verify:

- initial title, floating state, and approximately 620x620 geometry;
- immediate typing after summon without a click;
- focus can move to another window and stays there;
- Super+T tiles and remains tiled after at least 500 ms;
- History and Settings shortcuts preserve address, geometry, floating state, and fullscreen state;
- header maximize and Super+Alt+F produce compositor maximized state and restore;
- private, model, effort, new-chat, focus-input, Alt+Left, Tab/Shift+Tab, arrows, Enter, Space, Ctrl+Enter, and Escape paths;
- no `opacity:` in plugin QML and the client receives Omarchy's `default-opacity` tag; and
- `hyprctl configerrors` is empty after reload.

Capture a separate `effort-picker.png`. History and Settings artifact names no longer use “expanded”.

- [ ] **Step 4: Update docs and version**

Bump the manifest minor version. Document schema-1 automatic migration, `uiShortcuts`, `thinkingEffort`, the supported-only rule, Default semantics, native per-harness translation, Cursor `--mode ask`, and the real-harness opt-in quota warning. Update protocol examples to include model effort metadata and config schema 2.

- [ ] **Step 5: Run the complete offline suite**

Run: `rtk ./test/all`
Expected: PASS.

Run: `rtk git diff --check`
Expected: PASS with no whitespace errors.

- [ ] **Step 6: Commit acceptance and documentation**

```bash
rtk git add test/acceptance/quick-chat-test.sh README.md docs manifest.json test/qml-static-test.sh
rtk git commit -m "docs: describe standard keyboard quick chat"
```

---

### Task 9: Install, exercise every harness, and verify the active desktop

**Files:**
- Modify only if a failing live test first gains a focused regression test in the owning test file.
- Write acceptance artifacts under `test/acceptance/artifacts/` only when that directory remains ignored by Git.

**Interfaces:**
- The source repository, installed `community.quick-chat` copy, and live Omarchy shell report the same manifest version.
- Final evidence contains six actual versions/models and explicit desktop check results.

- [ ] **Step 1: Establish a clean repository baseline**

Run: `rtk git status --short --branch`
Expected: `main` with no uncommitted files.

Run: `rtk ./test/all`
Expected: PASS.

- [ ] **Step 2: Resolve or install all six CLI runtimes**

Record `--version` for Codex, Claude Code, OpenCode, Grok, Cursor, and Pi. If OpenCode or another runtime is missing, install it through the user's existing mise/Omarchy CLI manager with the previously granted authorization. Re-run the version command and require success; do not mark a wrapper that still attempts a failed on-demand install as installed.

- [ ] **Step 3: Run the real provider matrix**

Run: `rtk env QUICK_CHAT_LIVE_HARNESSES=1 python3 test/live-harness-smoke.py`
Expected: exit 0 and six JSON success rows, each containing a real version, model, `QUICK_CHAT_OK`, and `completed: true`.

For any failure, first add a focused failing unit/fixture test, make the smallest adapter correction, run its focused test, run `rtk ./test/all`, and repeat the failed real harness. Authentication failures require the existing CLI's non-interactive status to become healthy; never start or automate an interactive login flow without the user.

- [ ] **Step 4: Install the passing source plugin**

Run: `rtk omarchy plugin add file:///home/g2v/Projects/omarchy/omarchy-quick-chat --enable --yes`
Expected: `community.quick-chat` installed and enabled from this source.

Reload the Omarchy shell through its supported CLI and verify the plugin list reports the new manifest version. Do not edit the installed copy directly.

- [ ] **Step 5: Run active-session acceptance with the user's authorization**

Back up `~/.config/omarchy/quick-chat/config.json`, summon through the Omarchy root menu entry and global shortcut, and execute the approved desktop checks from Task 8. Use exact-address `hyprctl` reads before any dispatch. Restore the config backup after fixture-only changes.

If the migrated legacy `SUPER ALT, SPACE` shortcut reports its known Apps-menu collision, verify that feedback in Settings, change the selected profile shortcut through the UI to the inspected free value `SUPER ALT, C`, and then test summon. This is an explicit user-visible remap, not a migration rewrite.

Require these outcomes:

- normal floating `Quick Chat` toplevel at 620x620 on summon;
- theme/font changes remain live and no plugin opacity override exists;
- another app remains focusable while Quick Chat is open;
- header drag and Super+drag both move the window;
- Super+T tiles it without a re-float;
- header maximize and Super+Alt+F use true compositor maximize/restore;
- History/Settings never change geometry or maximize state;
- all configurable action shortcuts and fixed interaction keys work;
- model and effort pickers expose only discovered supported rows;
- Enter sends and Ctrl+Enter inserts a newline; and
- the root menu search terms `Quick Chat`, `chat`, and `ask` still open the selected profile.

- [ ] **Step 6: Run final verification and inspect the diff**

Run: `rtk ./test/all`
Expected: PASS.

Run: `rtk git status --short --branch`
Expected: clean `main`.

Run: `rtk git log --oneline -10`
Expected: small commits matching the task boundaries above.

Compare a content hash of the source plugin and installed plugin while excluding `.git`, generated acceptance artifacts, and user state. Expected: no source-file differences.

- [ ] **Step 7: Produce the completion report**

Report:

- repository commit hash and installed manifest version;
- automated suite result;
- each harness's actual version, selected model, advertised effort choices, auth result, and `QUICK_CHAT_OK` result;
- standard-window geometry/focus/drag/tile/maximize/opacity results;
- keyboard shortcut and page-geometry results;
- menu integration result; and
- any harness that explicitly advertises no effort values, shown as a disabled Default selector rather than a guessed list.

Do not claim completion until every required row and desktop check is successful.

---

## Plan Self-Review Checklist

- [ ] Every goal and non-goal in the approved design maps to at least one task and one verification step.
- [ ] Python and JavaScript use the same schema-2 field names and null semantics.
- [ ] `EffortOption`, `ModelOption`, `Capabilities`, `AdapterContext`, registry resolution, bridge JSON, and QML projections agree on types.
- [ ] Config migration preserves all version-1 profile, model, history, private, transport, custom command, and global summon values.
- [ ] No task introduces a persistent Hyprland rule, QML opacity, overlay scrim, automatic approval, or guessed effort value.
- [ ] Every production change is preceded by a named failing test and followed by focused plus aggregate verification.
- [ ] Live harness success requires a real answer and completion; desktop success requires actual compositor state.
- [ ] All commands in this plan use the required `rtk` prefix.
