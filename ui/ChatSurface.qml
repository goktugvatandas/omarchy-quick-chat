import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts
import qs.Commons
import ".."
import "../models/ChatModel.js" as ChatModel
import "../models/EffortModel.js" as EffortModel
import "../models/ProfileModel.js" as ProfileModel
import qs.Ui

Item {
  id: root

  property var manifest: null
  property var shell: null
  property var service: null
  property string profileId: "codex"
  property string conversationId: "conversation-" + Date.now()
  property bool privateMode: false
  property bool maximized: false
  property var chatState: ChatModel.initialState(conversationId, profileId)
  property var profileState: null
  property var historyItems: []
  property var adapterStates: []
  property var attachments: []
  property var contextRequests: ({})
  property var modelCatalogs: ({})
  property var modelCatalogErrors: ({})
  property var modelRequests: ({})
  property string effortStatus: ""
  property string pendingPrompt: ""
  property var pendingApproval: null
  property string pendingClipboard: ""
  property string activePage: "chat"
  property string profilesRequestId: ""
  property string historyRequestId: ""
  property string historyGetRequestId: ""
  property string clearRequestId: ""
  property string profileSaveRequestId: ""

  signal moveRequested()
  signal maximizeRequested()

  function openPage(page) {
    activePage = page
    Qt.callLater(focusActivePage)
  }

  function togglePage(page) {
    if (activePage === page) {
      activePage = "chat"
      Qt.callLater(focusActivePage)
      return
    }
    openPage(page)
  }

  function focusActivePage() {
    if (activePage === "history") historyPage.focusPage()
    else if (activePage === "profiles") profilePage.focusPage()
    else composer.focusInput()
  }

  function newRequestId() {
    return "request-" + Date.now() + "-" + Math.floor(Math.random() * 1000000)
  }

  function selectProfile(nextProfileId) {
    if (!nextProfileId || chatState.running) return
    profileId = nextProfileId
    chatState = ChatModel.initialState(conversationId, profileId)
  }

  function selectProfileModel(nextProfileId, modelId) {
    if (!profileState || !nextProfileId || chatState.running) return
    var profile = null
    for (var index = 0; index < profileState.profiles.length; index += 1) {
      if (profileState.profiles[index].id === nextProfileId) {
        profile = profileState.profiles[index]
        break
      }
    }
    if (!profile) return

    var nextModel = String(modelId || "")
    var profileChanged = profileId !== nextProfileId
    var modelChanged = String(profile.model || "") !== nextModel
    if (!profileChanged && !modelChanged) return

    profileId = nextProfileId
    chatState = ChatModel.initialState(conversationId, profileId)
    if (modelChanged) {
      var values = { model: nextModel || null }
      var candidate = Object.assign({}, profile, values)
      var reconciliation = EffortModel.reconcile(
        profile.thinkingEffort,
        EffortModel.choices(candidate, adapterStates, modelCatalogs)
      )
      if (reconciliation.reset) {
        values.thinkingEffort = null
        setEffortStatus(
          "Thinking effort reset to Default because the new model does not support it."
        )
      }
      saveProfiles(ProfileModel.update(profileState, {
        profileId: nextProfileId,
        values: values
      }))
    }
    Qt.callLater(reconcileActiveThinkingEffort)
    Qt.callLater(focusActivePage)
  }

  function activeProfile() {
    if (!profileState) return null
    for (var index = 0; index < profileState.profiles.length; index += 1) {
      if (profileState.profiles[index].id === profileId)
        return profileState.profiles[index]
    }
    return null
  }

  function activeEffortChoices() {
    return EffortModel.choices(activeProfile(), adapterStates, modelCatalogs)
  }

  function setEffortStatus(message) {
    effortStatus = String(message || "")
    if (effortStatus) effortStatusTimer.restart()
  }

  function selectThinkingEffort(value) {
    var profile = activeProfile()
    if (!profile || !profileState || chatState.running) return
    var requested = value === undefined || value === null || value === ""
      ? null : String(value)
    var reconciliation = EffortModel.reconcile(requested, activeEffortChoices())
    if (reconciliation.reset) {
      setEffortStatus("That thinking effort is not supported by the active model.")
      return
    }
    if ((profile.thinkingEffort || null) === reconciliation.value) return
    setEffortStatus("")
    saveProfiles(ProfileModel.update(profileState, {
      profileId: profile.id,
      values: { thinkingEffort: reconciliation.value }
    }))
  }

  function reconcileActiveThinkingEffort() {
    var profile = activeProfile()
    if (!profile || !profileState) return
    var reconciliation = EffortModel.reconcile(
      profile.thinkingEffort,
      activeEffortChoices()
    )
    if (!reconciliation.reset) return
    setEffortStatus(
      "Thinking effort reset to Default because this model does not support it."
    )
    saveProfiles(ProfileModel.update(profileState, {
      profileId: profile.id,
      values: { thinkingEffort: null }
    }))
  }

  function requestProfilesAndHistory() {
    profilesRequestId = newRequestId()
    historyRequestId = newRequestId()
    bridge.send({ type: "profiles", requestId: profilesRequestId })
    bridge.send({ type: "history.list", requestId: historyRequestId })
  }

  function modelsFor(adapterId) {
    return root.modelCatalogs[adapterId] || []
  }

  function modelErrorFor(adapterId) {
    return root.modelCatalogErrors[adapterId] || ""
  }

  function modelsLoadingFor(adapterId) {
    for (var requestId in root.modelRequests) {
      if (root.modelRequests[requestId] === adapterId) return true
    }
    return false
  }

  function requestModels(adapterId, refresh, sourceProfileId) {
    if (!adapterId) return
    if (adapterId === "custom") {
      var emptyCatalogs = Object.assign({}, root.modelCatalogs)
      emptyCatalogs[adapterId] = []
      root.modelCatalogs = emptyCatalogs
      var customProfile = root.activeProfile()
      if (customProfile && customProfile.adapterId === adapterId)
        Qt.callLater(root.reconcileActiveThinkingEffort)
      return
    }
    if (root.modelsLoadingFor(adapterId)) return
    if (!refresh && root.modelCatalogs[adapterId] !== undefined) return

    var requestId = root.newRequestId()
    var requests = Object.assign({}, root.modelRequests)
    requests[requestId] = adapterId
    root.modelRequests = requests

    var errors = Object.assign({}, root.modelCatalogErrors)
    errors[adapterId] = ""
    root.modelCatalogErrors = errors

    bridge.send({
      type: "models.list",
      requestId: requestId,
      profileId: sourceProfileId || root.profileId,
      adapterId: adapterId,
      refresh: Boolean(refresh)
    })
  }

  function finishModelRequest(event) {
    var adapterId = root.modelRequests[event.requestId]
    if (!adapterId) return false

    var requests = Object.assign({}, root.modelRequests)
    delete requests[event.requestId]
    root.modelRequests = requests

    if (event.type === "complete") {
      var catalogs = Object.assign({}, root.modelCatalogs)
      catalogs[adapterId] = event.data.models || []
      root.modelCatalogs = catalogs
      var profile = root.activeProfile()
      if (profile && profile.adapterId === adapterId)
        Qt.callLater(root.reconcileActiveThinkingEffort)
    } else {
      var errors = Object.assign({}, root.modelCatalogErrors)
      errors[adapterId] = event.data.message || "Model discovery failed."
      root.modelCatalogErrors = errors
    }
    return true
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
    activePage = "chat"
    Qt.callLater(focusActivePage)
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

  function showAcceptanceFixture(name) {
    newConversation()
    attachments = []
    pendingApproval = null
    if (name === "attachment") {
      attachments = [{
        id: "fixture-text",
        kind: "text",
        path: null,
        text: "Selected text preview",
        mimeType: "text/plain",
        appName: "Acceptance fixture",
        windowTitle: "Preview before sending",
        size: 28
      }]
    } else if (name === "streamed") {
      chatState = ChatModel.loadConversation(chatState, {
        id: conversationId,
        profileId: profileId,
        messages: [
          { role: "user", content: "Explain this window" },
          { role: "assistant", content: "This is a streamed answer fixture." }
        ],
        cliSessions: {}
      })
    } else if (name === "approval") {
      pendingApproval = {
        approvalId: "fixture-approval",
        title: "Read a protected project file",
        operation: "read_file",
        details: "/tmp/example"
      }
    } else if (name === "error") {
      chatState = ChatModel.withFailedRun("Explain this", "timeout")
    }
    activePage = name === "settings" ? "profiles"
      : name === "history" ? "history"
      : "chat"
    Qt.callLater(focusActivePage)
    if (name === "picker")
      Qt.callLater(function() { composer.openAgentPicker() })
    else if (name === "effort-picker")
      Qt.callLater(function() { composer.openEffortPicker() })
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

  function answerApproval(approvalId, approved) {
    bridge.send({
      type: approved ? "approve" : "deny",
      requestId: chatState.activeRequestId,
      approvalId: approvalId
    })
    pendingApproval = null
  }

  function copyText(value) {
    pendingClipboard = value
    clipboardProcess.running = true
  }

  function handleRecovery(code, data) {
    if (code === "not_installed" || code === "invalid_working_directory") {
      openPage("profiles")
    } else if (code === "authentication_required") {
      copyText((data.loginCommand || []).join(" "))
    } else if (code === "unsupported_version") {
      bridge.send({ type: "probe", requestId: newRequestId(), profileId: profileId })
    } else if (code === "capture_failed") {
      attachments = []
    } else if (code === "bridge_exited") {
      bridge.start()
    } else if (code === "approval_not_relayable" && data.continueCommand) {
      if (shell && typeof shell.openTerminal === "function")
        shell.openTerminal(data.continueCommand)
      else
        Quickshell.execDetached(["foot", "-e"].concat(data.continueCommand))
    } else if (code === "history_recovered" && data.path) {
      Quickshell.execDetached(["xdg-open", data.path])
    }
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
    activePage = "chat"
    Qt.callLater(focusActivePage)
  }

  onActivePageChanged: Qt.callLater(focusActivePage)

  onProfileIdChanged: Qt.callLater(function() {
    var profile = root.activeProfile()
    if (profile) root.requestModels(profile.adapterId, false, profile.id)
  })

  Timer {
    id: effortStatusTimer
    interval: 5000
    repeat: false
    onTriggered: root.effortStatus = ""
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
        Qt.callLater(function() {
          var profile = root.activeProfile()
          if (profile) root.requestModels(profile.adapterId, false, profile.id)
        })
      } else if (event.type === "complete" && event.requestId === root.historyRequestId) {
        root.historyItems = event.data.conversations || []
      } else if (event.type === "complete" && event.requestId === root.historyGetRequestId) {
        root.chatState = ChatModel.loadConversation(root.chatState, event.data.conversation)
        root.conversationId = root.chatState.conversationId
        root.profileId = root.chatState.profileId
        root.activePage = "chat"
        Qt.callLater(root.focusActivePage)
      } else if (event.type === "complete" && event.requestId === root.clearRequestId) {
        root.historyItems = []
        root.newConversation()
      } else if (event.type === "complete" && event.requestId === root.profileSaveRequestId) {
        root.profileState = ProfileModel.normalize(event.data.config)
        if (!root.activeProfile()) root.profileId = root.profileState.selectedId
      } else if ((event.type === "complete" || event.type === "error")
                 && root.finishModelRequest(event)) {
        // Model catalog events belong to pickers, not the transcript.
      } else if (event.type === "complete" && root.contextRequests[event.requestId]) {
        if (event.data.attachment)
          root.attachments = root.attachments.concat([event.data.attachment])
        var requests = Object.assign({}, root.contextRequests)
        delete requests[event.requestId]
        root.contextRequests = requests
      } else {
        if (event.type === "tool_request") root.pendingApproval = event.data
        root.chatState = ChatModel.reduce(root.chatState, event)
        if ((event.type === "complete" || event.type === "error")
            && event.requestId === root.chatState.activeRequestId) {
          root.attachments = []
          root.pendingApproval = null
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

  ColumnLayout {
    anchors.fill: parent
    spacing: Style.space(12)

    ChatHeader {
      Layout.fillWidth: true
      profileId: root.profileId
      profiles: root.profileState ? root.profileState.profiles : []
      cliState: bridge.ready ? root.chatState.status : "Starting bridge"
      privateMode: root.privateMode
      maximized: root.maximized
      activePage: root.activePage
      onPrivateChanged: function(value) { root.privateMode = value }
      onHistoryRequested: root.togglePage("history")
      onSettingsRequested: root.togglePage("profiles")
      onMoveRequested: root.moveRequested()
      onMaximizeRequested: root.maximizeRequested()
    }

    PanelSeparator {
      Layout.fillWidth: true
      foreground: Color.popups.text
    }

    StackLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      currentIndex: root.activePage === "history" ? 1
        : root.activePage === "profiles" ? 2
        : 0

      ColumnLayout {
        spacing: Style.spacing.controlGap

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
          onActionRequested: function(code, data) { root.handleRecovery(code, data) }
        }

        ApprovalCard {
          Layout.fillWidth: true
          request: root.pendingApproval
          adapterName: root.activeProfile() ? root.activeProfile().name : "Agent"
          onApproveRequested: function(identifier) { root.answerApproval(identifier, true) }
          onDenyRequested: function(identifier) { root.answerApproval(identifier, false) }
        }

        PanelSeparator {
          Layout.fillWidth: true
          foreground: Color.popups.text
        }

        Composer {
          id: composer
          Layout.fillWidth: true
          running: root.chatState.running
          attachmentCount: root.attachments.length
          profileId: root.profileId
          profiles: root.profileState ? root.profileState.profiles : []
          modelCatalogs: root.modelCatalogs
          modelCatalogErrors: root.modelCatalogErrors
          modelRequests: root.modelRequests
          effortChoices: root.activeEffortChoices()
          thinkingEffort: root.activeProfile()
            ? root.activeProfile().thinkingEffort : null
          statusText: root.effortStatus
          onSendRequested: function(prompt) { root.sendPrompt(prompt) }
          onContextRequested: function(mode) { root.requestContext(mode) }
          onAgentModelSelected: function(nextProfileId, modelId) {
            root.selectProfileModel(nextProfileId, modelId)
          }
          onEffortSelected: function(value) { root.selectThinkingEffort(value) }
          onModelDiscoveryRequested: function(nextProfileId, adapterId, refresh) {
            root.requestModels(adapterId, refresh, nextProfileId)
          }
          onStopRequested: bridge.send({
            type: "cancel",
            requestId: root.chatState.activeRequestId
          })
        }
      }

      HistoryDrawer {
        id: historyPage
        conversations: root.historyItems
        profiles: root.profileState ? root.profileState.profiles : []
        onConversationSelected: function(identifier) { root.loadConversation(identifier) }
        onClearRequested: clearDialog.opened = true
        onNewChatRequested: root.newConversation()
      }

      ProfileSettings {
        id: profilePage
        profileState: root.profileState
        activeProfile: root.activeProfile()
        modelOptions: root.modelsFor(editingAdapterId)
        adapterStates: root.adapterStates
        modelsLoading: root.modelsLoadingFor(editingAdapterId)
        modelsError: root.modelErrorFor(editingAdapterId)
        shortcutError: root.service ? root.service.lastError : ""
        onModelDiscoveryRequested: function(adapterId, refresh) {
          root.requestModels(adapterId, refresh)
        }
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
  }

  ConfirmDialog {
    id: clearDialog
    anchors.fill: parent
    message: "Clear all Quick Chat history? CLI-owned sessions are not deleted."
    confirmText: "Clear"
    background: Color.popups.background
    foreground: Color.popups.text
    scrim: Util.alpha(Color.popups.background, 0.72)
    selectedBackground: Style.selectedFillFor(Color.popups.text, Color.accent)
    selectedText: Style.selectedStateColor(Color.popups.text, Color.accent)
    fontFamily: Style.font.menuFamily
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
    background: Color.popups.background
    foreground: Color.popups.text
    scrim: Util.alpha(Color.popups.background, 0.72)
    selectedBackground: Style.selectedFillFor(Color.popups.text, Color.accent)
    selectedText: Style.selectedStateColor(Color.popups.text, Color.accent)
    fontFamily: Style.font.menuFamily
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

  Process {
    id: clipboardProcess
    command: ["wl-copy"]
    stdinEnabled: true
    onStarted: {
      write(root.pendingClipboard)
      root.pendingClipboard = ""
    }
  }
}
