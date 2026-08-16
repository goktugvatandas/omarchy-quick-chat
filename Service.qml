import Quickshell
import Quickshell.Io
import QtQuick

Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property string lastError: ""
  property var profiles: [
    { id: "codex", name: "Codex", shortcut: "SUPER ALT, SPACE" },
    { id: "claude", name: "Claude Code", shortcut: null },
    { id: "opencode", name: "OpenCode", shortcut: null },
    { id: "grok", name: "Grok", shortcut: null },
    { id: "cursor", name: "Cursor", shortcut: null },
    { id: "pi", name: "Pi", shortcut: null }
  ]
  readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME")
    || Quickshell.env("HOME") + "/.config"
  readonly property string configPath: configHome + "/omarchy/quick-chat/config.json"
  readonly property string bridgePath: manifest && manifest.__sourceDir
    ? manifest.__sourceDir + "/bridge/quick-chat-bridge"
    : ""

  onBridgePathChanged: {
    Qt.callLater(function() { root.syncShortcuts() })
  }

  function syncShortcuts() {
    if (!bridgePath || shortcutSync.running) return
    shortcutSync.command = [bridgePath, "shortcuts", "sync"]
    shortcutSync.running = true
  }

  function loadConfig(content) {
    try {
      var config = JSON.parse(String(content || ""))
      if (!config || config.schemaVersion !== 1 || !Array.isArray(config.profiles))
        throw new Error("invalid schema")
      profiles = config.profiles.map(function(profile) {
        return {
          id: profile.id,
          name: profile.name,
          shortcut: profile.shortcut
            || (profile.id === config.selectedProfileId ? config.defaultShortcut : null)
        }
      })
      lastError = ""
      Qt.callLater(function() {
        root.syncShortcuts()
      })
    } catch (error) {
      lastError = "Invalid Quick Chat configuration: " + error
    }
  }

  Repeater {
    model: root.profiles
    delegate: ShortcutDelegate {
      required property var modelData
      profileId: modelData.id
      profileName: modelData.name
    }
  }

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    printErrors: false
    onLoaded: root.loadConfig(text())
    onFileChanged: reload()
    onLoadFailed: function(error) {
      Qt.callLater(function() { root.syncShortcuts() })
    }
  }

  Process {
    id: shortcutSync
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var result = JSON.parse(line)
          if (result.conflicts && result.conflicts.length)
            root.lastError = "Shortcut conflicts: " + JSON.stringify(result.conflicts)
        } catch (error) {
          root.lastError = "Shortcut sync returned invalid data."
        }
      }
    }
    stderr: SplitParser {
      onRead: function(line) { root.lastError = line }
    }
  }
}
