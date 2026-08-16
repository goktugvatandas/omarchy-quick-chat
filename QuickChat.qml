import Quickshell
import Quickshell.Hyprland
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
  property bool closingFromHost: false
  property int openingGeneration: 0
  property int placedGeneration: -1
  property int activatedGeneration: -1
  property bool focusPending: false
  property var quickToplevel: null
  property string openingPayload: "{}"
  readonly property bool isMaximized: Boolean(
    quickToplevel
      && quickToplevel.lastIpcObject
      && Number(quickToplevel.lastIpcObject.fullscreen) === 1
  )

  function parsePayload(payloadJson) {
    try { return JSON.parse(payloadJson || "{}") } catch (error) { return ({}) }
  }

  function open(payloadJson) {
    var payload = parsePayload(payloadJson)
    openingPayload = payloadJson || "{}"
    if (payload.profileId) chat.profileId = payload.profileId
    if (payload.conversationId) chat.conversationId = payload.conversationId
    if (payload.acceptanceFixture) chat.showAcceptanceFixture(payload.acceptanceFixture)

    openingGeneration += 1
    placedGeneration = -1
    activatedGeneration = -1
    focusPending = true
    quickToplevel = null
    closingFromHost = false
    window.visible = true
    Hyprland.refreshToplevels()
    placementTimeout.restart()
    Qt.callLater(tryBindToplevel)
  }

  function close() {
    closingFromHost = true
    focusPending = false
    placementTimeout.stop()
    focusRetry.stop()
    quickToplevel = null
    window.visible = false
    closingFromHost = false
  }

  function requestClose() {
    focusPending = false
    placementTimeout.stop()
    focusRetry.stop()
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "community.quick-chat")
    else
      window.visible = false
  }

  function isQuickChatToplevel(candidate) {
    return Boolean(candidate
      && String(candidate.title || "") === "Quick Chat"
      && String(candidate.address || "").length > 0)
  }

  function findQuickChatToplevel() {
    var active = Hyprland.activeToplevel
    if (isQuickChatToplevel(active)) return active
    var values = Hyprland.toplevels && Hyprland.toplevels.values
      ? Hyprland.toplevels.values : []
    var fallback = null
    for (var index = 0; index < values.length; index += 1) {
      var candidate = values[index]
      if (!isQuickChatToplevel(candidate)) continue
      if (candidate.activated) return candidate
      if (!fallback) fallback = candidate
    }
    return fallback
  }

  function placeCurrentGeneration() {
    if (!quickToplevel || placedGeneration === openingGeneration) return
    var target = String(quickToplevel.address || "")
    if (!target) return
    placedGeneration = openingGeneration
    Hyprland.dispatch("setfloating address:" + target)
    Hyprland.dispatch("resizewindowpixel exact 620 620,address:" + target)
    Hyprland.dispatch("centerwindow 1,address:" + target)
  }

  function finishPendingFocus() {
    if (!focusPending || !quickToplevel || !quickToplevel.activated) return
    focusPending = false
    placementTimeout.stop()
    focusRetry.stop()
    Qt.callLater(function() {
      if (window.visible) chat.focusComposer()
    })
  }

  function tryBindToplevel() {
    if (!window.visible || !focusPending || !placementTimeout.running) return
    if (!quickToplevel) quickToplevel = findQuickChatToplevel()
    if (!quickToplevel) return

    placeCurrentGeneration()
    if (quickToplevel.activated) {
      finishPendingFocus()
      return
    }
    if (activatedGeneration !== openingGeneration && quickToplevel.wayland) {
      activatedGeneration = openingGeneration
      quickToplevel.wayland.activate()
    }
  }

  function startHeaderMove() {
    if (window.visible) window.startSystemMove()
  }

  function toggleMaximized() {
    if (!quickToplevel) quickToplevel = findQuickChatToplevel()
    if (!quickToplevel || !quickToplevel.address) return
    var target = quickToplevel.address
    var next = isMaximized ? "0 0," : "1 1,"
    Hyprland.dispatch("fullscreenstate " + next + "address:" + target)
  }

  Connections {
    target: Hyprland
    function onActiveToplevelChanged() {
      if (root.focusPending) root.tryBindToplevel()
    }
  }

  Connections {
    target: root.quickToplevel
    ignoreUnknownSignals: true
    function onActivatedChanged() { root.finishPendingFocus() }
  }

  Timer {
    id: focusRetry
    interval: 45
    repeat: true
    running: root.focusPending && placementTimeout.running && window.visible
    onTriggered: {
      Hyprland.refreshToplevels()
      root.tryBindToplevel()
    }
  }

  Timer {
    id: placementTimeout
    interval: 1500
    repeat: false
    onTriggered: root.focusPending = false
  }

  FloatingWindow {
    id: window
    title: "Quick Chat"
    color: Color.popups.background
    implicitWidth: Style.space(620)
    implicitHeight: Style.space(620)
    minimumSize: Qt.size(Style.space(480), Style.space(520))

    onVisibleChanged: {
      if (!visible && !root.closingFromHost)
        root.requestClose()
    }

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
        maximized: root.isMaximized
        onMoveRequested: root.startHeaderMove()
        onMaximizeRequested: root.toggleMaximized()
      }

      Keys.onEscapePressed: function(event) {
        root.requestClose()
        event.accepted = true
      }
    }
  }
}
