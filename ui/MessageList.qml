import QtQuick
import QtQuick.Controls
import qs.Commons

ScrollView {
  id: root

  property var messages: []

  ListView {
    id: messageView
    model: root.messages
    spacing: Style.spacing.controlGap
    clip: true

    delegate: Rectangle {
      required property var modelData
      width: messageView.width
      height: messageText.implicitHeight + Style.spacing.controlPaddingY * 2
      radius: Style.cornerRadius
      color: modelData.role === "user"
        ? Color.menu.selectedBackground
        : "transparent"

      TextEdit {
        id: messageText
        anchors.fill: parent
        anchors.margins: Style.spacing.controlPaddingY
        text: modelData.text || ""
        textFormat: Text.PlainText
        wrapMode: TextEdit.Wrap
        readOnly: true
        color: Color.menu.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
        selectByMouse: true
      }
    }

    onCountChanged: Qt.callLater(function() { positionViewAtEnd() })
  }
}
