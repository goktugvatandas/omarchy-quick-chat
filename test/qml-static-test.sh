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
assert 'import "ui"' in menu, "menu must import its local UI component directory"
assert re.search(r"\bproperty\s+var\s+service\b", menu), (
    "menu must expose the paired service for shortcut diagnostics"
)
assert "Color.menu.scrim" not in menu, "Quick Chat must not paint a backdrop scrim"
assert not re.search(
    r"anchors\s*\{[^}]*\btop:\s*true[^}]*\bbottom:\s*true",
    menu,
    flags=re.DOTALL,
), "Quick Chat must not create a full-height click-blocking layer"
assert "implicitWidth:" in menu and "implicitHeight:" in menu, (
    "Quick Chat must use a card-sized popup surface"
)
assert "HyprlandFocusGrab" in menu, (
    "outside-click dismissal must not require a full-screen MouseArea"
)

bridge = (root / "BridgeClient.qml").read_text()
assert "stdinEnabled: true" in bridge, "bridge process must accept JSONL stdin"
assert "SplitParser" in bridge, "bridge stdout must be split into lines"
assert "JSON.stringify(object) + \"\\n\"" in bridge, "send() must write one JSON line"
assert "stderr: SplitParser" in bridge, "stderr must remain separate"
assert "onBridgePathChanged: start()" in bridge, (
    "bridge must start after Omarchy injects the plugin manifest"
)

chat_surface = (root / "ui/ChatSurface.qml").read_text()
assert 'import ".."' in chat_surface, (
    "chat surface must import root-level plugin components"
)

message_list = (root / "ui/MessageList.qml").read_text()
assert "TextEdit {" in message_list and "readOnly: true" in message_list, (
    "message text must use a selectable read-only text type"
)

attachment_preview = (root / "ui/AttachmentPreview.qml").read_text()
assert "implicitHeight: childrenRect.height" not in attachment_preview, (
    "Flow implicitHeight is read-only in the supported Qt runtime"
)

themed_consumers = [
    root / "ui/ApprovalCard.qml",
    root / "ui/AttachmentPreview.qml",
    root / "ui/ChatHeader.qml",
    root / "ui/Composer.qml",
    root / "ui/HistoryDrawer.qml",
    root / "ui/InlineError.qml",
    root / "ui/MessageList.qml",
    root / "ui/ProfileSettings.qml",
]
for path in themed_consumers:
    source = path.read_text()
    assert "qs.Commons" in source, f"{path.name} must consume Omarchy theme tokens"
    assert not re.search(r"Qt\.rgba\(\s*[0-9]", source), (
        f"{path.name} must derive colors from the active Omarchy palette"
    )

for name in ("ChatHeader.qml", "Composer.qml", "ProfileSettings.qml"):
    source = (root / "ui" / name).read_text()
    assert not re.search(r"\b(?:ComboBox|CheckBox|TextArea|ScrollView)\s*\{", source), (
        f"{name} must use Omarchy-themed controls"
    )

for component in ("ThemedTextArea.qml", "ThemedScrollView.qml"):
    source = (root / "ui" / component).read_text()
    assert "Color.menu" in source and "Style." in source, (
        f"{component} must bind to the live Omarchy theme"
    )

service = (root / "Service.qml").read_text()
shortcut = (root / "ShortcutDelegate.qml").read_text()
assert "watchChanges: true" in service, "service must watch profile configuration"
assert "GlobalShortcut" in shortcut, "profile shortcut target is required"
assert 'appid: "community.quick-chat"' in shortcut, "shortcut app id must be immutable"
assert "Quickshell.execDetached([" in shortcut, "summon must use an argument array"
assert "onBridgePathChanged:" in service, (
    "shortcut sync must start after Omarchy injects the plugin manifest"
)
assert 'shortcutSync.command = [bridgePath, "shortcuts", "sync"]' in service, (
    "shortcut sync must assign argv before starting its process"
)
assert 'menuInstall.command = [bridgePath, "menu", "install"]' in service, (
    "service must install the Omarchy menu entry after manifest injection"
)

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
