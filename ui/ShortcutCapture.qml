import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property string sequence: ""
  property bool capturing: false
  property string captureError: ""
  property color foreground: Color.popups.text
  property color accent: Color.accent
  property string fontFamily: Style.font.menuFamily

  signal sequenceCaptured(string sequence)
  signal captureCanceled()

  function beginCapture() {
    captureError = ""
    capturing = true
    forceActiveFocus()
  }

  function cancelCapture() {
    capturing = false
    captureError = ""
    captureCanceled()
  }

  function modifierKey(key) {
    return key === Qt.Key_Control || key === Qt.Key_Shift
      || key === Qt.Key_Alt || key === Qt.Key_Meta || key === Qt.Key_AltGr
  }

  function keyName(key) {
    if (key >= Qt.Key_A && key <= Qt.Key_Z)
      return String.fromCharCode("A".charCodeAt(0) + key - Qt.Key_A)
    if (key >= Qt.Key_0 && key <= Qt.Key_9)
      return String.fromCharCode("0".charCodeAt(0) + key - Qt.Key_0)
    if (key >= Qt.Key_F1 && key <= Qt.Key_F24)
      return "F" + String(key - Qt.Key_F1 + 1)
    var names = ({})
    names[Qt.Key_Backspace] = "Backspace"
    names[Qt.Key_Delete] = "Delete"
    names[Qt.Key_Down] = "Down"
    names[Qt.Key_End] = "End"
    names[Qt.Key_Return] = "Enter"
    names[Qt.Key_Enter] = "Enter"
    names[Qt.Key_Home] = "Home"
    names[Qt.Key_Insert] = "Insert"
    names[Qt.Key_Left] = "Left"
    names[Qt.Key_PageDown] = "PageDown"
    names[Qt.Key_PageUp] = "PageUp"
    names[Qt.Key_Right] = "Right"
    names[Qt.Key_Space] = "Space"
    names[Qt.Key_Tab] = "Tab"
    names[Qt.Key_Up] = "Up"
    names[Qt.Key_Comma] = ","
    names[Qt.Key_Period] = "."
    names[Qt.Key_Semicolon] = ";"
    names[Qt.Key_Slash] = "/"
    names[Qt.Key_Backslash] = "\\"
    names[Qt.Key_Minus] = "-"
    names[Qt.Key_Equal] = "="
    names[Qt.Key_BracketLeft] = "["
    names[Qt.Key_BracketRight] = "]"
    return names[key] || ""
  }

  function capturedSequence(event) {
    var parts = []
    if (event.modifiers & Qt.ControlModifier) parts.push("Ctrl")
    if (event.modifiers & Qt.AltModifier) parts.push("Alt")
    if (event.modifiers & Qt.ShiftModifier) parts.push("Shift")
    if (event.modifiers & Qt.MetaModifier) parts.push("Meta")
    var key = keyName(event.key)
    if (!key) return ""
    parts.push(key)
    return parts.join("+")
  }

  activeFocusOnTab: true
  implicitWidth: Style.space(170)
  implicitHeight: Style.spacing.controlHeight
  radius: Style.cornerRadius
  color: Style.controlFill(
    activeFocus,
    captureHover.hovered,
    root.foreground,
    root.accent
  )
  borderSpec: Border.controlSpec(
    activeFocus ? "focus" : (captureHover.hovered ? "hover-cursor" : "normal"),
    root.foreground,
    root.accent
  )

  HoverHandler { id: captureHover }

  Keys.priority: Keys.BeforeItem
  Keys.onPressed: function(event) {
    if (!root.capturing) {
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
          || event.key === Qt.Key_Space) {
        root.beginCapture()
        event.accepted = true
      }
      return
    }

    event.accepted = true
    if (event.isAutoRepeat) return
    if (event.key === Qt.Key_Escape) {
      root.cancelCapture()
      return
    }
    if (root.modifierKey(event.key)) return
    var result = root.capturedSequence(event)
    if (!result) {
      root.captureError = "Unsupported key"
      return
    }
    root.capturing = false
    root.captureError = ""
    root.sequenceCaptured(result)
  }

  onActiveFocusChanged: {
    if (!activeFocus && capturing) cancelCapture()
  }

  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: root.borderLeft + Style.spacing.controlPaddingX
    anchors.rightMargin: root.borderRight + Style.spacing.controlPaddingX
    spacing: Style.spacing.controlGap

    Text {
      Layout.fillWidth: true
      text: root.captureError || (root.capturing
        ? "Press shortcut…" : (root.sequence || "Not set"))
      color: root.captureError ? Color.urgent : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      textFormat: Text.PlainText
      elide: Text.ElideRight
      Layout.alignment: Qt.AlignVCenter
    }

    Text {
      text: root.capturing ? "Esc cancels" : "󰌌"
      color: Qt.darker(root.foreground, 1.4)
      font.family: root.fontFamily
      font.pixelSize: root.capturing ? Style.font.caption : Style.font.body
      Layout.alignment: Qt.AlignVCenter
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.beginCapture()
  }

  PanelToolTip {
    visible: captureHover.hovered && !root.capturing
    text: "Click, then press one shortcut chord"
    fontFamily: root.fontFamily
  }
}
