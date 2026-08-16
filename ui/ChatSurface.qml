import QtQuick
import QtQuick.Layouts
import qs.Commons
import "../models/ChatModel.js" as ChatModel

Item {
  id: root

  property var manifest: null
  property string profileId: "codex"
  property string conversationId: "conversation-" + Date.now()
  property bool privateMode: false
  property bool expanded: false
  property var chatState: ChatModel.initialState(conversationId, profileId)

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
      root.chatState = ChatModel.reduce(root.chatState, event)
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

  ColumnLayout {
    anchors.fill: parent
    spacing: Style.spacing.controlGap

    ChatHeader {
      Layout.fillWidth: true
      profileId: root.profileId
      cliState: bridge.ready ? root.chatState.status : "Starting bridge"
      privateMode: root.privateMode
      onProfileSelected: function(value) { root.selectProfile(value) }
      onPrivateChanged: function(value) { root.privateMode = value }
      onExpandRequested: root.expandRequested()
      onHistoryRequested: root.historyRequested()
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
}
