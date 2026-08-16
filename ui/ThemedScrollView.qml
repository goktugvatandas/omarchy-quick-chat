import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.ScrollView {
  id: root

  clip: true

  Controls.ScrollBar.vertical: Controls.ScrollBar {
    id: verticalBar
    policy: Controls.ScrollBar.AsNeeded

    contentItem: Rectangle {
      implicitWidth: Style.space(5)
      implicitHeight: Style.space(40)
      radius: Style.cornerRadius > 0 ? width / 2 : 0
      color: verticalBar.pressed
        ? Style.selectedStateColor(Color.popups.text, Color.accent)
        : Util.alpha(Color.popups.text, verticalBar.hovered ? 0.55 : 0.28)
    }

    background: Item {}
  }

  Controls.ScrollBar.horizontal: Controls.ScrollBar {
    id: horizontalBar
    policy: Controls.ScrollBar.AsNeeded

    contentItem: Rectangle {
      implicitWidth: Style.space(40)
      implicitHeight: Style.space(5)
      radius: Style.cornerRadius > 0 ? height / 2 : 0
      color: horizontalBar.pressed
        ? Style.selectedStateColor(Color.popups.text, Color.accent)
        : Util.alpha(Color.popups.text, horizontalBar.hovered ? 0.55 : 0.28)
    }

    background: Item {}
  }
}
