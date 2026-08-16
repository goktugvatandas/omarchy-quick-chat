# Quick Chat Standard Window, Keyboard Control, and Thinking Effort Design

**Date:** 2026-08-16  
**Status:** Approved design, pending implementation plan  
**Scope:** `goktugvatandas.quick-chat` Omarchy shell plugin

## Summary

Quick Chat will stop using a layer-shell overlay and become one normal desktop
window. It opens centered at 620x620 and is floated once for that opening. After
the initial placement, it behaves exactly like another Omarchy application:
the user can tile it with Super+T, move it with Super+drag or its header, switch
focus away without the chat blocking other windows, and maximize or restore it
through the compositor.

The chat will be operable without a mouse. Window-local shortcuts will open
History, Settings, the combined harness/model picker, and a new thinking-effort
picker, while preserving normal text-editing, focus traversal, and Omarchy
window-manager shortcuts. Shortcuts that represent Quick Chat actions will be
configurable.

Thinking effort will be a profile-level setting normalized by the bridge and
translated into each built-in CLI's native mechanism. Model-specific choices
will be shown when the harness exposes them; unsupported values will never be
silently sent.

Completion requires unit, integration, and live desktop verification plus a
minimal real prompt through Codex, Claude Code, OpenCode, Grok, Cursor, and Pi.

## Goals

- Focus the composer automatically whenever Quick Chat is summoned.
- Preserve the active Omarchy theme, fonts, and compositor opacity.
- Open as a floating 620x620 normal window, then allow ordinary tiling.
- Support both Super+drag and drag from the unused header area.
- Make maximize/restore use actual compositor window state.
- Keep History and Settings in the current window geometry and state.
- Make all product actions reachable with the keyboard.
- Add configurable shortcuts for private mode, History, Settings, model, and
  thinking effort, plus convenient focus-input and new-chat shortcuts.
- Preserve Enter to send and Ctrl+Enter to insert a newline.
- Support native thinking-effort controls across all six default harnesses.
- Prove that every default harness is installed, authenticated, discoverable,
  safe, and capable of completing a minimal Q&A request.

## Non-goals

- Quick Chat will not become an always-floating or always-on-top window.
- It will not add a background overlay, modal focus grab, tab bar, or separate
  expanded-pane implementation.
- It will not override a user's global Hyprland opacity or theme settings.
- It will not reserve new global Super shortcuts for internal page actions.
- It will not guess unsupported effort values or auto-approve tool execution.
- It will not replace the existing combined harness/model picker.

## Current Problems

`QuickChat.qml` currently owns a `PanelWindow` on the layer-shell overlay layer.
That architecture requires a temporary exclusive keyboard focus prime, does
not participate in normal toplevel window management, bypasses normal
per-window opacity behavior, and cannot provide genuine move, tile, or maximize
semantics.

`ChatSurface.openPage()` also requests the custom `expanded` state whenever
History or Settings opens. The expand control only changes the requested panel
dimensions from 620x620 to 760x760, so it is neither a standard maximize nor a
workspace-sized window.

The model picker has no adjacent effort selector and `Profile` has no effort
field. Adapter invocation tests cover fixture parsing and safety flags but not
live authentication, discovery, or end-to-end answers for all six harnesses.
Cursor also starts print mode without explicitly selecting its read-only Ask
mode.

## Considered Window Architectures

### 1. One standard window with one-shot initial floating — selected

Replace `PanelWindow` with Quickshell's `FloatingWindow`, which is a standard
operating-system toplevel despite its type name. On each fresh map, identify the
Quick Chat toplevel by its exact title and address, float and center that address
once, and then stop managing its layout state.

This produces a quick-popup opening while retaining Alt+Tab, compositor opacity,
Super+drag, Super+T, workspace movement, grouping, and actual maximize behavior.
Because the float action is scoped to the current map generation and exact
toplevel address, later user tiling is not reverted.

### 2. Persistent Hyprland window rule

A static title-matched rule could float every new Quick Chat window before its
first frame. It would require installing and maintaining user Hyprland config,
handling configuration reloads, and matching a title or shared shell app ID.
That is unnecessary state outside the plugin and is not selected.

