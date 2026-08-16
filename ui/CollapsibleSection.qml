import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

ColumnLayout {
  id: root

  property string title: ""
  property string hint: ""
  property bool expanded: false
  default property alias contentData: contentColumn.data

  spacing: Style.spacing.controlGap

  function toggle() { root.expanded = !root.expanded }

  BorderSurface {
    id: header
    Layout.fillWidth: true
    implicitHeight: Style.spacing.controlHeight
    radius: Style.cornerRadius
    activeFocusOnTab: true
    color: Style.controlFill(
      activeFocus, headerHover.hovered, Color.popups.text, Color.accent
    )
    borderSpec: Border.controlSpec(
      activeFocus ? "focus" : (headerHover.hovered ? "hover-cursor" : "normal"),
      Color.popups.text,
      Color.accent
    )

    HoverHandler { id: headerHover }

    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
          || event.key === Qt.Key_Space) {
        root.toggle()
        event.accepted = true
      }
    }

    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: header.borderLeft + Style.spacing.controlPaddingX
      anchors.rightMargin: header.borderRight + Style.spacing.controlPaddingX
      spacing: Style.spacing.sm

      Text {
        text: root.expanded ? "󰅀" : "󰅂"
        color: Qt.darker(Color.popups.text, 1.2)
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.bodySmall
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        Layout.fillWidth: true
        text: root.title
        color: Color.popups.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.body
        font.weight: Font.Medium
        elide: Text.ElideRight
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        visible: !root.expanded && root.hint.length > 0
        text: root.hint
        color: Qt.darker(Color.popups.text, 1.5)
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
        Layout.alignment: Qt.AlignVCenter
      }
    }

    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: root.toggle()
    }
  }

  ColumnLayout {
    id: contentColumn
    Layout.fillWidth: true
    Layout.leftMargin: Style.space(8)
    visible: root.expanded
    spacing: Style.spacing.controlGap
  }
}
