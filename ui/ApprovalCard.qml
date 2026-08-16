import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
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
  color: Util.alpha(Color.accent, Style.selectedFillAlpha)
  borderSpec: Border.flat(
    Util.alpha(Color.accent, Style.normalBorderAlpha),
    Style.normalBorderWidth
  )
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
      color: Color.popups.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.subtitle
      font.bold: true
    }
    Text {
      Layout.fillWidth: true
      text: root.request ? (root.request.title || root.request.operation || "Operation") : ""
      color: Color.popups.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.body
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
    }
    Text {
      Layout.fillWidth: true
      visible: root.detailsExpanded
      text: root.request ? String(root.request.details || "") : ""
      color: Color.popups.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.bodySmall
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
    }
    RowLayout {
      Layout.fillWidth: true
      Button {
        text: root.detailsExpanded ? "Hide details" : "Details"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
        focusable: true
        onClicked: root.detailsExpanded = !root.detailsExpanded
      }
      Item { Layout.fillWidth: true }
      Button {
        text: "Deny"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
        focusable: true
        onClicked: root.deny()
      }
      Button {
        text: "Approve once"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
        bordered: true
        focusable: true
        onClicked: {
          if (root.request && root.request.approvalId)
            root.approveRequested(root.request.approvalId)
        }
      }
    }
  }
}