### 3. Layer popup plus a second normal window

Keeping the current panel for compact mode and transferring state into another
window for expanded mode would duplicate lifecycle, focus, and geometry logic.
It would also create a visible discontinuity and more failure modes around
streaming runs. It is not selected.

## Window Lifecycle

### Mapping and initial placement

`QuickChat.open()` increments an opening generation, selects any payload profile
or conversation, makes the standard window visible, and marks focus and initial
placement as pending. The window has the stable title `Quick Chat`, a requested
size of 620x620, and minimum dimensions that keep the composer and header usable.

When Hyprland reports the matching active toplevel, the plugin records its
address. For that opening generation only, it sends address-targeted float,
exact-size, and center operations. It never uses a continuously evaluated
floating rule. If the exact toplevel cannot be identified, the plugin leaves
the window under normal compositor control instead of risking an operation on
another application.

Reopening Quick Chat creates a new opening generation and again starts as a
quick floating window. Once opened, Super+T may tile it and no timer or state
handler will float it again.

### Focus

Opening uses a bounded activation handshake:

1. Show the standard toplevel.
2. Request activation once the backing window exists.
3. On activation, defer `composer.focusInput()` until the next QML turn.
4. Clear the pending-open flag.

The plugin may retry only during that bounded opening handshake. It will not
focus the composer merely because profiles finish loading, a stream completes,
or another application becomes active. Consequently, a user can focus any
other window while Quick Chat remains visible and Quick Chat will not steal
focus back.

Returning through Alt+Tab preserves the last focused Quick Chat control. A new
summon focuses the composer because that is a new open action.

### Opacity and theme

The QML window will not assign a custom `opacity` and the plugin will not add an
opacity window rule. As a standard toplevel it receives the same Omarchy
`default-opacity` behavior and user transparency controls as other windows.

All content continues to use `Color`, `Style`, `BorderSurface`, and Omarchy UI
controls. The root surface uses the active popup/background color, and the
compositor applies active and inactive opacity to the entire window. Theme and
font changes remain live.

### Dragging, tiling, and maximize

- Super+left-drag and Super+right-drag work through the existing Omarchy binds.
- Pressing and dragging unused header/identity space calls
  `FloatingWindow.startSystemMove()`.
- Header buttons are excluded from the drag region.
- Double-clicking unused header space toggles compositor maximize/restore.
- The maximize icon invokes the same compositor maximized state as Omarchy's
  `Super+Alt+F`, targeted to the Quick Chat toplevel.
- The icon and tooltip derive from the reported toplevel state, including when
  maximize changes through an external keybind.
- Restoring returns to the compositor's prior floating or tiled placement.
- `expanded`, the 760x760 pseudo-expanded size, and page-driven resize behavior
  are removed.

## Page Navigation and Geometry

`ChatSurface.openPage(page)` will change only `activePage` and focus the first
appropriate control. It will never request a size or window-state change.

- History focuses its search/list entry point.
- Settings focuses its first editable field or page navigation control.
- Selecting a conversation returns to chat and focuses the composer.
- Escape from History or Settings returns to chat before a later Escape hides
  the window.
- Alt+Left returns from either subpage to chat.
- Window dimensions and maximize/tile state remain unchanged across all page
  transitions.

The layouts remain responsive: compact windows use each page's single vertical
scroll region, while maximized or tiled windows allow the primary transcript or
settings list to consume the additional space. No nested, meaningless
scrollbars are introduced.

## Keyboard Interaction

### Default shortcuts

| Action | Default | Behavior |
| --- | --- | --- |
| Focus composer | Ctrl+L | Return to chat and focus the prompt |
| Agent/model picker | Ctrl+K | Open the combined harness/model picker |
| Thinking effort | Ctrl+. | Open the effort picker |
| History | Ctrl+H | Toggle History and chat |
| Settings | Ctrl+, | Toggle Settings and chat |
| Private mode | Ctrl+Shift+P | Toggle the current conversation's private state |
| New chat | Ctrl+N | Create a new conversation and focus the prompt |
| Send | Enter | Send non-empty prompt when idle |
| New line | Ctrl+Enter | Insert a newline at the selection/cursor |
| Back/dismiss | Escape | Close the deepest popup/dialog, return to chat, then hide |
| Return to chat | Alt+Left | Return from History or Settings |

