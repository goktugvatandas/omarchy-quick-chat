import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui
import "ui"

Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property var service: null
  property bool opened: false
  property bool expanded: false
  property string openingPayload: "{}"

  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (error) { payload = ({}) }
    openingPayload = payloadJson || "{}"
    if (payload.profileId) chat.profileId = payload.profileId
    if (payload.conversationId) chat.conversationId = payload.conversationId
    if (payload.acceptanceFixture === "settings" || payload.acceptanceFixture === "history")
      root.expanded = true
    else if (payload.acceptanceFixture) root.expanded = false
    if (payload.acceptanceFixture) chat.showAcceptanceFixture(payload.acceptanceFixture)
    opened = true
    Qt.callLater(function() { chat.focusActivePage() })
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
    readonly property int requestedWidth: root.expanded ? Style.space(760) : Style.space(620)
    readonly property int requestedHeight: root.expanded ? Style.space(760) : Style.space(620)
    implicitWidth: screen
      ? Math.min(requestedWidth, screen.width - Style.gapsOut * 2)
      : requestedWidth
    implicitHeight: screen
      ? Math.min(requestedHeight, root.expanded
          ? screen.height - Style.gapsOut * 2
          : Math.round(screen.height * 0.7))
      : requestedHeight
    color: "transparent"
    WlrLayershell.namespace: "community-quick-chat"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    BorderSurface {
      id: card
      anchors.fill: parent
      radius: Style.cornerRadius
      color: Color.popups.background
      borderSpec: Border.surfaceSpec(
        "popups",
        "border",
        Color.popups.border,
        Math.max(1, Style.space(2))
      )
      padding: Style.spacing.panelPadding

      ChatSurface {
        id: chat
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        manifest: root.manifest
        shell: root.shell
        service: root.service
        expanded: root.expanded
        onExpandRequested: root.expanded = !root.expanded
      }

      Keys.onEscapePressed: function(event) {
        root.dismiss()
        event.accepted = true
      }
    }
  }

  HyprlandFocusGrab {
    active: root.opened && panel.visible
    windows: [panel]
    onCleared: if (root.opened) root.dismiss()
  }
}
