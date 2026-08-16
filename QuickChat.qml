import Quickshell
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui

Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property bool opened: false
  property bool expanded: false
  property string openingPayload: "{}"

  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (error) { payload = ({}) }
    openingPayload = payloadJson || "{}"
    if (payload.profileId) chat.profileId = payload.profileId
    if (payload.conversationId) chat.conversationId = payload.conversationId
    opened = true
    Qt.callLater(function() { chat.focusComposer() })
  }

  function close() {
    opened = false
  }

  function dismiss() {
    opened = false
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "community.quick-chat")
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; right: true; bottom: true; left: true }
    color: "transparent"
    WlrLayershell.namespace: "community-quick-chat"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      width: root.expanded
        ? Math.min(Style.space(1040), panel.width - Style.gapsOut * 2)
        : Math.min(Style.space(620), panel.width - Style.gapsOut * 2)
      height: root.expanded
        ? Math.min(Style.space(760), panel.height - Style.gapsOut * 2)
        : Math.min(Style.space(620), panel.height * 0.7)
      anchors.centerIn: parent
      radius: Style.cornerRadius
      color: Color.menu.background
      borderSpec: Border.surfaceSpec(
        "menu",
        "border",
        Color.menu.border,
        Math.max(1, Style.space(2))
      )
      padding: Style.spacing.panelPadding

      MouseArea { anchors.fill: parent; onClicked: {} }

      ChatSurface {
        id: chat
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        manifest: root.manifest
        shell: root.shell
        expanded: root.expanded
        onExpandRequested: root.expanded = !root.expanded
      }

      Keys.onEscapePressed: function(event) {
        root.dismiss()
        event.accepted = true
      }
    }
  }
}
