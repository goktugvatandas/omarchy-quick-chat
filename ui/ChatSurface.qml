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
  property var adapterStates: []
  property var attachments: []
  property var contextRequests: ({})
  property string pendingPrompt: ""
  property bool historyOpen: false
  property string profilesRequestId: ""
  property string historyRequestId: ""
  property string historyGetRequestId: ""
  property string clearRequestId: ""
  property string profileSaveRequestId: ""

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

  function saveProfiles(nextState) {
    profileState = nextState
    profileSaveRequestId = newRequestId()
    bridge.send({
      type: "profiles.save",
      requestId: profileSaveRequestId,
      config: ProfileModel.serialize(nextState)
    })
  }

  function sendPrompt(prompt) {
    var trimmed = prompt.trim()
    if (!trimmed || chatState.running) return
    var capabilities = activeCapabilities()
    var hasImages = attachments.some(function(attachment) {
      return attachment.kind === "image"
    })
    if (hasImages && capabilities && capabilities.native_images === false) {
      pendingPrompt = prompt
      imageChoice.opened = true
      return
    }
    dispatchPrompt(prompt)
  }

  function dispatchPrompt(prompt) {
    var requestId = newRequestId()
    chatState = ChatModel.beginRun(chatState, requestId, prompt, attachments, privateMode)
    bridge.send({
      type: "run",
      requestId: requestId,
      conversationId: conversationId,
      profileId: profileId,
      prompt: prompt,
      attachments: attachments,
      private: privateMode
    })
    composer.text = ""
  }

  function activeCapabilities() {
    var profile = activeProfile()
    if (!profile) return null
    for (var index = 0; index < adapterStates.length; index += 1) {
      if (adapterStates[index].id === profile.adapterId)
        return adapterStates[index].capabilities
    }
    return null
  }

  function requestContext(mode) {
    var requestId = newRequestId()
    var requests = Object.assign({}, contextRequests)
    requests[requestId] = { type: "capture", mode: mode }
    contextRequests = requests
    bridge.send({ type: "context.capture", requestId: requestId, mode: mode })
  }

  function requestOcr(attachmentId) {
    var requestId = newRequestId()
    var requests = Object.assign({}, contextRequests)
    requests[requestId] = { type: "ocr", attachmentId: attachmentId }
    contextRequests = requests
    bridge.send({
      type: "context.ocr",
      requestId: requestId,
      attachmentId: attachmentId
    })
  }

  function removeAttachment(attachmentId) {
    attachments = attachments.filter(function(attachment) {
      return attachment.id !== attachmentId
    })
    bridge.send({
      type: "context.remove",
      requestId: newRequestId(),
      attachmentId: attachmentId
    })
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
        root.adapterStates = event.data.adapters || []
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
      } else if (event.type === "complete" && event.requestId === root.profileSaveRequestId) {
        root.profileState = ProfileModel.normalize(event.data.config)
        if (!root.activeProfile()) root.profileId = root.profileState.selectedId
      } else if (event.type === "complete" && root.contextRequests[event.requestId]) {
        if (event.data.attachment)
          root.attachments = root.attachments.concat([event.data.attachment])
        var requests = Object.assign({}, root.contextRequests)
        delete requests[event.requestId]
        root.contextRequests = requests
      } else {
        root.chatState = ChatModel.reduce(root.chatState, event)
        if ((event.type === "complete" || event.type === "error")
            && event.requestId === root.chatState.activeRequestId) {
          root.attachments = []
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

      AttachmentPreview {
        Layout.fillWidth: true
        visible: root.attachments.length > 0
        attachments: root.attachments
        onRemoveRequested: function(identifier) { root.removeAttachment(identifier) }
        onOcrRequested: function(identifier) { root.requestOcr(identifier) }
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
        attachmentCount: root.attachments.length
        onSendRequested: function(prompt) { root.sendPrompt(prompt) }
        onContextRequested: function(mode) { root.requestContext(mode) }
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
        root.saveProfiles(ProfileModel.setHistoryLimit(root.profileState, value))
      }
      onProfilePatchRequested: function(values) {
        root.saveProfiles(ProfileModel.update(root.profileState, {
          profileId: root.profileId,
          values: values
        }))
      }
      onDuplicateRequested: root.saveProfiles(
        ProfileModel.duplicate(root.profileState, root.profileId)
      )
      onRemoveRequested: {
        var next = ProfileModel.remove(root.profileState, root.profileId, true)
        root.profileId = next.selectedId
        root.saveProfiles(next)
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

  ConfirmDialog {
    id: imageChoice
    anchors.fill: parent
    message: "This profile cannot receive images in process mode. Convert them to text or switch profile."
    cancelText: "Switch profile"
    confirmText: "Convert to text"
    onCanceled: {
      opened = false
      root.pendingPrompt = ""
    }
    onConfirmed: {
      opened = false
      for (var index = 0; index < root.attachments.length; index += 1) {
        if (root.attachments[index].kind === "image")
          root.requestOcr(root.attachments[index].id)
      }
    }
  }
}
