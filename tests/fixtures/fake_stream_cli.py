#!/usr/bin/python3
import json
import signal
import sys
import time


mode = sys.argv[1]

if mode == "stream":
    prompt = sys.stdin.read()
    print(json.dumps({"type": "delta", "text": prompt}), flush=True)
elif mode == "stderr":
    print("assistant text", flush=True)
    print("private diagnostic", file=sys.stderr, flush=True)
elif mode == "ansi":
    print("\033[31mred\033[0m\x00 text", flush=True)
elif mode == "sleep":
    time.sleep(30)
elif mode == "ignore-int":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("ready", flush=True)
    time.sleep(30)
elif mode == "fail":
    print("failed safely", file=sys.stderr, flush=True)
    raise SystemExit(7)
