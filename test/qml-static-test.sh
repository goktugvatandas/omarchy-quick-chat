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
readme = (root / "README.md").read_text()
readme_lower = readme.lower()

for stale_phrase in ("expanded workspace", "overlay"):
    assert stale_phrase not in readme_lower, (
        f"README must not describe the retired {stale_phrase} behavior"
    )
assert not re.search(r"Ctrl\+Enter[^\n.]{0,80}\bsend", readme, re.IGNORECASE), (
    "README must not describe Ctrl+Enter as send"
)
for shortcut in (
    "Ctrl+L", "Ctrl+K", "Ctrl+.", "Ctrl+H", "Ctrl+,", "Ctrl+Shift+P", "Ctrl+N"
):
    assert shortcut in readme, f"README must document the {shortcut} default"
for behavior in (
    "Super+T",
    "Super+drag",
    "header drag",
    "standard maximize",
    "inherited opacity",
):
    assert behavior.lower() in readme_lower, f"README must document {behavior}"
for effort_mapping in (
    'model_reasoning_effort="',
    "Claude `--effort`",
    "OpenCode `--variant`",
    "Grok `--reasoning-effort`",
    "Cursor `effort=`",
    "Pi `--thinking`",
):
    assert effort_mapping in readme, (
        f"README must document the native effort mapping {effort_mapping}"
    )

assert re.search(r"\bItem\s*\{", menu), "QuickChat.qml root must be an Item"
assert re.search(r"\bItem\s*\{", service), "Service.qml root must be an Item"
assert re.search(r"\bfunction\s+open\s*\(", menu), "menu must implement open()"
assert re.search(r"\bfunction\s+close\s*\(", menu), "menu must implement close()"
assert "Enter sends;\n`Ctrl+Enter` adds a line." in readme, (
    "usage documentation must match the composer key behavior"
)
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
assert "FloatingWindow {" in menu, "Quick Chat must use a standard desktop window"
assert "PanelWindow {" not in menu, "Quick Chat must not remain a layer-shell panel"
assert "Quickshell.Wayland" not in menu
assert "WlrLayershell" not in menu
assert "WlrKeyboardFocus" not in menu
assert "opacity:" not in menu, "Quick Chat must inherit compositor opacity"
for qml_path in root.rglob("*.qml"):
    assert not re.search(r"\bopacity\s*:", qml_path.read_text()), (
        f"{qml_path.name} must not override inherited compositor opacity"
    )
