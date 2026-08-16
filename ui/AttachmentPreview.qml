import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Flow {
  id: root

  property var attachments: []
  signal removeRequested(string attachmentId)
  signal ocrRequested(string attachmentId)

  spacing: Style.space(6)

  Repeater {
    model: root.attachments

    delegate: Rectangle {
      required property var modelData
      width: Math.min(root.width, Style.space(230))
      height: Style.space(92)
      radius: Style.cornerRadius
      color: Qt.rgba(1, 1, 1, 0.05)

      RowLayout {
        anchors.fill: parent
        anchors.margins: Style.space(6)
        spacing: Style.space(6)

        Image {
          Layout.preferredWidth: Style.space(70)
          Layout.fillHeight: true
          visible: modelData.kind === "image" && Boolean(modelData.path)
          source: visible ? "file://" + modelData.path : ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
        }

        ColumnLayout {
          Layout.fillWidth: true
          Layout.fillHeight: true

          Text {
            Layout.fillWidth: true
            text: modelData.appName || (modelData.kind === "image" ? "Screenshot" : "Context")
            color: Color.menu.text
            font.bold: true
            elide: Text.ElideRight
          }

          Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: modelData.windowTitle || modelData.text || ""
            color: Color.menu.text
            opacity: 0.7
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            elide: Text.ElideRight
            maximumLineCount: 2
          }

          Text {
            text: String(modelData.size || 0) + " bytes"
            color: Color.menu.text
            opacity: 0.5
            font.pixelSize: Style.font.caption
          }
        }

        ColumnLayout {
          Button {
            visible: modelData.kind === "image"
            text: "OCR"
            onClicked: root.ocrRequested(modelData.id)
          }
          Button {
            text: "Remove"
            onClicked: root.removeRequested(modelData.id)
          }
        }
      }
    }
  }
}
