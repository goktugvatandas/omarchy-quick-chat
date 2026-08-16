import QtQuick
import qs.Commons
import qs.Ui

Item {
  id: root

  property string profileId: "codex"
  property string cliState: "Starting"
  property bool privateMode: false
  property bool expanded: false
  property string activePage: "chat"
  property var profiles: [
    { id: "codex", name: "Codex", icon: "󰚩" },
    { id: "claude", name: "Claude Code", icon: "󰚩" },
    { id: "opencode", name: "OpenCode", icon: "󰚩" },
    { id: "grok", name: "Grok", icon: "󰚩" },
    { id: "cursor", name: "Cursor", icon: "󰚩" },
    { id: "pi", name: "Pi", icon: "󰚩" }
  ]

  signal profileSelected(string profileId)
  signal privateChanged(bool enabled)
  signal expandRequested()
  signal historyRequested()
  signal settingsRequested()

  function activeProfile() {
    for (var index = 0; index < root.profiles.length; index += 1) {
      if (root.profiles[index].id === root.profileId) return root.profiles[index]
    }
    return null
  }

  implicitHeight: Math.max(agentIcon.implicitHeight, identity.implicitHeight, actions.implicitHeight)

  Text {
    id: agentIcon
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    text: root.activeProfile() ? (root.activeProfile().icon || "󰚩") : "󰚩"
    color: Color.popups.text
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.display
    width: Style.space(48)
    horizontalAlignment: Text.AlignHCenter
  }

  Column {
    id: identity
    anchors.left: agentIcon.right
    anchors.leftMargin: Style.space(14)
    anchors.right: actions.left
    anchors.rightMargin: Style.space(14)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.spacing.labelGap

    Dropdown {
      id: profilePicker
      width: Math.min(parent.width, Style.space(230))
      showLabel: false
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      value: root.profileId
      options: root.profiles.map(function(profile) {
        return { value: profile.id, label: profile.name }
      })
      onChanged: function(value) { root.profileSelected(value) }
    }

    Text {
      width: parent.width
      text: root.cliState.toUpperCase()
      color: Qt.darker(Color.popups.text, 1.4)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
      font.bold: true
      font.letterSpacing: 1.2
      elide: Text.ElideRight
    }
  }

  Row {
    id: actions
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.spacing.sm

    ToggleSwitch {
      id: privateSwitch
      checked: root.privateMode
      foreground: Color.popups.text
      accent: Color.accent
      anchors.verticalCenter: parent.verticalCenter
      onToggled: root.privateChanged(!root.privateMode)

      PanelToolTip {
        visible: privateSwitch.containsMouse
        text: root.privateMode ? "Private conversation on" : "Private conversation off"
        fontFamily: Style.font.menuFamily
      }
    }

    Button {
      iconText: "󰋚"
      tooltipText: "History"
      selected: root.expanded && root.activePage === "history"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.historyRequested()
    }

    Button {
      iconText: ""
      tooltipText: "Profiles and settings"
      selected: root.expanded && root.activePage === "profiles"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.settingsRequested()
    }

    Button {
      iconText: root.expanded ? "󰁍" : "󰁌"
      tooltipText: root.expanded ? "Compact view" : "Open workspace"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.expandRequested()
    }
  }
}
