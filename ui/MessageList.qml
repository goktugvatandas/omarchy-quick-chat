import QtQuick
import qs.Commons
import qs.Ui

ThemedScrollView {
  id: root

  property var messages: []
  property string agentShortcut: ""
  verticalScrollBarEnabled: messages.length > 0

  ListView {
    id: messageView
    model: root.messages
    spacing: Style.spacing.controlGap
    clip: true

    delegate: Item {
      id: messageRow
      required property var modelData
      readonly property bool fromUser: modelData.role === "user"

      width: messageView.width
      height: bubble.height

      // Measures the unwrapped text so user bubbles hug their content
      // instead of rendering a short message as a full-width slab.
      Text {
        id: measure
        visible: false
        text: messageRow.modelData.text || ""
        textFormat: Text.PlainText
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
      }

      BorderSurface {
        id: bubble
        x: messageRow.fromUser ? messageRow.width - width : 0
        width: messageRow.fromUser
          ? Math.min(
              measure.implicitWidth + Style.spacing.controlPaddingY * 2
                + Style.space(2),
              Math.round(messageRow.width * 0.85)
            )
          : messageRow.width
        height: messageText.implicitHeight + Style.spacing.controlPaddingY * 2
        radius: Style.cornerRadius
        color: messageRow.fromUser
          ? Style.selectedFillFor(Color.popups.text, Color.accent)
          : "transparent"
        borderSpec: messageRow.fromUser
          ? Border.controlSpec("selected", Color.popups.text, Color.accent)
          : Border.none()

        TextEdit {
          id: messageText
          x: Style.spacing.controlPaddingY
          y: Style.spacing.controlPaddingY
          width: bubble.width - Style.spacing.controlPaddingY * 2
          text: messageRow.modelData.text || ""
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
    }

    onCountChanged: Qt.callLater(function() { positionViewAtEnd() })

    Column {
      anchors.centerIn: parent
      visible: root.messages.length === 0
      spacing: Style.spacing.md

      Text {
        width: Style.space(360)
        text: "󰚩"
        color: Color.accent
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.displayLarge
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: Style.space(360)
        text: "Ask anything"
        color: Color.popups.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.heading
        font.weight: Font.Medium
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: Style.space(360)
        text: "Enter sends · Ctrl+Enter adds a line"
          + (root.agentShortcut
            ? "\n" + root.agentShortcut + " switches agent and model" : "")
        color: Qt.darker(Color.popups.text, 1.4)
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }
  }
}
