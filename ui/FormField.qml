import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: root

  property string label: ""
  default property alias fieldContent: fieldHost.data

  spacing: Style.spacing.labelGap

  PanelSectionHeader {
    width: parent.width
    text: root.label.toUpperCase()
    foreground: Color.popups.text
    fontFamily: Style.font.menuFamily
  }

  Item {
    id: fieldHost
    width: parent.width
    implicitHeight: childrenRect.height
  }
}
