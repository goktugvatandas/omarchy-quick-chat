import QtQuick

Item {
  id: root

  property var shortcuts: ({
    focusInput: "",
    model: "",
    effort: "",
    history: "",
    settings: "",
    private: "",
    newChat: ""
  })

  signal focusInputRequested()
  signal modelRequested()
  signal effortRequested()
  signal historyRequested()
  signal settingsRequested()
  signal privateRequested()
  signal newChatRequested()

  function configuredSequence(action) {
    if (!root.shortcuts || typeof root.shortcuts[action] !== "string") return ""
    return root.shortcuts[action]
  }

  Shortcut {
    sequence: root.configuredSequence("focusInput")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("focusInput").length > 0
    onActivated: root.focusInputRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("model")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("model").length > 0
    onActivated: root.modelRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("effort")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("effort").length > 0
    onActivated: root.effortRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("history")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("history").length > 0
    onActivated: root.historyRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("settings")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("settings").length > 0
    onActivated: root.settingsRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("private")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("private").length > 0
    onActivated: root.privateRequested()
  }

  Shortcut {
    sequence: root.configuredSequence("newChat")
    context: Qt.WindowShortcut
    enabled: root.enabled && root.configuredSequence("newChat").length > 0
    onActivated: root.newChatRequested()
  }
}
