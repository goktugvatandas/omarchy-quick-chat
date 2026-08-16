# Omarchy Quick Chat Plugin Design

**Date:** 2026-08-16  
**Status:** Approved  
**Target:** Standalone third-party Omarchy plugin installed with `omarchy plugin add`

## Summary

Quick Chat is a keyboard-first Omarchy shell plugin for asking short questions through locally installed agent CLIs. It opens as a compact centered popup, can expand for longer conversations, and can attach explicitly approved active-window or full-screen context.

The first release integrates Codex, Claude Code, OpenCode, Grok, Cursor, and Pi through capability-aware adapters. Users can create named profiles with distinct prompts, models, permissions, working directories, context providers, history behavior, and global keybindings. A custom-command adapter supports other harnesses.

The plugin uses the CLIs' existing authentication and never stores credentials or sends data through a plugin-owned service. Read-only operation is the default. Screen context is captured only on explicit request, previewed before dispatch, and deleted after use.

## Goals

- Make quick local Q&A available from anywhere in Omarchy through a global shortcut.
- Let users select and configure multiple CLI-based agent harnesses without duplicating their authentication.
- Provide named profiles for different roles and allow a distinct shortcut for each profile.
- Attach active-window, full-screen, app, selected-text, and approved Omarchy CLI context with explicit consent.
- Stream normalized answers from heterogeneous CLIs into one native Omarchy interface.
- Keep local conversation history with configurable retention and a genuinely ephemeral private mode.
- Enforce safe defaults and show explicit approval for any relayed tool operation.
- Preserve a transport boundary that can support persistent ACP connections later.

## Non-goals for Version 1

- Direct integration with model-provider HTTP APIs.
- A cloud sync service or remote Quick Chat account.
- Storing or managing CLI credentials.
- Silently capturing the screen or active application.
- Automatically enabling CLI auto-approve, dangerous bypass, or unrestricted execution modes.
- Universal interactive tool approvals for CLIs that do not expose a safe machine-readable approval protocol.
- A persistent ACP host; this is a planned second phase.

## Product Decisions

- Distribution: standalone third-party git repository.
- Surface: compact centered popup by default, expandable into a larger panel-style layout.
- Default CLI presets: Codex, Claude Code, OpenCode, Grok, Cursor, and Pi.
- Extensibility: custom-command adapter in version 1.
- Profiles: named profiles with a CLI, model, system instructions, working directory, permissions, context providers, history behavior, and optional global shortcut.
- Safety: read-only by default; visible approval for safely relayable tool requests.
- Visual context: active-window and full-screen capture, with a preview before sending.
- History: retain the latest 20 conversations by default; allow any finite limit or unlimited history.
- Privacy: per-conversation private toggle and clear-history control.
- Phase 2: add persistent ACP transports behind the same adapter interface.

## Architecture

### Omarchy shell surface

The plugin manifest declares an Omarchy menu surface. Its QML entry point is an `Item` that accepts the shell-injected plugin properties and implements `open(payloadJson)` and `close()`.

The surface owns presentation and interaction only:

- Popup and expanded layouts
- Prompt composition and keyboard behavior
- Profile selection and settings
- Attachment previews
- Streaming response rendering
- History navigation
- Approval cards
- Inline errors and status

The plugin remains loaded while an answer is running so hiding the popup does not cancel work. Expanding changes the layout within the same plugin surface and preserves the active conversation.

### Local bridge

A bundled dependency-free Python helper communicates with QML over newline-delimited JSON on stdin and stdout. It has no listening socket and exposes no network endpoint.

The bridge owns:

- Request schema validation
- CLI discovery and version probing
- Capability selection
- Safe subprocess argument construction without a shell
- Process lifecycle, streaming, cancellation, and timeouts
- CLI-specific output parsing and normalized events
- Session ID mapping
- Context-provider execution
- Configuration and history persistence
- Temporary attachment cleanup

The bridge accepts one active run per UI instance in version 1. A new prompt is disabled until the current run completes or is stopped. This avoids ambiguous output interleaving while keeping the process protocol extensible.

### CLI adapter boundary

Each adapter implements a common interface:

- `detect`: locate the executable and identify its version.
- `capabilities`: report structured output, streaming, resume, model selection, native image attachment, read-only enforcement, and relayable approvals.
- `build_start`: create arguments and environment for a new session.
- `build_resume`: create arguments and environment for a continued session.
- `parse_event`: translate stdout/stderr records into normalized bridge events.
- `cancel`: define any adapter-specific graceful cancellation behavior before the generic process shutdown sequence.

Adapters are data-driven where practical, but CLI-specific parsing and safety behavior stays isolated in dedicated modules. A custom-command adapter supports a user-defined executable and argument template. Substitution is limited to documented typed placeholders and never evaluated through a shell.

### Context providers

Context capture is independent of CLI execution. Providers implement:

- Active-window screenshot
- Full-screen screenshot
- Active app name and window title
- Selected text
- OCR conversion for image context sent to text-only adapters
- Approved read-only Omarchy CLI queries

