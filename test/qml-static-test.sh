#!/bin/bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
menu = (root / "QuickChat.qml").read_text()
service = (root / "Service.qml").read_text()

assert re.search(r"\bItem\s*\{", menu), "QuickChat.qml root must be an Item"
assert re.search(r"\bItem\s*\{", service), "Service.qml root must be an Item"
assert re.search(r"\bfunction\s+open\s*\(", menu), "menu must implement open()"
assert re.search(r"\bfunction\s+close\s*\(", menu), "menu must implement close()"

for source, name in ((menu, "QuickChat.qml"), (service, "Service.qml")):
    for prop in ("omarchyPath", "shell", "manifest", "pluginRegistry"):
        assert re.search(rf"\bproperty\s+\w+\s+{prop}\b", source), (
            f"{name} must expose {prop}"
        )
PY

if command -v qmllint >/dev/null 2>&1; then
  qmllint "$ROOT/QuickChat.qml" "$ROOT/Service.qml"
fi
