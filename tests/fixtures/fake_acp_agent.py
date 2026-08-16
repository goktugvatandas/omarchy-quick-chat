#!/usr/bin/python3
import json
import sys


protocol_version = 2 if "--mismatch" in sys.argv else 1
permission_mode = "--permission" in sys.argv
disconnect_prompt = "--disconnect-prompt" in sys.argv


def send(value):
    print(json.dumps(value), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": protocol_version,
                "agentCapabilities": {"loadSession": True},
            },
        })
    elif method == "session/new":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"sessionId": "session-1"}})
    elif method == "session/load":
        send({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"sessionId": params["sessionId"], "loaded": True},
        })
    elif method == "session/prompt":
        if disconnect_prompt:
            raise SystemExit(9)
        if permission_mode:
            send({
                "jsonrpc": "2.0",
                "id": 900,
                "method": "session/request_permission",
                "params": {
                    "sessionId": params["sessionId"],
                    "title": "Read file",
                    "operation": "read_file",
                    "details": "/tmp/example",
                },
            })
        send({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": params["sessionId"],
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "Hello over ACP"},
                },
            },
        })
        send({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"stopReason": "end_turn"},
        })
    elif method == "session/cancel":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"cancelled": True}})
