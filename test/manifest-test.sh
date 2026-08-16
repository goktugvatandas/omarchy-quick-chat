#!/bin/bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
assert manifest["schemaVersion"] == 1
assert manifest["id"] == "goktugvatandas.quick-chat"
assert manifest["kinds"] == ["menu", "service"]
assert manifest["keepLoaded"] is True
assert manifest["entryPoints"] == {
    "menu": "QuickChat.qml",
    "service": "Service.qml",
}
for path in manifest["entryPoints"].values():
    assert (root / path).is_file(), path
PY
