import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

ColumnLayout {
  id: root

  property bool running: false
  property int attachmentCount: 0
  property alias text: prompt.text
  signal sendRequested(string prompt)
  signal stopRequested()
  signal contextRequested(string mode)

  function focusInput() {
    prompt.forceActiveFocus()
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
      if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
          && (event.modifiers & Qt.ControlModifier)) {
        if (!root.running && prompt.text.trim()) root.sendRequested(prompt.text)
        event.accepted = true
      }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    spacing: Style.space(4)

    Button {
      text: "Window"
      foreground: Color.menu.text
      fontFamily: Style.font.menuFamily
      onClicked: root.contextRequested("window")
    }
    Button {
      text: "Screen"
      foreground: Color.menu.text
      fontFamily: Style.font.menuFamily
      onClicked: root.contextRequested("screen")
    }
    Button {
      text: "App"
      foreground: Color.menu.text
      fontFamily: Style.font.menuFamily
      onClicked: root.contextRequested("app")
    }
    Button {
      text: "Selected text"
      foreground: Color.menu.text
      fontFamily: Style.font.menuFamily
      onClicked: root.contextRequested("selection")
    }

    Text {
      Layout.fillWidth: true
      horizontalAlignment: Text.AlignRight
      text: root.attachmentCount ? root.attachmentCount + " attached" : "Context is opt-in"
      color: Util.alpha(Color.menu.text, 0.6)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
    }
  }

  RowLayout {
    Layout.fillWidth: true

    Text {
      Layout.fillWidth: true
      text: "Ctrl+Enter sends · Enter adds a line"
      color: Util.alpha(Color.menu.text, 0.6)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
    }

    Button {
      visible: root.running
      text: "Stop"
      foreground: Color.urgent
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.stopRequested()
    }

    Button {
      visible: !root.running
      enabled: prompt.text.trim().length > 0
      text: "Send"
      foreground: Color.menu.text
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.sendRequested(prompt.text)
    }
  }
}
