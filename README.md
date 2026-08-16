# Omarchy Quick Chat

Quick Chat is a third-party Omarchy shell plugin for fast Q&A through agent
CLIs already installed and authenticated on your machine. It opens as a
keyboard-first centered popup and expands into a larger history and profile
workspace when needed. The workspace keeps one focused page on screen at a
time—Chat, History, or Profiles—instead of compressing them into sidebars.

The built-in profiles are Codex, Claude Code, OpenCode, Grok, Cursor, and Pi.
Custom shell-free command profiles are also supported.

## Install

For this development checkout:

```bash
omarchy plugin add file:///home/g2v/Projects/omarchy/omarchy-quick-chat --enable
```

This repository currently has no `origin` remote. After publishing it, obtain
the canonical URL with `git remote get-url origin`, then install that exact URL:

```bash
omarchy plugin add https://example.invalid/owner/omarchy-quick-chat.git --enable
```

Replace the example only with the value returned by `git remote get-url
origin`. Update or remove the plugin with Omarchy's normal `omarchy plugin`
commands.

## Use

Press `SUPER+ALT+SPACE` to open the default Codex profile. `Ctrl+Enter` sends;
plain Enter adds a line. Escape hides the popup without cancelling the active
turn, so reopening restores it. Use Expand to switch between the full-width
Chat, History, and Profiles pages. Each named profile can have its own
Hyprland shortcut.

Quick Chat also adds a searchable **Quick Chat** action to the root Omarchy
menu. The entry is merged idempotently into the user menu extension without
replacing existing entries or comments, and is hidden while the plugin is
disabled. Current Omarchy releases render all stock root rows before extension
rows, so Quick Chat is the first custom row. The planned relative-order hook
will default it immediately after Apps and let users choose another position.

The popup itself has no full-screen backdrop or click-blocking overlay. Its
surface, controls, state fills, borders, corners, spacing, type scale, and font
family bind to Omarchy's live theme tokens and update with the active theme.

The header switches profiles and toggles private mode. History keeps the 20
most recently updated conversations by default. Set any positive finite limit
or Unlimited globally or per profile. Clear History removes Quick Chat's
messages and session mappings, but does not delete sessions owned by a CLI.

## CLI prerequisites

Install and authenticate any presets you intend to use through their native
tools:

- `codex`
- `claude`
- `opencode`
- `grok`
- `cursor-agent`
- `pi`

Quick Chat does not store API keys or provider credentials. A missing,
unauthenticated, unsupported, or degraded CLI is shown as an actionable inline
state. Unknown structured output degrades to plain text and disables resume,
native images, and relayed approvals while preserving read-only arguments.

## Profiles and safety

A profile selects the CLI adapter, model, system instructions, working
directory policy, allowed context providers, permission policy, retention,
private default, advanced arguments, and shortcut. Fixed working directories
must exist. Active-project profiles resolve `/proc/<active-pid>/cwd` without a
shell and fall back visibly to home when unavailable.

Every built-in process adapter uses read-only or plan behavior. Quick Chat never
passes force, yolo, full-auto, dangerously-skip-permissions, or equivalent
flags. Custom command arguments are arrays; prompts and paths are never shell
interpolated. Custom commands are Q&A-only unless explicit read-only arguments
are configured.

Approvals offer only Approve once and Deny. If process mode cannot relay an
approval safely, Quick Chat denies it and offers to continue the native session
in a terminal.

## Desktop context and privacy

Window, Screen, App, and Selected Text context is opt-in per message. Captures
are shown before sending. Window capture is the default visual choice;
full-screen capture always requires its own button. OCR is a separate explicit
action when the selected profile cannot receive images.

Runtime copies live under `$XDG_RUNTIME_DIR/omarchy-quick-chat`, use private
permissions, and are deleted after sending, cancellation, failure, removal, or
bridge shutdown. Private conversations write no Quick Chat messages,
attachments, or CLI session mappings.

Configuration is stored in
`$XDG_CONFIG_HOME/omarchy/quick-chat/config.json` and history in
`$XDG_STATE_HOME/omarchy/quick-chat/history.json`, with standard home-directory
fallbacks. Corrupt files are quarantined beside the original and defaults are
loaded with a visible recovery notice.

## Troubleshooting

Run the local non-graphical suite:

```bash
./test/all
```

Bridge diagnostics are emitted on stderr and never rendered as assistant text.
Inspect Omarchy shell logs and the quarantined path shown by a recovery notice.
Use Refresh probe after updating a CLI. Native login commands are only copied;
Quick Chat never logs in automatically.

Omarchy plugins execute unsandboxed inside the shell process. Review third-party
plugin source before enabling it. The bridge limits its own subprocesses and
files, but installing a plugin still grants code execution as your desktop user.

## Development

Runtime code uses Python's standard library, QML/Quickshell, and argument-array
subprocess execution. See [the bridge protocol](docs/bridge-protocol.md) and
[adapter authoring guide](docs/adapter-authoring.md).

The graphical acceptance test must only run in a disposable Omarchy guest:

```bash
QUICK_CHAT_DISPOSABLE=1 QUICK_CHAT_REPO="file://$PWD" \
  bash test/acceptance/quick-chat-test.sh
```
