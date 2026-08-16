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
    spacing: Style.spacing.sm

    Button {
      iconText: "󰖲"
      tooltipText: "Attach active window"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("window")
    }
    Button {
      iconText: "󰍹"
      tooltipText: "Attach full screen"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("screen")
    }
    Button {
      iconText: "󰣆"
      tooltipText: "Attach active app details"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("app")
    }
    Button {
      iconText: "󰆏"
      tooltipText: "Attach selected text"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("selection")
    }

    Text {
      Layout.fillWidth: true
      text: root.attachmentCount ? root.attachmentCount + " attached" : "Context is opt-in"
      color: Qt.darker(Color.popups.text, 1.4)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
      verticalAlignment: Text.AlignVCenter
    }

    Text {
      visible: !root.running
      text: "CTRL ↵"
      color: Qt.darker(Color.popups.text, 1.6)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.bodySmall
      font.bold: true
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
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.sendRequested(prompt.text)
    }
  }
}
