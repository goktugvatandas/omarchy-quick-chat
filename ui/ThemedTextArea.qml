import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui

Controls.TextArea {
  id: root

  property color foreground: Color.popups.text
  property color accent: Color.accent
  readonly property bool hot: activeFocus || hovered
  readonly property var controlBorder: Border.controlSpec(
    activeFocus ? "focus" : (hovered ? "hover-cursor" : "normal"),
    foreground,
    accent
  )

  font.family: Style.font.menuFamily
  font.pixelSize: Style.font.body
  color: foreground
  placeholderTextColor: Util.alpha(foreground, 0.55)
  selectionColor: Style.selectionFillFor(foreground, accent)
  selectedTextColor: foreground
  selectByMouse: true
  tabChangesFocus: true
  leftPadding: Style.spacing.controlPaddingX + Border.left(controlBorder)
  rightPadding: Style.spacing.controlPaddingX + Border.right(controlBorder)
  topPadding: Style.spacing.inputPaddingY + Border.top(controlBorder)
  bottomPadding: Style.spacing.inputPaddingY + Border.bottom(controlBorder)

  background: BorderSurface {
    color: Style.controlFill(root.activeFocus, root.hovered, root.foreground, root.accent)
    borderSpec: root.controlBorder
    radius: Style.cornerRadius
  }
}