Enter, Ctrl+Enter, Escape, Alt+Left, Tab, and Shift+Tab are interaction
contracts rather than user-remappable action shortcuts. This prevents a custom
binding from breaking basic editing or focus traversal.

### Focus and list behavior

- Tab and Shift+Tab traverse every visible enabled control in both directions.
- Arrow keys move within picker trees, menus, history rows, and settings lists.
- Right expands a harness and Left collapses it in the combined picker.
- Enter activates the focused row or button; Space toggles focused toggles and
  icon buttons.
- Typing while a picker is open filters its rows without returning to the
  composer.
- Escape closes the deepest active transient before affecting its parent page.
- Tool/context buttons remain in the tab order, so mouse use is optional even
  without dedicated accelerators.
- Shortcut hints appear in tooltips and accessible labels.

### Shortcut configuration

Config schema version 2 adds a top-level `uiShortcuts` object for the seven
remappable Quick Chat actions. These sequences use canonical Qt-style names
such as `Ctrl+K`, deliberately separate from the existing Hyprland-style global
summon shortcuts.

Settings gains a keyboard-accessible Shortcuts section with capture, conflict
feedback, and reset-to-default actions. Validation rejects empty sequences,
modifier-only sequences, duplicates, and sequences reserved by the fixed
editing/navigation contract. Invalid changes are not persisted. Existing
per-profile global summon shortcuts remain independent.

Version 1 configuration migrates automatically to version 2 by adding default
`uiShortcuts` and a null profile effort. Existing profile, history, private,
model, and global-shortcut values are preserved exactly.

## Thinking Effort

### Domain model

Each profile gains `thinkingEffort: string | null`. Null means `Default` and
passes no Quick Chat override, preserving the CLI or user's native setting.

`AdapterContext` gains `thinking_effort`. `Capabilities` reports whether the
adapter can select effort. Model discovery returns effort/variant metadata with
each `ModelOption` where the CLI exposes it. The UI derives the active choices
from the active harness and selected model.

Changing model validates the stored effort against the new model. If it is no
longer valid, Quick Chat resets it to Default, persists the correction, and
shows the new effective label. It never silently substitutes a different
non-default level.

### UI

A compact effort button sits beside the combined harness/model picker near the
composer. Its label is `Default` or the selected native level/variant. Ctrl+.
opens it. The menu provides model-supported options, keyboard navigation, and a
short explanation that effort can affect latency and usage.

If a harness or selected model exposes no effort control, the button remains a
disabled `Default` indicator with an explanatory tooltip. It does not show a
generic list that may fail at runtime.

### Adapter translation

| Harness | Native mapping |
| --- | --- |
| Codex | `-c model_reasoning_effort=\"<level>\"` before the exec subcommand |
| Claude Code | `--effort <level>` |
| OpenCode | `--variant <variant>` using model-specific catalog variants |
| Grok | `--reasoning-effort <level>` |
| Cursor | Merge `effort=<level>` into the selected model's parameter block |
| Pi | `--thinking <level>` |

Codex discovery preserves advertised reasoning-effort metadata; its static
fallback is limited to values supported by the installed CLI contract. Claude
uses the choices advertised by its installed help. OpenCode never fabricates
variants: it uses the current catalog. Cursor preserves any existing model
parameters while changing only `effort`. Pi may narrow its global levels using
model reasoning metadata. Grok exposes only values validated by its adapter
contract or discovery response.

Custom adapters have no effort support unless a future adapter contract adds an
explicit safe argument template for it.

## Harness Safety and Correctness

All process adapters retain explicit read-only or planning behavior and never
add automatic-approval flags.

- Codex keeps `--sandbox read-only`.
- Claude Code keeps plan mode and mutation-tool denials.
- OpenCode never receives `--auto`.
- Grok keeps a read-only tool allowlist and no auto-approval.
- Cursor adds `--mode ask` and continues to exclude force/yolo behavior.
- Pi keeps only `read,grep,find,ls`.

Effort arguments are added as distinct argv values, never shell fragments.
Adapter and shortcut inputs continue through structural validation. Live tests
run in a temporary directory and may not write to the repository.

