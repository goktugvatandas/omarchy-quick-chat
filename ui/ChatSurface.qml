import QtQuick
import QtQuick.Layouts
import qs.Commons
import "../models/ChatModel.js" as ChatModel
import "../models/ProfileModel.js" as ProfileModel
import qs.Ui

Item {
  id: root

  property var manifest: null
  property string profileId: "codex"
  property string conversationId: "conversation-" + Date.now()
  property bool privateMode: false
  property bool expanded: false
  property var chatState: ChatModel.initialState(conversationId, profileId)
  property var profileState: null
  property var historyItems: []
  property bool historyOpen: false
  property string profilesRequestId: ""
  property string historyRequestId: ""
  property string historyGetRequestId: ""
  property string clearRequestId: ""

  signal expandRequested()
  signal historyRequested()

  function newRequestId() {
    return "request-" + Date.now() + "-" + Math.floor(Math.random() * 1000000)
  }

  function selectProfile(nextProfileId) {
    if (!nextProfileId || chatState.running) return
    profileId = nextProfileId
    chatState = ChatModel.initialState(conversationId, profileId)
  }

  function activeProfile() {
    if (!profileState) return null
    for (var index = 0; index < profileState.profiles.length; index += 1) {
      if (profileState.profiles[index].id === profileId)
        return profileState.profiles[index]
    }
    return null
  }

  function requestProfilesAndHistory() {
    profilesRequestId = newRequestId()
    historyRequestId = newRequestId()
    bridge.send({ type: "profiles", requestId: profilesRequestId })
    bridge.send({ type: "history.list", requestId: historyRequestId })
  }

  function loadConversation(identifier) {
    historyGetRequestId = newRequestId()
    bridge.send({
      type: "history.get",
      requestId: historyGetRequestId,
      conversationId: identifier
    })
  }

  function newConversation() {
    conversationId = "conversation-" + Date.now()
    chatState = ChatModel.initialState(conversationId, profileId)
    historyOpen = false
  }

  function sendPrompt(prompt) {
    var trimmed = prompt.trim()
    if (!trimmed || chatState.running) return
    var requestId = newRequestId()
    chatState = ChatModel.beginRun(chatState, requestId, prompt, [], privateMode)
    bridge.send({
      type: "run",
      requestId: requestId,
      conversationId: conversationId,
      profileId: profileId,
      prompt: prompt,
      attachments: [],
      private: privateMode
    })
    composer.text = ""
  }

  function retry() {
    if (chatState.running || chatState.activeUserIndex < 0) return
    var requestId = newRequestId()
    var user = chatState.messages[chatState.activeUserIndex]
    chatState = ChatModel.retryRun(chatState, requestId)
    bridge.send({
      type: "run",
      requestId: requestId,
      conversationId: conversationId,
      profileId: profileId,
      prompt: user.text,
      attachments: user.attachments || [],
      private: user.private
    })
  }

  function focusComposer() {
    composer.focusInput()
  }

  BridgeClient {
    id: bridge
    manifest: root.manifest
    onEventReceived: function(event) {
      if (event.type === "ready") {
        root.requestProfilesAndHistory()
      } else if (event.type === "complete" && event.requestId === root.profilesRequestId) {
        root.profileState = ProfileModel.normalize(event.data.config)
        root.profileId = root.profileState.selectedId
      } else if (event.type === "complete" && event.requestId === root.historyRequestId) {
        root.historyItems = event.data.conversations || []
      } else if (event.type === "complete" && event.requestId === root.historyGetRequestId) {
        root.chatState = ChatModel.loadConversation(root.chatState, event.data.conversation)
        root.conversationId = root.chatState.conversationId
        root.profileId = root.chatState.profileId
        root.historyOpen = false
      } else if (event.type === "complete" && event.requestId === root.clearRequestId) {
        root.historyItems = []
        root.newConversation()
      } else {
        root.chatState = ChatModel.reduce(root.chatState, event)
        if (event.type === "complete" && event.requestId === root.chatState.activeRequestId) {
          root.historyRequestId = root.newRequestId()
          bridge.send({ type: "history.list", requestId: root.historyRequestId })
        }
      }
    }
    onBridgeFailed: function(message) {
      if (!root.chatState.running) return
      root.chatState = ChatModel.reduce(root.chatState, {
        type: "error",
        requestId: root.chatState.activeRequestId,
        data: { code: "bridge_exited", message: message }
      })
    }
  }

  RowLayout {
    anchors.fill: parent
    spacing: Style.spacing.controlGap

    HistoryDrawer {
      Layout.preferredWidth: Style.space(240)
      Layout.fillHeight: true
      visible: root.expanded || root.historyOpen
      conversations: root.historyItems
      profiles: root.profileState ? root.profileState.profiles : []
      onConversationSelected: function(identifier) { root.loadConversation(identifier) }
      onClearRequested: clearDialog.opened = true
      onNewChatRequested: root.newConversation()
    }

    ColumnLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: Style.spacing.controlGap

      ChatHeader {
        Layout.fillWidth: true
        profileId: root.profileId
        profiles: root.profileState ? root.profileState.profiles : []
        cliState: bridge.ready ? root.chatState.status : "Starting bridge"
        privateMode: root.privateMode
        onProfileSelected: function(value) { root.selectProfile(value) }
        onPrivateChanged: function(value) { root.privateMode = value }
        onExpandRequested: root.expandRequested()
        onHistoryRequested: root.historyOpen = !root.historyOpen
      }

      MessageList {
        Layout.fillWidth: true
        Layout.fillHeight: true
        messages: root.chatState.messages
      }

      InlineError {
        Layout.fillWidth: true
        error: root.chatState.error
        onDismissed: root.chatState = ChatModel.clearError(root.chatState)
        onRetryRequested: root.retry()
      }

      Composer {
        id: composer
        Layout.fillWidth: true
        running: root.chatState.running
        onSendRequested: function(prompt) { root.sendPrompt(prompt) }
        onStopRequested: bridge.send({
          type: "cancel",
          requestId: root.chatState.activeRequestId
        })
      }
    }

    ProfileSettings {
      Layout.preferredWidth: Style.space(230)
      Layout.fillHeight: true
      visible: root.expanded
      profileState: root.profileState
      activeProfile: root.activeProfile()
      onHistoryLimitChanged: function(value) {
        root.profileState = ProfileModel.setHistoryLimit(root.profileState, value)
      }
    }
  }

  ConfirmDialog {
    id: clearDialog
    anchors.fill: parent
    message: "Clear all Quick Chat history? CLI-owned sessions are not deleted."
    confirmText: "Clear"
    onCanceled: opened = false
    onConfirmed: {
      opened = false
      root.clearRequestId = root.newRequestId()
      bridge.send({
        type: "history.clear",
        requestId: root.clearRequestId,
        confirm: true
      })
    }
  }
}
