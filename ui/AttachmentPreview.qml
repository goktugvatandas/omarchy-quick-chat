import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Flow {
  id: root

  property var attachments: []
  signal removeRequested(string attachmentId)
  signal ocrRequested(string attachmentId)

  spacing: Style.space(6)

  Repeater {
    model: root.attachments

    delegate: BorderSurface {
      required property var modelData
      width: Math.min(root.width, Style.space(230))
      height: Style.space(92)
      radius: Style.cornerRadius
      color: Style.normalFillFor(Color.popups.text, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.popups.text, Color.accent)

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
            color: Color.popups.text
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.body
            font.bold: true
            elide: Text.ElideRight
          }

          Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: modelData.windowTitle || modelData.text || ""
            color: Util.alpha(Color.popups.text, 0.7)
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.bodySmall
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            elide: Text.ElideRight
            maximumLineCount: 2
          }

          Text {
            text: String(modelData.size || 0) + " bytes"
            color: Util.alpha(Color.popups.text, 0.5)
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.caption
          }
        }

        ColumnLayout {
          Button {
            visible: modelData.kind === "image"
            text: "OCR"
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            onClicked: root.ocrRequested(modelData.id)
          }
          Button {
            text: "Remove"
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            onClicked: root.removeRequested(modelData.id)
          }
        }
      }
    }
  }
}
