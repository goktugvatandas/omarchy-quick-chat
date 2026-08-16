import QtQuick
import qs.Commons
import qs.Ui

ThemedScrollView {
  id: root

  property var messages: []
  verticalScrollBarEnabled: messages.length > 0

  ListView {
    id: messageView
    model: root.messages
    spacing: Style.spacing.controlGap
    clip: true

    delegate: BorderSurface {
      required property var modelData
      width: messageView.width
      height: messageText.implicitHeight + Style.spacing.controlPaddingY * 2
      radius: Style.cornerRadius
      color: modelData.role === "user"
        ? Style.selectedFillFor(Color.popups.text, Color.accent)
        : "transparent"
      borderSpec: modelData.role === "user"
        ? Border.controlSpec("selected", Color.popups.text, Color.accent)
        : Border.none()

      TextEdit {
        id: messageText
        anchors.fill: parent
        anchors.margins: Style.spacing.controlPaddingY
        text: modelData.text || ""
        textFormat: Text.PlainText
        wrapMode: TextEdit.Wrap
        readOnly: true
        color: Color.popups.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
        selectionColor: Style.selectionFillFor(Color.popups.text, Color.accent)
        selectedTextColor: Color.popups.text
        selectByMouse: true
      }
    }

    onCountChanged: Qt.callLater(function() { positionViewAtEnd() })
  }
}
