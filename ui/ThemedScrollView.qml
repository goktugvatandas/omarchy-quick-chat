import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.ScrollView {
  id: root

  property bool verticalScrollBarEnabled: true

  clip: true
  contentWidth: availableWidth

  // Replacing an attached scroll bar discards the default style's geometry
  // bindings, so a custom bar must position itself or it renders at 0,0.
  Controls.ScrollBar.vertical: Controls.ScrollBar {
    id: verticalBar
    parent: root
    x: root.mirrored ? 0 : root.width - width
    y: root.topPadding
    height: root.availableHeight
    policy: root.verticalScrollBarEnabled
      ? Controls.ScrollBar.AsNeeded
      : Controls.ScrollBar.AlwaysOff

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
    parent: root
    x: root.leftPadding
    y: root.height - height
    width: root.availableWidth
    policy: Controls.ScrollBar.AlwaysOff

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
