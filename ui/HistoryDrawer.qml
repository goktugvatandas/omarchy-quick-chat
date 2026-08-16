import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property var conversations: []
  property var profiles: []
  signal conversationSelected(string conversationId)
  signal clearRequested()
  signal newChatRequested()

  function profileName(profileId) {
    for (var index = 0; index < profiles.length; index += 1) {
      if (profiles[index].id === profileId) return profiles[index].name
    }
    return "Deleted profile"
  }

  color: Style.normalFillFor(Color.menu.text, Color.accent)
  borderSpec: Border.controlSpec("normal", Color.menu.text, Color.accent)
  radius: Style.cornerRadius

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: Style.spacing.controlPaddingY
    spacing: Style.spacing.controlGap

    RowLayout {
      Layout.fillWidth: true
      Text {
        Layout.fillWidth: true
        text: "History"
        color: Color.menu.text
        font.family: Style.font.menuFamily
        font.bold: true
        font.pixelSize: Style.font.title
      }
      Button {
        text: "New"
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        onClicked: root.newChatRequested()
      }
    }

    ListView {
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      spacing: Style.space(4)
      model: root.conversations

      delegate: Button {
        required property var modelData
        width: ListView.view.width
        text: (modelData.title || "Untitled") + "\n"
          + root.profileName(modelData.profileId) + " · " + (modelData.updatedAt || "")
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        leftAlign: true
        onClicked: root.conversationSelected(modelData.id)
      }
    }

    Button {
      Layout.fillWidth: true
      text: "Clear history"
      enabled: root.conversations.length > 0
      foreground: Color.urgent
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.clearRequested()
    }
  }
}
