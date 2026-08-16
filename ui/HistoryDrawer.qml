import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

FocusScope {
  id: root

  property var conversations: []
  property var profiles: []
  property string newChatShortcut: ""
  property int selectedIndex: 0
  property bool cursorActive: false
  signal conversationSelected(string conversationId)
  signal clearRequested()
  signal newChatRequested()

  function profile(profileId) {
    for (var index = 0; index < profiles.length; index += 1) {
      if (profiles[index].id === profileId) return profiles[index]
    }
    return null
  }

  function profileName(profileId) {
    var value = profile(profileId)
    return value ? value.name : "Deleted profile"
  }

  function profileIcon(profileId) {
    var value = profile(profileId)
    return value ? (value.icon || "󰚩") : "󰚩"
  }

  function focusPage() {
    cursorActive = conversations.length > 0
    keyTarget.forceActiveFocus()
  }

  function moveCursor(delta) {
    if (conversations.length === 0) return
    cursorActive = true
    selectedIndex = Math.max(0, Math.min(conversations.length - 1, selectedIndex + delta))
    conversationList.positionViewAtIndex(selectedIndex, ListView.Contain)
  }

  function activateCursor() {
    if (selectedIndex < 0 || selectedIndex >= conversations.length) return
    conversationSelected(conversations[selectedIndex].id)
  }

  Item {
    id: keyTarget
    anchors.fill: parent
    focus: true

    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Down || event.text === "j") {
        root.moveCursor(1)
        event.accepted = true
      } else if (event.key === Qt.Key_Up || event.text === "k") {
        root.moveCursor(-1)
        event.accepted = true
      } else if (event.key === Qt.Key_Home && root.conversations.length > 0) {
        root.cursorActive = true
        root.selectedIndex = 0
        conversationList.positionViewAtBeginning()
        event.accepted = true
      } else if (event.key === Qt.Key_End && root.conversations.length > 0) {
        root.cursorActive = true
        root.selectedIndex = root.conversations.length - 1
        conversationList.positionViewAtEnd()
        event.accepted = true
      } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                 || event.key === Qt.Key_Space) {
        root.activateCursor()
        event.accepted = true
      }
    }

    ColumnLayout {
      anchors.fill: parent
      spacing: Style.space(12)

      PanelHero {
        Layout.fillWidth: true
        title: "History"
        meta: root.conversations.length + " CONVERSATION" + (root.conversations.length === 1 ? "" : "S")
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily

        iconComponent: Component {
          Text {
            text: "󰋚"
            color: Color.popups.text
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.display
          }
        }

        trailingControl: Component {
          Button {
            iconText: "+"
            tooltipText: "New conversation"
              + (root.newChatShortcut ? " (" + root.newChatShortcut + ")" : "")
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            bordered: true
            focusable: true
            onClicked: root.newChatRequested()
          }
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.popups.text
      }

      PanelSectionHeader {
        text: "RECENT"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
      }

      ListView {
        id: conversationList
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: Style.spacing.xs
        model: root.conversations
        boundsBehavior: Flickable.StopAtBounds

        delegate: CursorSurface {
          id: conversationRow
          required property var modelData
          required property int index

          width: ListView.view.width
          implicitHeight: rowContent.implicitHeight + Style.spacing.xl * 2
          hasCursor: root.cursorActive && index === root.selectedIndex
          foreground: Color.popups.text

          Row {
            id: rowContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Style.space(8)
            anchors.rightMargin: Style.space(8)
            spacing: Style.space(12)

            Text {
              text: root.profileIcon(conversationRow.modelData.profileId)
              color: Color.popups.text
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.iconLarge
              width: Style.space(34)
              horizontalAlignment: Text.AlignHCenter
              anchors.verticalCenter: parent.verticalCenter
            }

            Column {
              width: parent.width - Style.space(34) - parent.spacing - trail.width
              spacing: Style.spacing.labelGap

              Text {
                width: parent.width
                text: conversationRow.modelData.title || "Untitled"
                color: Color.popups.text
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.heading
                font.weight: Font.Medium
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: root.profileName(conversationRow.modelData.profileId)
                  + " · " + (conversationRow.modelData.updatedAt || "")
                color: Qt.darker(Color.popups.text, 1.4)
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
              }
            }

            Text {
              id: trail
              text: "›"
              color: Qt.darker(Color.popups.text, 2.2)
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.heading
              anchors.verticalCenter: parent.verticalCenter
            }
          }

          MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: {
              root.cursorActive = true
              root.selectedIndex = conversationRow.index
            }
            onClicked: root.conversationSelected(conversationRow.modelData.id)
          }
        }

        Column {
          anchors.centerIn: parent
          visible: root.conversations.length === 0
          spacing: Style.spacing.md

          Text {
            width: Style.space(320)
            text: "󰈉"
            color: Color.accent
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.displayLarge
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            width: Style.space(320)
            text: "No saved conversations yet"
            color: Qt.darker(Color.popups.text, 1.4)
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
          }
        }
      }

      Button {
        Layout.alignment: Qt.AlignRight
        visible: root.conversations.length > 0
        text: "Clear history"
        iconText: "󰆴"
        foreground: Color.urgent
        fontFamily: Style.font.menuFamily
        focusable: true
        onClicked: root.clearRequested()
      }
    }
  }
}
