import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Rectangle {
  id: root

  property var profileState: null
  property var activeProfile: null
  signal historyLimitChanged(var value)
  signal editProfilesRequested()

  color: Qt.rgba(1, 1, 1, 0.025)
  radius: Style.cornerRadius

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: Style.spacing.controlPaddingY
    spacing: Style.spacing.controlGap

    Text {
      Layout.fillWidth: true
      text: "Profile"
      color: Color.menu.text
      font.bold: true
      font.pixelSize: Style.font.title
    }

    Text {
      Layout.fillWidth: true
      text: root.activeProfile
        ? root.activeProfile.name + "\n" + root.activeProfile.adapterId
        : "No profile"
      color: Color.menu.text
      wrapMode: Text.Wrap
    }

    CheckBox {
      id: unlimited
      text: "Unlimited history"
      checked: root.profileState && root.profileState.historyLimit === null
      onToggled: {
        if (checked) root.historyLimitChanged(null)
        else root.historyLimitChanged(Math.max(1, parseInt(retention.text || "20")))
      }
    }

    TextField {
      id: retention
      Layout.fillWidth: true
      enabled: !unlimited.checked
      placeholderText: "History limit"
      text: root.profileState && root.profileState.historyLimit !== null
        ? String(root.profileState.historyLimit)
        : "20"
      validator: IntValidator { bottom: 1 }
      onEditingFinished: {
        var value = parseInt(text)
        if (value > 0) root.historyLimitChanged(value)
      }
    }

    Text {
      Layout.fillWidth: true
      Layout.fillHeight: true
      text: root.activeProfile && root.activeProfile.systemInstructions
        ? root.activeProfile.systemInstructions
        : "Read-only execution is enabled by default."
      color: Color.menu.text
      opacity: 0.7
      wrapMode: Text.Wrap
      textFormat: Text.PlainText
    }

    Button {
      Layout.fillWidth: true
      text: "Edit profiles"
      onClicked: root.editProfilesRequested()
    }
  }
}
