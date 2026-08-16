# Bridge protocol

Quick Chat speaks version 1 of a newline-delimited JSON protocol over the
bridge process's standard input and output. Each physical line is one UTF-8
JSON object and is limited to 1 MiB. Standard error is reserved for bridge
diagnostics and is never rendered as assistant text.

The bridge emits one ready event immediately after startup:

```json
{"type":"ready","requestId":"bridge","data":{"protocolVersion":1}}
```

A chat turn is submitted with a stable request, conversation, and profile ID:

```json
{"type":"run","requestId":"req-1","conversationId":"conv-1","profileId":"codex","prompt":"Explain this window","attachments":[],"private":false}
```

Requests support these types: `run`, `cancel`, `approve`, `deny`, `probe`,
`profiles`, `history.list`, `history.get`, `history.clear`, `context.capture`,
`context.ocr`, and `context.remove`. Events support `ready`, `status`,
`text_delta`, `tool_request`, `session`, `complete`, and `error`.

Attachments are typed as `image`, `text`, or `metadata`. File-backed
attachments are accepted only beneath `$XDG_RUNTIME_DIR/omarchy-quick-chat`
(or the system temporary directory fallback) so callers cannot make a profile
read arbitrary paths.

Malformed or oversized input produces an `error` event for that line. The
bridge remains alive and continues reading later requests.
