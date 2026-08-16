import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

ColumnLayout {
  id: root

  property bool running: false
  property int attachmentCount: 0
  property string profileId: ""
  property var profiles: []
  property var modelCatalogs: ({})
  property var modelCatalogErrors: ({})
  property var modelRequests: ({})
  property alias text: prompt.text
  signal sendRequested(string prompt)
  signal stopRequested()
  signal contextRequested(string mode)
  signal agentModelSelected(string profileId, string modelId)
  signal modelDiscoveryRequested(string profileId, string adapterId, bool refresh)

  function focusInput() {
    prompt.forceActiveFocus()
  }

  spacing: Style.spacing.controlGap

  ThemedTextArea {
    id: prompt
    Layout.fillWidth: true
    Layout.preferredHeight: Style.space(92)
    placeholderText: "Ask a quick question…"
    wrapMode: TextEdit.Wrap
    textFormat: TextEdit.PlainText
    selectByMouse: true

    Keys.onPressed: function(event) {
      if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
          && (event.modifiers & Qt.ControlModifier)) {
        if (!root.running && prompt.text.trim()) root.sendRequested(prompt.text)
        event.accepted = true
      }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    spacing: Style.spacing.sm

    HarnessModelPicker {
      Layout.preferredWidth: Style.space(270)
      Layout.minimumWidth: Style.space(190)
      Layout.maximumWidth: Style.space(320)
      profileId: root.profileId
      profiles: root.profiles
      modelCatalogs: root.modelCatalogs
      modelCatalogErrors: root.modelCatalogErrors
      modelRequests: root.modelRequests
      enabled: !root.running && root.profiles.length > 0
      onSelectionRequested: function(nextProfileId, modelId) {
        root.agentModelSelected(nextProfileId, modelId)
      }
      onModelDiscoveryRequested: function(nextProfileId, adapterId, refresh) {
        root.modelDiscoveryRequested(nextProfileId, adapterId, refresh)
      }
    }

    Button {
      iconText: "󰖲"
      tooltipText: "Attach active window"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("window")
    }
    Button {
      iconText: "󰍹"
      tooltipText: "Attach full screen"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("screen")
    }
    Button {
      iconText: "󰣆"
      tooltipText: "Attach active app details"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("app")
    }
    Button {
      iconText: "󰆏"
      tooltipText: "Attach selected text"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      horizontalPadding: Style.spacing.sm
      onClicked: root.contextRequested("selection")
    }

    Text {
      visible: root.attachmentCount > 0
      text: "󰁦 " + root.attachmentCount
      color: Qt.darker(Color.popups.text, 1.4)
      font.family: Style.font.menuFamily
      font.pixelSize: Style.font.caption
      verticalAlignment: Text.AlignVCenter
    }

    Item {
      Layout.fillWidth: true
    }

    Button {
      visible: root.running
      text: "Stop"
      foreground: Color.urgent
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.stopRequested()
    }

    Button {
      visible: !root.running
      enabled: prompt.text.trim().length > 0
      text: "Send"
      foreground: Color.popups.text
      fontFamily: Style.font.menuFamily
      bordered: true
      onClicked: root.sendRequested(prompt.text)
    }
  }
}