Omarchy capture commands are preferred when they expose the required mode. Provider output is staged in the private runtime directory and returned to QML for preview. Nothing is attached until the user submits the message with the attachment still selected.

### Transport evolution

QML speaks only the normalized bridge protocol. CLI adapters use a process transport in version 1. A later ACP transport can implement the same start, resume, event, approval, and cancellation semantics without changing the profile schema or UI contract.

## Storage

The plugin follows XDG locations:

- Configuration and profiles: `${XDG_CONFIG_HOME:-~/.config}/omarchy/quick-chat/`
- Conversation history and session mappings: `${XDG_STATE_HOME:-~/.local/state}/omarchy/quick-chat/`
- Temporary captures: `$XDG_RUNTIME_DIR/omarchy-quick-chat/`

Configuration and state documents include an explicit schema version. Writes use a temporary sibling file followed by an atomic rename. A corrupt file is preserved with a timestamped suffix, and the plugin reports recovery before starting with safe defaults.

Credentials, access tokens, and provider API keys are never copied into plugin configuration. Child CLIs inherit the user's existing authentication environment, subject to a minimal configurable environment allowlist for custom adapters.

### Profile schema

A profile contains:

- Stable ID, display name, and optional icon
- Adapter ID and optional model
- System instructions
- Working-directory strategy and optional fixed path
- Allowed context-provider IDs
- Tool and permission policy
- Optional global shortcut
- Optional history-retention override
- Private-by-default flag
- Adapter-specific advanced arguments

Profile IDs remain stable across renames so history, sessions, and shortcuts do not break.

### History schema

A conversation contains:

- Stable conversation ID and title
- Profile ID
- Creation and update timestamps
- Ordered user and assistant messages
- Run attempts and completion state
- Attachment metadata without retained temporary image paths
- Adapter and remote CLI session identifiers

History defaults to the 20 most recently updated conversations. A positive integer sets a finite retention count, while `null` means unlimited. Private conversations never enter persistent history and never persist CLI session mappings.

## User Experience

### Opening and layout

The default global shortcut opens the last-used profile. Each profile may register its own shortcut and opens selected when that shortcut is invoked. Shortcut conflicts are reported on the affected profile and do not disable the default shortcut.

The compact popup contains:

- Profile switcher
- CLI availability indicator
- Private-mode toggle
- Prompt field
- Active-window, full-screen, and app-context buttons
- Attachment chips and screenshot preview
- Streaming response area
- Stop, Retry, Copy, New Chat, and Expand controls
- Compact history picker

The expanded layout keeps the same conversation and adds full history, profile settings, and additional room for long answers and code.

`Esc` hides the surface without cancelling an active answer. Stop cancels the exact active child process. Reopening the popup returns to the active or most recent conversation.

### Profiles and settings

Users can create, duplicate, rename, reorder, and remove profiles. Profile settings cover the schema above and expose adapter capabilities rather than flags that the selected CLI cannot support.

The settings screen shows whether each default CLI is installed and authenticated when authentication can be checked without triggering a login. It provides the detected version and any compatibility warning.

### Context consent

Capturing an active window or full screen creates a preview card showing the image, app name, window title, and file size. The user can remove or replace it before sending.

An image-capable adapter receives the approved image through its native attachment mechanism. A text-only adapter offers an explicit OCR conversion or asks the user to switch profiles. The plugin never performs OCR or changes attachment semantics silently.

### History and private mode

The default global retention is 20 conversations. Users may choose another finite value or unlimited retention. Profiles may override the global value.

Private mode is visible before submission. It suppresses conversation persistence and CLI session mapping for the private conversation. Clear History requires confirmation, removes persisted Quick Chat history and mappings, and does not delete sessions owned by the underlying CLI.

## Request and Event Flow

1. The user chooses a profile, enters a prompt, and optionally captures context.
2. Context providers stage data in the private runtime directory.
3. QML previews the staged context and waits for submission.
4. QML sends the bridge a structured request containing the conversation ID, profile ID, prompt, approved attachment paths, and context metadata.
5. The bridge validates the request, resolves the executable, verifies the working directory, and selects safe adapter capabilities.
6. The adapter creates a new CLI session or resumes the mapped session with read-only restrictions.
7. The bridge emits normalized JSON Lines events: `status`, `text_delta`, `tool_request`, `session`, `complete`, and `error`.
8. QML renders the stream and any supported approval card.
9. On completion, the bridge atomically records the conversation and session mapping unless the conversation is private.
10. The bridge removes temporary attachments after completion, cancellation, failure, or preview removal.

## Safety Model

- Read-only is the default for every built-in profile.
- The bridge launches executables directly with argument arrays and never through a shell.
- Custom adapter placeholders are typed and escaped as individual arguments.
- The plugin never passes auto-approve, unrestricted, dangerous-bypass, or equivalent flags.
- Tool operations are permitted only when the adapter can expose and answer a structured approval request.
- Approval cards display the exact operation and provide Approve Once and Deny actions.
- An unrelayable interactive request is denied. The user may continue the underlying session in its native terminal UI.
- Screen and app context requires explicit per-message selection and remains visible until submission.
- Child output is untrusted: ANSI controls are stripped, structured records are schema-validated, and rendered Markdown cannot execute QML or shell content.
- Cancellation targets the known child process group only.
- The plugin owns no remote service and adds no network listener.