## Error Handling

- Initial-placement timeout leaves a usable normal window rather than touching
  an unverified active window.
- Unsupported effort resets to Default with visible feedback.
- Model discovery failure preserves the current saved model/effort and offers a
  retry; it does not populate guessed rows.
- Missing executable, failed authentication, timeout, malformed stream, or
  nonzero exit remains a harness failure with an actionable message.
- Shortcut conflicts are rejected before config persistence.
- If a live smoke prompt cannot complete, the harness is not reported working.
- Existing stream cancellation, retry, approval, and recovery paths remain in
  place.

## Test Strategy

Implementation follows test-driven development: each behavior begins with a
focused failing test, followed by the smallest implementation and then the full
suite.

### Domain and adapter tests

- Version 1 to version 2 config migration.
- Shortcut defaults, canonicalization, duplicate detection, and reserved-key
  rejection.
- Profile effort validation, serialization, and model-change reset.
- Effort metadata in model discovery protocol responses.
- Exact argv mapping for all six built-in adapters.
- Cursor's explicit `--mode ask` safety regression.
- Effort values remain separate argv entries and cannot inject shell syntax.
- Existing streaming, resume, attachments, and completion fixtures continue to
  pass.

### QML/static tests

- `FloatingWindow` replaces `PanelWindow` and no Wlr layer-shell focus mode
  remains.
- No QML/window opacity override exists.
- History and Settings page changes do not invoke maximize or resize.
- The header exposes system move and compositor maximize actions.
- Every default shortcut is wired exactly once.
- Shortcut precedence follows dialog -> picker -> page -> window.
- The effort picker is adjacent to the harness/model picker and keyboard
  reachable.
- Enter/Ctrl+Enter behavior remains unchanged.

### Live harness matrix

An opt-in live smoke test runs for Codex, Claude Code, OpenCode, Grok, Cursor,
and Pi. For every harness it must:

1. Resolve the real executable and record its installed version.
2. verify authentication without launching an interactive login flow;
3. discover at least one selectable model;
4. build the read-only invocation through the production adapter;
5. send a minimal prompt requesting the exact token `QUICK_CHAT_OK` in a
   temporary directory;
6. receive normalized assistant text and completion before timeout; and
7. leave the temporary directory and repository unchanged.

Missing runtimes are installed through the user's existing CLI manager when
authorized. Missing authentication is reported as a failure requiring login,
not a skipped success. The smoke prompt is intentionally minimal but is a real
provider request.

### Live desktop acceptance

Against the installed plugin and active Hyprland session:

- Summon Quick Chat and type into the prompt immediately without clicking.
- Confirm `hyprctl clients` reports a normal floating toplevel at approximately
  620x620 with title `Quick Chat`.
- Verify active/inactive compositor opacity changes with focus and no plugin
  opacity override is present.
- Focus another application while Quick Chat remains visible and confirm focus
  stays there.
- Move the window by header drag and by Super+left-drag.
- Tile it with Super+T and confirm it is not floated again.
- Maximize and restore through both the header control and Super+Alt+F; confirm
  compositor state and responsive layout.
- Open History and Settings through shortcuts and confirm geometry/window state
  does not change.
- Exercise private, model, effort, new-chat, focus-input, back, Enter,
  Ctrl+Enter, Tab, Shift+Tab, arrows, Enter, Space, and Escape behavior.
- Run `hyprctl reload` and require an empty `hyprctl configerrors` result if any
  Hyprland integration changed.
- Reinstall/update the source plugin, reload the Omarchy shell, and repeat the
  focused smoke path from the root menu entry and global summon shortcut.

## Rollout and Completion

The work lands in small commits grouped around config/adapter behavior, window
behavior, keyboard UI, and verification. The installed `goktugvatandas.quick-chat`
copy is refreshed only after repository tests pass. Completion requires:

- the complete automated suite passing;
- the six live harness prompts succeeding;
- the desktop acceptance checks succeeding;
- the repository and installed plugin matching;
- no Hyprland configuration errors; and
- a final report that lists actual harness versions, selected smoke models,
  effort support, and acceptance results.

