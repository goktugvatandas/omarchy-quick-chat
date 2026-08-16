import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "../models/ProfileModel.js" as ProfileModel

ColumnLayout {
  id: root

  property var profileState: null
  property var shortcuts: ({})
  property string validationError: ""
  property bool captureActive: false
  property var captureStates: ({})
  readonly property var actions: [
    { action: "focusInput", label: "Focus input", hint: "Default Ctrl+L" },
    { action: "model", label: "Agent and model", hint: "Default Ctrl+K" },
    { action: "effort", label: "Thinking effort", hint: "Default Ctrl+." },
    { action: "history", label: "History", hint: "Default Ctrl+H" },
    { action: "settings", label: "Settings", hint: "Default Ctrl+," },
    { action: "private", label: "Private mode", hint: "Default Ctrl+Shift+P" },
    { action: "newChat", label: "New chat", hint: "Default Ctrl+N" }
  ]

  signal shortcutsChanged(var shortcuts)

  function candidate(action, sequence) {
    var next = Object.assign({}, root.shortcuts || ({}))
    next[action] = sequence
    return next
  }

  function applyCandidate(shortcuts) {
    if (!root.profileState) return
    try {
      var nextState = ProfileModel.setUiShortcuts(root.profileState, shortcuts)
      validationError = ""
      shortcutsChanged(nextState.uiShortcuts)
    } catch (error) {
      validationError = String(error && error.message ? error.message : error)
    }
  }

  function resetDefaults() {
    if (!root.profileState) return
    try {
      var nextState = ProfileModel.resetUiShortcuts(root.profileState)
      validationError = ""
      shortcutsChanged(nextState.uiShortcuts)
    } catch (error) {
      validationError = String(error && error.message ? error.message : error)
    }
  }

  function setCaptureActive(action, active) {
    var states = Object.assign({}, root.captureStates)
    states[action] = Boolean(active)
    root.captureStates = states
    root.captureActive = Object.keys(states).some(function(key) { return states[key] })
  }

  spacing: Style.spacing.controlGap

  Repeater {
    model: root.actions

    delegate: RowLayout {
      id: shortcutRow
      required property var modelData

      Layout.fillWidth: true
      spacing: Style.spacing.controlGap

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.spacing.xxs

        Text {
          Layout.fillWidth: true
          text: shortcutRow.modelData.label
          color: Color.popups.text
          font.family: Style.font.menuFamily
          font.pixelSize: Style.font.body
          textFormat: Text.PlainText
        }

        Text {
          Layout.fillWidth: true
          text: shortcutRow.modelData.hint
          color: Qt.darker(Color.popups.text, 1.45)
          font.family: Style.font.menuFamily
          font.pixelSize: Style.font.caption
          textFormat: Text.PlainText
        }
      }

      ShortcutCapture {
        Layout.preferredWidth: Style.space(190)
        sequence: String(
          (root.shortcuts && root.shortcuts[shortcutRow.modelData.action]) || ""
        )
        onCapturingChanged: root.setCaptureActive(
          shortcutRow.modelData.action,
          capturing
        )
        onSequenceCaptured: function(sequence) {
          root.applyCandidate(root.candidate(shortcutRow.modelData.action, sequence))
        }
      }
    }
  }

  Text {
    Layout.fillWidth: true
    visible: root.validationError.length > 0
    text: root.validationError
    color: Color.urgent
    font.family: Style.font.menuFamily
    font.pixelSize: Style.font.caption
    textFormat: Text.PlainText
    wrapMode: Text.WordWrap
  }

  Button {
    Layout.alignment: Qt.AlignRight
    text: "Reset shortcuts"
    iconText: "󰑐"
    tooltipText: "Restore all seven default shortcuts"
    foreground: Color.popups.text
    fontFamily: Style.font.menuFamily
    bordered: true
    focusable: true
    onClicked: root.resetDefaults()
  }
}
