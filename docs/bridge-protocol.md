# Bridge protocol

Quick Chat speaks version 1 of a newline-delimited JSON protocol over the
bridge process's standard input and output. Each physical line is one UTF-8
JSON object and is limited to 1 MiB. The bridge reads at most that much before
rejecting and draining an oversized physical request. Standard error is reserved
for bridge diagnostics and is never rendered as assistant text.

The bridge emits one ready event immediately after startup:

```json
{"type":"ready","requestId":"bridge","data":{"protocolVersion":1}}
```

A chat turn is submitted with a stable request, conversation, and profile ID:

```json
{"type":"run","requestId":"req-1","conversationId":"conv-1","profileId":"codex","prompt":"Explain this window","attachments":[],"private":false}
```

Requests support these types: `run`, `cancel`, `approve`, `deny`, `probe`,
`models.list`, `profiles`, `history.list`, `history.get`, `history.clear`,
`context.capture`, `context.ocr`, and `context.remove`. Events support `ready`, `status`,
`text_delta`, `tool_request`, `session`, `complete`, and `error`.

Model discovery identifies the adapter and may bypass the bridge-lifetime cache:

```json
{"type":"models.list","requestId":"req-models","profileId":"codex","adapterId":"codex","refresh":false}
```

The corresponding completion contains selectable model metadata:

```json
{"type":"complete","requestId":"req-models","data":{"models":[{"id":"gpt-5.6-sol","label":"GPT-5.6 Sol","description":"Fast coding model","efforts":[{"id":"low","label":"Low","description":"Faster"},{"id":"high","label":"High","description":"Deeper"}],"isDefault":true}]}}
```

`efforts: null` asks the UI to use explicit adapter-level choices,
`efforts: []` means the model explicitly advertises none, and a non-empty array
is the complete supported set for that model. The bridge never synthesizes
effort values. Discovery failures are returned as normal `error` events and
are rendered only in settings and pickers.

The `profiles` and `profiles.save` messages carry configuration schema 2. The
important top-level and profile fields are shaped as follows:

```json
{
  "schemaVersion": 2,
  "selectedProfileId": "codex",
  "historyLimit": 20,
  "defaultShortcut": "SUPER ALT, C",
  "uiShortcuts": {
    "focusInput": "Ctrl+L",
    "model": "Ctrl+K",
    "effort": "Ctrl+.",
    "history": "Ctrl+H",
    "settings": "Ctrl+,",
    "private": "Ctrl+Shift+P",
    "newChat": "Ctrl+N"
  },
  "profiles": [
    {
      "id": "codex",
      "adapterId": "codex",
      "model": "gpt-5.6-sol",
      "thinkingEffort": "high"
    }
  ]
}
```

`thinkingEffort` is either a validated effort identifier or `null`. It belongs
to the profile, so a `run` request does not duplicate it; the engine resolves
the selected profile, verifies the choice against current model metadata, and
passes it to the adapter. A stale or unsupported value is rejected instead of
being forwarded.

Schema-1 files are migrated on load. Migration preserves all existing profile,
model, history, private, transport, custom-command, and summon-shortcut values,
adds default `uiShortcuts`, sets missing `thinkingEffort` values to `null`, and
atomically saves schema 2 when the config directory is writable.

Attachments are typed as `image`, `text`, or `metadata`. File-backed
attachments are accepted only beneath `$XDG_RUNTIME_DIR/omarchy-quick-chat`
(or the system temporary directory fallback) so callers cannot make a profile
read arbitrary paths.

Malformed or oversized input produces an `error` event for that line. The
bridge remains alive and continues reading later requests. Provider output is
bounded before it reaches QML: 64 KiB per physical line, 256 KiB of assistant
text, 1,024 provider events, and 1 MiB for a serialized bridge event.
