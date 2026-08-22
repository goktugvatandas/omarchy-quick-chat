# ACP transport

Quick Chat optionally supports Agent Client Protocol (ACP) version 1 over
newline-delimited JSON-RPC 2.0 stdio. Process transport remains the default.
A profile must select `transport: "auto"` or `transport: "acp"`, and its
adapter must expose a verified ACP command. Grok uses `grok agent stdio`.

## Lifecycle

```text
stopped -> initializing -> ready -> prompting -> ready
              |              |          |
              v              v          v
            failed      reconnecting   failed
```

Initialization sends `initialize` with `protocolVersion: 1` and rejects any
other negotiated version. New conversations use `session/new` with an absolute
working directory and `mcpServers: []`; known mappings use `session/load`.
Text and explicitly approved images are sent as typed content blocks through
`session/prompt`. `session/update` agent chunks become `text_delta` events and
tool updates become status events. ACP stdout is read in bounded physical lines
and enters a 64-item backpressure queue. A run stops forwarding provider events
after 1,024 updates or 256 KiB of assistant text.

One ACP process is cached per adapter/model tuple and closes after ten idle
minutes. If it has disconnected before a prompt, Quick Chat reconnects once and
loads the known session. A disconnect after prompt submission is an error: the
prompt is never replayed automatically. The registry marks that ACP tuple
failed, reports a degraded state, and `auto` uses process transport on the next
turn.

## Permissions and cancellation

Agent permission requests reuse Quick Chat's visible Approve once/Deny card.
Only the matching active approval ID is accepted; timeout resolves to Deny.
There is no approve-always outcome. Stop sends `session/cancel` for the exact
active session.

The transport never grants filesystem or terminal client capabilities during
initialization. It reuses the same attachment cleanup, private-history, and
session-mapping policies as process transport.
