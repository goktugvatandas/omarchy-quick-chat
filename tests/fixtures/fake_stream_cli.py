#!/usr/bin/python3
import json
import signal
import subprocess
import sys
import time
from pathlib import Path


mode = sys.argv[1]

if mode == "stream":
    prompt = sys.stdin.read()
    print(json.dumps({"type": "delta", "text": prompt}), flush=True)
elif mode == "stderr":
    print("assistant text", flush=True)
    print("private diagnostic", file=sys.stderr, flush=True)
elif mode == "ansi":
    print("\033[31mred\033[0m\x00 text", flush=True)
elif mode == "oversize-line":
    print("x" * (512 * 1024), flush=True)
elif mode == "write-file":
    with open(sys.argv[2], "wb") as stream:
        stream.write(b"x" * 4096)
elif mode == "spawn-descendant":
    child = subprocess.Popen(
        (sys.executable, "-c", "import time; time.sleep(30)"),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    Path(sys.argv[2]).write_text(str(child.pid))
elif mode == "spawn-detached-descendant":
    child = subprocess.Popen(
        (sys.executable, "-c", "import time; time.sleep(30)"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path(sys.argv[2]).write_text(str(child.pid))
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
