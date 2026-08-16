import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Rectangle {
  id: root

  property var request: null
  property string adapterName: "Agent"
  property bool detailsExpanded: false
  signal approveRequested(string approvalId)
  signal denyRequested(string approvalId)

  function deny() {
    if (request && request.approvalId) denyRequested(request.approvalId)
  }

  visible: request !== null
  implicitHeight: visible ? content.implicitHeight + Style.space(18) : 0
  radius: Style.cornerRadius
  color: Qt.rgba(1, 0.65, 0, 0.12)
  focus: visible

  Keys.onEscapePressed: function(event) {
    root.deny()
    event.accepted = true
  }

  ColumnLayout {
    id: content
    anchors.fill: parent
    anchors.margins: Style.space(9)
    spacing: Style.space(6)

    Text {
      Layout.fillWidth: true
      text: root.adapterName + " requests approval"
      color: Color.menu.text
      font.bold: true
    }
    Text {
      Layout.fillWidth: true
      text: root.request ? (root.request.title || root.request.operation || "Operation") : ""
      color: Color.menu.text
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
    }
    Text {
      Layout.fillWidth: true
      visible: root.detailsExpanded
      text: root.request ? String(root.request.details || "") : ""
      color: Color.menu.text
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
    }
    RowLayout {
      Layout.fillWidth: true
      Button {
        text: root.detailsExpanded ? "Hide details" : "Details"
        onClicked: root.detailsExpanded = !root.detailsExpanded
      }
      Item { Layout.fillWidth: true }
      Button { text: "Deny"; onClicked: root.deny() }
      Button {
        text: "Approve once"
        onClicked: {
          if (root.request && root.request.approvalId)
            root.approveRequested(root.request.approvalId)
        }
      }
    }
  }
}
