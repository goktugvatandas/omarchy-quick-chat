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
    if (payload.conversationId) chat.conversationId = payload.conversationId
    chat.activateProfile(payload.profileId || "")
    if (payload.acceptanceFixture) chat.showAcceptanceFixture(payload.acceptanceFixture)

    openingGeneration += 1
    placedGeneration = -1
    activatedGeneration = -1
    focusPending = true
    quickToplevel = null
    closingFromHost = false
    chat.focusComposer()
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
      shell.hide((manifest && manifest.id) || "goktugvatandas.quick-chat")
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

  function normalizedWindowAddress(address) {
    var raw = String(address || "").trim()
    if (!/^(0x)?[0-9a-fA-F]+$/.test(raw)) return ""
    return raw.indexOf("0x") === 0 ? raw : "0x" + raw
  }

  function windowSelector(address) {
    var normalized = normalizedWindowAddress(address)
    return normalized ? "address:" + normalized : ""
  }

  function dispatchWindow(legacyRequest, luaRequest) {
    if (!legacyRequest || !luaRequest) return
    Hyprland.dispatch(Hyprland.usingLua ? luaRequest : legacyRequest)
  }

  function placeCurrentGeneration() {
    if (!quickToplevel || placedGeneration === openingGeneration) return
    var selector = windowSelector(quickToplevel.address)
    if (!selector) return
    placedGeneration = openingGeneration
    dispatchWindow(
      "setfloating " + selector,
      'hl.dsp.window.float({ action = "set", window = "' + selector + '" })'
    )
    dispatchWindow(
      "resizewindowpixel exact 620 620," + selector,
      'hl.dsp.window.resize({ x = 620, y = 620, window = "' + selector + '" })'
    )
    dispatchWindow(
      "centerwindow 1," + selector,
      'hl.dsp.window.center({ window = "' + selector + '" })'
    )
  }

  function finishPendingFocus() {
    if (!focusPending || !quickToplevel || !quickToplevel.activated) return
    focusPending = false
    placementTimeout.stop()
    focusRetry.stop()
    // The activation event can land seconds after summon. By then the user
    // may have navigated to another page, so only focus what is showing.
    Qt.callLater(function() {
      if (window.visible) chat.focusActivePage()
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
    var selector = windowSelector(quickToplevel.address)
    if (!selector) return
    var action = isMaximized ? "unset" : "set"
    var legacyState = isMaximized ? "0 0" : "1 1"
    dispatchWindow(
      "fullscreenstate " + legacyState + "," + selector,
      'hl.dsp.window.fullscreen({ mode = "maximized", action = "'
        + action + '", window = "' + selector + '" })'
    )
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
    visible: false
    color: Color.popups.background
    implicitWidth: Style.space(620)
    implicitHeight: Style.space(620)
    minimumSize: Qt.size(Style.space(480), Style.space(520))

    onVisibleChanged: {
      if (!visible && !root.closingFromHost)
        root.requestClose()
    }

    WindowShortcuts {
      enabled: window.visible && !chat.hasBlockingTransient
      shortcuts: chat.profileState ? chat.profileState.uiShortcuts : ({})
      onFocusInputRequested: chat.focusComposer()
      onModelRequested: chat.openAgentPicker()
      onEffortRequested: chat.openEffortPicker()
      onHistoryRequested: chat.togglePage("history")
      onSettingsRequested: chat.togglePage("profiles")
      onPrivateRequested: chat.togglePrivate()
      onNewChatRequested: chat.newConversation()
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

      Keys.priority: Keys.AfterItem
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
          if (!chat.handleBack()) root.requestClose()
          event.accepted = true
        } else if (event.key === Qt.Key_Left
                   && event.modifiers === Qt.AltModifier) {
          chat.handleBack()
          event.accepted = true
        }
      }
    }
  }
}
