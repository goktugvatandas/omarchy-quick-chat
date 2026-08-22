import QtQuick
import qs.Commons
import qs.Ui
import "../models/ChatModel.js" as ChatModel

Item {
  id: root

  property string profileId: "codex"
  property string cliState: "Starting"
  property bool privateMode: false
  property bool maximized: false
  property string activePage: "chat"
  property string privateShortcut: ""
  property string historyShortcut: ""
  property string settingsShortcut: ""
  property var profiles: [
    { id: "codex", name: "Codex", icon: "󰚩" },
    { id: "claude", name: "Claude Code", icon: "󰚩" },
    { id: "opencode", name: "OpenCode", icon: "󰚩" },
    { id: "grok", name: "Grok", icon: "󰚩" },
    { id: "cursor", name: "Cursor", icon: "󰚩" },
    { id: "pi", name: "Pi", icon: "󰚩" }
  ]

  signal privateChanged(bool enabled)
  signal historyRequested()
  signal settingsRequested()
  signal moveRequested()
  signal maximizeRequested()

  function activeProfile() {
    for (var index = 0; index < root.profiles.length; index += 1) {
      if (root.profiles[index].id === root.profileId) return root.profiles[index]
    }
    return null
  }

  function focusMaximize() {
    maximizeButton.forceActiveFocus()
  }

  implicitHeight: Math.max(agentIcon.implicitHeight, identity.implicitHeight, actions.implicitHeight)

  Text {
    id: agentIcon
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    text: root.activeProfile() ? (root.activeProfile().icon || "󰚩") : "󰚩"
    textFormat: Text.PlainText
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

    Text {
      width: parent.width
      text: root.activeProfile() ? root.activeProfile().name : "Quick Chat"
      textFormat: Text.PlainText
      color: Color.popups.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.body
      font.bold: true
      elide: Text.ElideRight
    }

    Text {
      width: parent.width
      text: ChatModel.statusLabel(root.cliState).toUpperCase()
      textFormat: Text.PlainText
      color: Qt.darker(Color.popups.text, 1.4)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
      font.bold: true
      font.letterSpacing: 1.2
      elide: Text.ElideRight
    }
  }

  MouseArea {
    id: headerDrag
    anchors.left: parent.left
    anchors.right: actions.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    cursorShape: Qt.SizeAllCursor
    onPressed: root.moveRequested()
    onDoubleClicked: root.maximizeRequested()
  }

  Row {
    id: actions
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.spacing.sm

    Button {
      iconText: root.privateMode ? "󰈉" : "󰈈"
      tooltipText: root.privateMode
        ? "Private conversation on"
          + (root.privateShortcut ? " (" + root.privateShortcut + ")" : "")
        : "Private conversation off"
          + (root.privateShortcut ? " (" + root.privateShortcut + ")" : "")
      selected: root.privateMode
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.privateChanged(!root.privateMode)
    }

    Button {
      iconText: "󰋚"
      tooltipText: (root.activePage === "history" ? "Back to chat" : "History")
        + (root.historyShortcut ? " (" + root.historyShortcut + ")" : "")
      selected: root.activePage === "history"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.historyRequested()
    }

    Button {
      iconText: ""
      tooltipText: (root.activePage === "profiles" ? "Back to chat" : "Settings")
        + (root.settingsShortcut ? " (" + root.settingsShortcut + ")" : "")
      selected: root.activePage === "profiles"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.settingsRequested()
    }

    Button {
      id: maximizeButton
      iconText: root.maximized ? "󰖯" : "󰖲"
      tooltipText: root.maximized ? "Restore window" : "Maximize window"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.maximizeRequested()
    }
  }
}
