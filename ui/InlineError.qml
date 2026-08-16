import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Rectangle {
  id: root

  property var error: null
  signal dismissed()
  signal retryRequested()

  visible: error !== null
  implicitHeight: visible ? errorRow.implicitHeight + Style.spacing.controlPaddingY * 2 : 0
  radius: Style.cornerRadius
  color: Qt.rgba(1, 0.2, 0.2, 0.12)

  RowLayout {
    id: errorRow
    anchors.fill: parent
    anchors.margins: Style.spacing.controlPaddingY

    Text {
      Layout.fillWidth: true
      text: root.error ? (root.error.message || root.error.code || "Request failed") : ""
      color: Color.menu.text
      wrapMode: Text.Wrap
      textFormat: Text.PlainText
    }

    Button { text: "Retry"; onClicked: root.retryRequested() }
    Button { text: "Dismiss"; onClicked: root.dismissed() }
  }
}
