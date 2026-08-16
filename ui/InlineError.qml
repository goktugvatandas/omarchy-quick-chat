import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property var error: null
  signal dismissed()
  signal retryRequested()
  signal actionRequested(string code, var data)

  function actionLabel(code) {
    var labels = {
      not_installed: "Switch profile",
      authentication_required: "Copy login command",
      unsupported_version: "Refresh probe",
      invalid_working_directory: "Edit profile",
      capture_failed: "Send without context",
      timeout: "Retry",
      bridge_exited: "Restart bridge",
      approval_not_relayable: "Open terminal",
      history_recovered: "Open recovered file"
    }
    return labels[code] || ""
  }

  visible: error !== null
  implicitHeight: visible ? errorRow.implicitHeight + Style.spacing.controlPaddingY * 2 : 0
  radius: Style.cornerRadius
  color: Util.alpha(Color.urgent, Style.selectedFillAlpha)
  borderSpec: Border.flat(
    Util.alpha(Color.urgent, Style.normalBorderAlpha),
    Style.normalBorderWidth
  )

  RowLayout {
    id: errorRow
    anchors.fill: parent
    anchors.margins: Style.spacing.controlPaddingY

    Text {
      Layout.fillWidth: true
      text: root.error ? (root.error.message || root.error.code || "Request failed") : ""
      color: Color.popups.text
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.body
      wrapMode: Text.Wrap
      textFormat: Text.PlainText
    }

    Button {
      visible: root.error && root.actionLabel(root.error.code)
      text: root.error ? root.actionLabel(root.error.code) : ""
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      bordered: true
      focusable: true
      onClicked: {
        if (root.error.code === "timeout") root.retryRequested()
        else root.actionRequested(root.error.code, root.error)
      }
    }
    Button {
      text: "Dismiss"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      focusable: true
      onClicked: root.dismissed()
    }
  }
}
