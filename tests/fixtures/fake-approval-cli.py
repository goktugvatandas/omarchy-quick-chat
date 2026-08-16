#!/usr/bin/python3
import json

print(json.dumps({
    "type": "tool_request",
    "approvalId": "approval-1",
    "title": "Read a protected file",
    "operation": "read_file",
    "details": "/tmp/example",
}), flush=True)
