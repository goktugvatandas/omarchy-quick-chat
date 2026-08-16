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

bridge = (root / "BridgeClient.qml").read_text()
assert "stdinEnabled: true" in bridge, "bridge process must accept JSONL stdin"
assert "SplitParser" in bridge, "bridge stdout must be split into lines"
assert "JSON.stringify(object) + \"\\n\"" in bridge, "send() must write one JSON line"
assert "stderr: SplitParser" in bridge, "stderr must remain separate"

service = (root / "Service.qml").read_text()
shortcut = (root / "ShortcutDelegate.qml").read_text()
assert "watchChanges: true" in service, "service must watch profile configuration"
assert "GlobalShortcut" in shortcut, "profile shortcut target is required"
assert 'appid: "community.quick-chat"' in shortcut, "shortcut app id must be immutable"
assert "Quickshell.execDetached([" in shortcut, "summon must use an argument array"

inline_error = (root / "ui/InlineError.qml").read_text()
for code in (
    "not_installed", "authentication_required", "unsupported_version",
    "invalid_working_directory", "capture_failed", "timeout",
    "bridge_exited", "approval_not_relayable", "history_recovered",
):
    assert code in inline_error, f"missing recovery action for {code}"

approval = (root / "ui/ApprovalCard.qml").read_text()
assert "Approve once" in approval
assert "approve always" not in approval.lower()

for source, name in ((menu, "QuickChat.qml"), (service, "Service.qml")):
    for prop in ("omarchyPath", "shell", "manifest", "pluginRegistry"):
        assert re.search(rf"\bproperty\s+\w+\s+{prop}\b", source), (
            f"{name} must expose {prop}"
        )
PY

if command -v qmllint >/dev/null 2>&1; then
  qmllint "$ROOT/QuickChat.qml" "$ROOT/Service.qml" "$ROOT/BridgeClient.qml"
fi