## CLI Compatibility

Known CLI versions use their structured streaming and session features where supported. Unknown versions fall back to plain-text output only when the adapter can do so without weakening the configured safety policy. Resume, native attachments, and tool approvals are disabled in fallback mode.

The UI distinguishes:

- Not installed
- Installed and ready
- Authentication required
- Unsupported version
- Degraded plain-text compatibility
- Running
- Timed out or failed

Version probing is lazy and cached for the current bridge lifetime. A profile use or settings refresh invalidates the relevant cache entry.

## Failure Handling

- Missing executable: show install guidance and offer another profile.
- Authentication required: show the CLI's native login command without executing it automatically.
- Invalid working directory: prevent submission and identify the missing path.
- Capture failure or denial: preserve the prompt and allow sending without the attachment.
- Unsupported image input: offer explicit OCR or profile switching.
- Malformed structured output: preserve sanitized diagnostics and enter safe plain-text mode only if allowed.
- Timeout: interrupt the child, report elapsed time, and offer Retry.
- Cancellation: interrupt, wait briefly, then terminate the exact child process group.
- Bridge crash: show a reconnect action and preserve any already persisted conversation state.
- History corruption: quarantine the source file, report recovery, and start with empty history.
- Shortcut conflict: disable only the conflicting profile shortcut and identify the conflict.

A retry creates another run attempt under the existing user message rather than duplicating it.

## Testing Strategy

### Bridge unit tests

Cover schema validation, profile migrations, retention including unlimited history, atomic writes, session mapping, safe argument construction, environment filtering, event normalization, ANSI stripping, timeouts, cancellation, and cleanup.

### Adapter contract tests

Use recorded synthetic fixtures for all six built-in adapters. Cover text output, structured streaming, session IDs, image capability, read-only flags, missing binaries, unsupported versions, malformed records, and stderr separation.

### Integration tests

Put fake CLI executables on a temporary `PATH` and run them through the real bridge with isolated XDG directories. Verify streaming, session continuation, retries, safely relayable approvals, denied approvals, non-zero exits, process cleanup, image staging, OCR choice, retention, private mode, and clear history without accounts or network access.

### QML and model tests

Keep state transformation logic in testable JavaScript modules where practical. Cover profile selection, history navigation, attachment lifecycle, shortcut mapping, popup-to-expanded transitions, approval state, and safe rendering. Run manifest validation, `qmllint`, Python compilation, formatting, and schema checks.

### Live Omarchy acceptance

In a disposable Omarchy environment, verify:

- Installation through `omarchy plugin add`, enablement, and hot reload
- Default and per-profile shortcuts
- Focus, keyboard navigation, `Esc`, Stop, Retry, Copy, and expansion
- Theme-aware rendering across themes, scales, and monitor layouts
- Active-window and full-screen preview and consent
- Private mode, retention, clear history, and temporary-file cleanup
- Missing, unauthenticated, unsupported, and degraded CLI states

Visual changes require screenshots and inspection in the running UI in addition to automated checks.

## Delivery Phases

### Phase 1: Process-backed plugin

1. Plugin shell, manifest, theme-aware popup, and bridge protocol
2. Profile/config storage and CLI detection
3. Codex and Claude Code adapters as the first vertical slice
4. Conversation streaming, persistence, retention, and private mode
5. Active-window/full-screen context preview and cleanup
6. OpenCode, Grok, Cursor, and Pi adapters
7. Profile-specific keybindings and expanded layout
8. Structured approval relay where safely supported
9. Custom-command adapter, compatibility fallback, documentation, and full acceptance pass

### Phase 2: Persistent agent protocols

1. Define the persistent transport lifecycle behind the existing adapter interface
2. Add ACP connection, capability negotiation, session load, reconnection, and cancellation
3. Prefer ACP for compatible CLIs while keeping process mode as fallback
4. Add protocol-level approval and tool-event handling
5. Add contract tests for reconnects, partial streams, protocol errors, and version negotiation

## Success Criteria

- A user can install and enable the repository through Omarchy's third-party plugin flow.
- The popup opens from a default shortcut, and named profiles can have distinct shortcuts.
- Each default CLI is detected and either works through a safe adapter or shows a precise compatibility state.
- Answers stream, can be stopped, and can resume through mapped CLI sessions where supported.
- Active-window and full-screen context is never sent without a visible preview and submission.
- Read-only behavior is the default, and the plugin never silently auto-approves actions.
- History retains 20 conversations by default, supports finite or unlimited retention, and can be cleared.
- Private conversations leave no Quick Chat history, session mapping, or temporary capture behind.
- Missing tools, expired auth, malformed output, timeouts, and bridge crashes produce actionable recovery paths.
- Phase 2 ACP support can be added without changing the QML-to-bridge request and event contract or migrating user profiles.
