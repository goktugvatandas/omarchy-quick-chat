import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

RowLayout {
  id: root

  property string profileId: "codex"
  property string cliState: "Starting"
  property bool privateMode: false
  property var profiles: [
    { id: "codex", name: "Codex" },
    { id: "claude", name: "Claude Code" },
    { id: "opencode", name: "OpenCode" },
    { id: "grok", name: "Grok" },
    { id: "cursor", name: "Cursor" },
    { id: "pi", name: "Pi" }
  ]

  signal profileSelected(string profileId)
  signal privateChanged(bool enabled)
  signal expandRequested()
  signal historyRequested()

  spacing: Style.spacing.controlGap

  ComboBox {
    id: profilePicker
    Layout.preferredWidth: Style.space(180)
    textRole: "name"
    valueRole: "id"
    model: root.profiles
    onActivated: root.profileSelected(currentValue)
    Component.onCompleted: {
      for (var index = 0; index < root.profiles.length; index += 1) {
        if (root.profiles[index].id === root.profileId) currentIndex = index
      }
    }
  }

  Text {
    Layout.fillWidth: true
    text: root.cliState
    color: Color.menu.text
    opacity: 0.7
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.caption
    elide: Text.ElideRight
  }

  CheckBox {
    text: "Private"
    checked: root.privateMode
    onToggled: root.privateChanged(checked)
  }

  Button {
    text: "History"
    onClicked: root.historyRequested()
  }

  Button {
    text: "Expand"
    onClicked: root.expandRequested()
  }
}
