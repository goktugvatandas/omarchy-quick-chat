import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

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

  Dropdown {
    id: profilePicker
    Layout.preferredWidth: Style.space(180)
    showLabel: false
    foreground: Color.menu.text
    fontFamily: Style.font.menuFamily
    value: root.profileId
    options: root.profiles.map(function(profile) {
      return { value: profile.id, label: profile.name }
    })
    onChanged: function(value) { root.profileSelected(value) }
  }

  Text {
    Layout.fillWidth: true
    text: root.cliState
    color: Util.alpha(Color.menu.text, 0.7)
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.caption
    elide: Text.ElideRight
  }

  RowLayout {
    spacing: Style.spacing.sm

    Text {
      text: "Private"
      color: Color.menu.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.body
    }

    ToggleSwitch {
      checked: root.privateMode
      foreground: Color.menu.text
      accent: Color.accent
      onToggled: root.privateChanged(!root.privateMode)
    }
  }

  Button {
    text: "History"
    foreground: Color.menu.text
    fontFamily: Style.font.menuFamily
    onClicked: root.historyRequested()
  }

  Button {
    text: "Expand"
    foreground: Color.menu.text
    fontFamily: Style.font.menuFamily
    onClicked: root.expandRequested()
  }
}