assert 'title: "Quick Chat"' in menu
assert "implicitWidth: Style.space(620)" in menu
assert "implicitHeight: Style.space(620)" in menu
assert "minimumSize: Qt.size(" in menu
assert 'Hyprland.dispatch("setfloating address:"' in menu
assert 'Hyprland.dispatch("resizewindowpixel exact 620 620,address:"' in menu
assert 'Hyprland.dispatch("centerwindow 1,address:"' in menu
assert 'Hyprland.dispatch("fullscreenstate "' in menu
assert "window.startSystemMove()" in menu
assert "quickToplevel.wayland.activate()" in menu
assert "Number(quickToplevel.lastIpcObject.fullscreen) === 1" in menu
assert "openingGeneration += 1" in menu
assert "placedGeneration = openingGeneration" in menu
assert 'String(candidate.title || "") === "Quick Chat"' in menu
assert 'String(candidate.address || "").length > 0' in menu
assert "focusPending && placementTimeout.running" in menu
assert 'Hyprland.dispatch("setfloating")' not in menu
assert 'Hyprland.dispatch("fullscreenstate " + next)' not in menu
assert "property bool expanded" not in menu
assert "requestedWidth" not in menu and "requestedHeight" not in menu
assert "focusPrimed" not in menu
assert "WindowShortcuts {" in menu
assert "shortcuts: chat.profileState ? chat.profileState.uiShortcuts : ({})" in menu
assert "Keys.priority: Keys.AfterItem" in menu
assert "event.key === Qt.Key_Escape" in menu
assert "event.key === Qt.Key_Left" in menu and "Qt.AltModifier" in menu
assert "chat.handleBack()" in menu and "root.requestClose()" in menu
assert "HyprlandFocusGrab" not in menu, (
    "Quick Chat must stay open without preventing focus on other windows"
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
assert 'property string activePage: "chat"' in chat_surface, (
    "the standard window must use a focused page model"
)
assert "StackLayout {" in chat_surface, (
    "the standard window must show one workspace page at a time"
)
assert "historyOpen" not in chat_surface, (
    "history must be a focused page, not a cramped side drawer"
)
assert not all(label in chat_surface for label in (
    'text: "Chat"', 'text: "History"', 'text: "Profiles"'
)), "expanded mode must not use a redundant page tab bar"
assert 'root.togglePage("history")' in chat_surface, (
    "the history icon must toggle between history and chat"
)
assert 'root.togglePage("profiles")' in chat_surface, (
    "the settings icon must toggle between settings and chat"
)
assert "expandRequested" not in chat_surface
assert "property bool expanded" not in chat_surface
assert "toggleExpanded" not in chat_surface
assert "readonly property bool hasBlockingTransient" in chat_surface
assert "function handleBack()" in chat_surface
assert "function openAgentPicker()" in chat_surface
assert "function openEffortPicker()" in chat_surface
assert "function togglePrivate()" in chat_surface
open_page = re.search(
    r"function\s+openPage\s*\([^)]*\)\s*\{(.*?)\n\s*\}\n\n\s*function",
    chat_surface,
    flags=re.DOTALL,
)
assert open_page, "chat surface must keep a page-opening function"
for forbidden in ("Hyprland", "Style.space", "maximize", "expand", "width", "height"):
    assert forbidden not in open_page.group(1), (
        f"opening a page must not change window state through {forbidden}"
    )

chat_header = (root / "ui/ChatHeader.qml").read_text()
assert "Dropdown {" not in chat_header, (
    "agent selection belongs beside the composer, not in the header"
)
assert "ToggleSwitch {" not in chat_header, (
    "private mode must use an icon toggle instead of a switch"
)
assert 'tooltipText: root.privateMode' in chat_header, (
    "the private icon must expose its current state accessibly"
)
assert 'root.privateMode ? "󰈉" : "󰈈"' in chat_header, (
    "private mode must use distinct eye-off and eye icons"
)
assert "signal moveRequested()" in chat_header
assert "signal maximizeRequested()" in chat_header
assert "property bool maximized" in chat_header
assert "onPressed: root.moveRequested()" in chat_header
assert "onDoubleClicked: root.maximizeRequested()" in chat_header
assert "anchors.right: actions.left" in chat_header, (
    "the draggable header region must stop before its action buttons"
)
assert "expandRequested" not in chat_header and "property bool expanded" not in chat_header
for shortcut_property in ("privateShortcut", "historyShortcut", "settingsShortcut"):
    assert f"property string {shortcut_property}" in chat_header

composer = (root / "ui/Composer.qml").read_text()
assert "HarnessModelPicker {" in composer, (
    "the unified agent/model picker must sit beside the prompt controls"
)
harness_index = composer.index("HarnessModelPicker {")
effort_index = composer.index("ThinkingEffortPicker {")
first_action_index = composer.index("Button {", harness_index)
assert harness_index < effort_index < first_action_index, (
    "the thinking-effort picker must immediately follow the agent/model picker"
)
assert "Qt.Key_Tab" in composer and "agentPicker.focusTrigger()" in composer, (
    "keyboard users must be able to move from the prompt to its adjacent picker"
)
assert "function insertNewline()" in composer, (
    "the composer must own deterministic multiline insertion"
)
assert re.search(
    r"event\.modifiers\s*&\s*Qt\.ControlModifier\)\s*\{\s*root\.insertNewline\(\)",
    composer,
), "Ctrl+Enter must insert a newline"
assert re.search(
    r"else\s*\{\s*if\s*\(!root\.running\s*&&\s*prompt\.text\.trim\(\)\)\s*"
    r"root\.sendRequested\(prompt\.text\)",
    composer,
), "Enter without Ctrl must send"
assert "readonly property bool popupOpen" in composer
assert "function closeTransient()" in composer
assert composer.count("focusable: true") >= 6, (
    "context, stop, and send controls must all be reachable by Tab"
)

harness_picker = (root / "ui/HarnessModelPicker.qml").read_text()
assert "QQC.Popup {" in harness_picker, (
    "the agent/model picker must use one anchored dropdown"
)
assert "expandedProfileId" in harness_picker, (
    "configured harness rows must expand to reveal their models"
)
assert 'root.expandedProfileId = ""' in harness_picker, (
    "opening the picker must keep every harness immediately reachable"
)
assert "modelDiscoveryRequested" in harness_picker, (
    "expanding a harness must trigger live model discovery"
)
assert "selectionRequested" in harness_picker, (
    "a nested model must select both its agent and model"
)
assert "Qt.Key_Right" in harness_picker and "Qt.Key_Left" in harness_picker, (
    "the agent/model tree must expand and collapse with arrow keys"
)

effort_picker = (root / "ui/ThinkingEffortPicker.qml").read_text()
assert "QQC.Popup {" in effort_picker and "modal: false" in effort_picker, (
    "the effort picker must use a non-modal anchored popup"
)
assert "y: -height" in effort_picker, "the effort picker must open upward"
assert "enabled: root.choices.length > 0" in effort_picker, (
    "unsupported models must leave a disabled Default effort indicator"
)
assert 'property string currentLabel: "Default"' in effort_picker, (
    "the effort indicator must default visibly and safely"
)
assert effort_picker.count("QQC.ScrollBar.vertical") == 1, (
    "the bounded effort list must expose exactly one vertical scrollbar"
)
assert "QQC.ScrollBar.horizontal" not in effort_picker, (
    "the effort popup must not render a meaningless horizontal scrollbar"
)
for key in ("Qt.Key_Up", "Qt.Key_Down", "Qt.Key_Home", "Qt.Key_End",
            "Qt.Key_Return", "Qt.Key_Space", "Qt.Key_Escape"):
    assert key in effort_picker, f"effort picker is missing keyboard support for {key}"

message_list = (root / "ui/MessageList.qml").read_text()
assert "TextEdit {" in message_list and "readOnly: true" in message_list, (
    "message text must use a selectable read-only text type"
)
assert "verticalScrollBarEnabled: messages.length > 0" in message_list, (
    "an empty transcript must not render a meaningless scrollbar"
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
    root / "ui/HarnessModelPicker.qml",
    root / "ui/ThinkingEffortPicker.qml",
    root / "ui/FormField.qml",
    root / "ui/HistoryDrawer.qml",
    root / "ui/InlineError.qml",
    root / "ui/MessageList.qml",
    root / "ui/ProfileSettings.qml",
    root / "ui/ShortcutCapture.qml",
    root / "ui/ShortcutEditor.qml",
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
    assert "Color.popups" in source and "Style." in source, (
        f"{component} must bind to the live Omarchy theme"
    )

scroll_view = (root / "ui/ThemedScrollView.qml").read_text()
assert "Controls.ScrollBar.AlwaysOff" in scroll_view, (
    "panel scroll views must not expose a meaningless horizontal scrollbar"
)

profile_settings = (root / "ui/ProfileSettings.qml").read_text()
assert "SearchableDropdown" in profile_settings, (
    "profile models must be selectable from a searchable discovered catalog"
)
assert "modelDiscoveryRequested" in profile_settings, (
    "profile settings must expose model discovery and refresh"
)
assert "if (!visible || !activeProfile) return" in profile_settings, (
    "model discovery must not delay chat while profile settings are hidden"
)
assert "thinkingEffort: effortPicker.value" in profile_settings, (
    "profile settings must serialize the selected thinking effort"
)
assert "ShortcutEditor {" in profile_settings
assert "signal uiShortcutsChanged(var shortcuts)" in profile_settings
assert "function ensureFocusedItemVisible" in profile_settings
assert "shortcutCaptureActive: shortcutEditor.captureActive" in profile_settings

window_shortcuts = (root / "ui/WindowShortcuts.qml").read_text()
assert window_shortcuts.count("Shortcut {") == 7, (
    "there must be exactly one window shortcut per configurable action"
)
shortcut_actions = (
    "focusInput", "model", "effort", "history", "settings", "private", "newChat"
)
for action in shortcut_actions:
    assert f'sequence: root.configuredSequence("{action}")' in window_shortcuts
    assert f"signal {action}Requested()" in window_shortcuts
assert window_shortcuts.count("context: Qt.WindowShortcut") == 7
for literal in ("Ctrl+L", "Ctrl+K", "Ctrl+.", "Ctrl+H", "Ctrl+,", "Ctrl+Shift+P", "Ctrl+N"):
    assert literal not in window_shortcuts, "router defaults must come from config"

shortcut_capture = (root / "ui/ShortcutCapture.qml").read_text()
assert "event.isAutoRepeat" in shortcut_capture
assert "signal sequenceCaptured(string sequence)" in shortcut_capture
assert "Qt.Key_Escape" in shortcut_capture and "captureCanceled" in shortcut_capture
for modifier in ("Ctrl", "Alt", "Shift", "Meta"):
    assert modifier in shortcut_capture

shortcut_editor = (root / "ui/ShortcutEditor.qml").read_text()
assert "ProfileModel.setUiShortcuts" in shortcut_editor
assert "ProfileModel.resetUiShortcuts" in shortcut_editor
assert "property bool captureActive" in shortcut_editor
assert "signal updateRequested(var shortcuts)" in shortcut_editor
assert "signal shortcutsChanged" not in shortcut_editor, (
    "a shortcuts property already owns the automatic shortcutsChanged signal"
)
assert "onUpdateRequested:" in profile_settings
assert shortcut_editor.count("Default ") >= 7
for literal in ("Ctrl+L", "Ctrl+K", "Ctrl+.", "Ctrl+H", "Ctrl+,", "Ctrl+Shift+P", "Ctrl+N"):
    assert literal in shortcut_editor, f"settings must present the {literal} default"

history_drawer = (root / "ui/HistoryDrawer.qml").read_text()
for key in ("Qt.Key_Home", "Qt.Key_End", "Qt.Key_Space", "Qt.Key_Return"):
    assert key in history_drawer, f"history is missing {key} keyboard behavior"
assert "event.text === \"n\"" not in history_drawer, (
    "new chat must use the configurable Ctrl+N action, not a bare letter"
)
assert 'type: "models.list"' in chat_surface, (
    "chat surface must request model catalogs through the bridge"
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
