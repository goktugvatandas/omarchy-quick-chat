import QtQuick
import qs.Commons
import qs.Ui

ThemedScrollView {
  id: root

  property var messages: []

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
        ? Color.menu.selectedBackground
        : "transparent"
      borderSpec: modelData.role === "user"
        ? Border.controlSpec("selected", Color.menu.text, Color.accent)
        : Border.none()

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
        selectionColor: Style.selectionFillFor(Color.menu.text, Color.accent)
        selectedTextColor: Color.menu.text
        selectByMouse: true
      }
    }

    onCountChanged: Qt.callLater(function() { positionViewAtEnd() })
  }
}
