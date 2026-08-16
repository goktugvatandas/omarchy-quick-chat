import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

ColumnLayout {
  id: root

  property bool running: false
  property int attachmentCount: 0
  property string profileId: ""
  property var profiles: []
  property var modelCatalogs: ({})
  property var modelCatalogErrors: ({})
  property var modelRequests: ({})
  property var effortChoices: []
  property var thinkingEffort: null
  property string statusText: ""
  property string modelShortcut: ""
  property string effortShortcut: ""
  readonly property bool popupOpen: agentPicker.popupOpen || effortPicker.popupOpen
  property alias text: prompt.text
  signal sendRequested(string prompt)
  signal stopRequested()
  signal contextRequested(string mode)
  signal agentModelSelected(string profileId, string modelId)
  signal effortSelected(var value)
  signal modelDiscoveryRequested(string profileId, string adapterId, bool refresh)

  function focusInput() {
    prompt.forceActiveFocus()
  }

  function openAgentPicker() {
    effortPicker.close()
    agentPicker.open()
  }

  function openEffortPicker() {
    agentPicker.close()
    effortPicker.open()
  }

  function closeTransient() {
    if (effortPicker.popupOpen) {
      effortPicker.close()
      return true
    }
    if (agentPicker.popupOpen) {
      agentPicker.close()
      return true
    }
    return false
  }

  function insertNewline() {
    var start = Math.min(prompt.selectionStart, prompt.selectionEnd)
    var end = Math.max(prompt.selectionStart, prompt.selectionEnd)
    if (start !== end) prompt.remove(start, end)
    prompt.insert(start, "\n")
    prompt.cursorPosition = start + 1
  }

  spacing: Style.spacing.controlGap

  ThemedTextArea {
    id: prompt
    Layout.fillWidth: true
    Layout.preferredHeight: Style.space(92)
    placeholderText: "Ask a quick question…"
    wrapMode: TextEdit.Wrap
    textFormat: TextEdit.PlainText
    selectByMouse: true

    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Tab && event.modifiers === Qt.NoModifier) {
        agentPicker.focusTrigger()
        event.accepted = true
      } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        if (event.modifiers & Qt.ControlModifier) {
          root.insertNewline()
        } else {
          if (!root.running && prompt.text.trim()) root.sendRequested(prompt.text)
        }
        event.accepted = true
      }
    }
  }

  Text {
    Layout.fillWidth: true
    visible: root.statusText.length > 0
    text: root.statusText
    color: Qt.darker(Color.popups.text, 1.35)
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.caption
    textFormat: Text.PlainText
    elide: Text.ElideRight
  }

  RowLayout {
    Layout.fillWidth: true
    spacing: Style.spacing.sm

    HarnessModelPicker {
      id: agentPicker
      Layout.preferredWidth: Style.space(220)
      Layout.minimumWidth: Style.space(170)
      Layout.maximumWidth: Style.space(320)
      profileId: root.profileId
      profiles: root.profiles
      modelCatalogs: root.modelCatalogs
      modelCatalogErrors: root.modelCatalogErrors
      modelRequests: root.modelRequests
      shortcutHint: root.modelShortcut
      enabled: !root.running && root.profiles.length > 0
      onSelectionRequested: function(nextProfileId, modelId) {
        root.agentModelSelected(nextProfileId, modelId)
      }
      onModelDiscoveryRequested: function(nextProfileId, adapterId, refresh) {
        root.modelDiscoveryRequested(nextProfileId, adapterId, refresh)
      }
    }

    ThinkingEffortPicker {
      id: effortPicker
      Layout.preferredWidth: Style.space(96)
      Layout.minimumWidth: Style.space(82)
      Layout.maximumWidth: Style.space(130)
      choices: root.effortChoices
      value: root.thinkingEffort
      enabled: !root.running
      shortcutHint: root.effortShortcut
      onSelectionRequested: function(value) { root.effortSelected(value) }
    }

    Button {
      iconText: "󰖲"
      tooltipText: "Attach active window"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.contextRequested("window")
    }
    Button {
      iconText: "󰍹"
      tooltipText: "Attach full screen"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.contextRequested("screen")
    }
    Button {
      iconText: "󰣆"
      tooltipText: "Attach active app details"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.contextRequested("app")
    }
    Button {
      iconText: "󰆏"
      tooltipText: "Attach selected text"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      focusable: true
      onClicked: root.contextRequested("selection")
    }

    Text {
      visible: root.attachmentCount > 0
      text: "󰁦 " + root.attachmentCount
      color: Qt.darker(Color.popups.text, 1.4)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
      verticalAlignment: Text.AlignVCenter
    }

    Item {
      Layout.fillWidth: true
    }

    Button {
      visible: root.running
      text: "Stop"
      foreground: Color.urgent
      fontFamily: Style.font.menuFamily
      bordered: true
      focusable: true
      onClicked: root.stopRequested()
    }

    Button {
      visible: !root.running
      enabled: prompt.text.trim().length > 0
      text: "Send"
      tooltipText: "Send with Enter · new line with Ctrl+Enter"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      bordered: true
      focusable: true
      onClicked: root.sendRequested(prompt.text)
    }
  }
}
