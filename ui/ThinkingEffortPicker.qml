import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "../models/EffortModel.js" as EffortModel

Item {
  id: root

  property var choices: []
  property var value: null
  property var rows: []
  property string currentLabel: "Default"
  property string shortcutHint: ""
  property color foreground: Color.popups.text
  property color background: Color.popups.background
  property color popupBorder: Color.popups.border
  property color accent: Color.accent
  property string fontFamily: Style.font.menuFamily
  readonly property bool popupOpen: effortPopup.opened
  readonly property var popupBorderSpec: Border.localOrSurfaceSpec(
    "popups", "border", popupBorder, Color.popups.border,
    Style.normalBorderWidth
  )

  signal selectionRequested(var value)

  function rebuild() {
    root.rows = EffortModel.rows(root.value, root.choices)
    root.currentLabel = EffortModel.label(root.value, root.choices)
    if (effortList.currentIndex >= root.rows.length)
      effortList.currentIndex = Math.max(0, root.rows.length - 1)
  }

  function selectCurrent() {
    if (effortList.currentIndex < 0 || effortList.currentIndex >= root.rows.length)
      return
    root.selectionRequested(root.rows[effortList.currentIndex].id)
    effortPopup.close()
    trigger.forceActiveFocus()
  }

  function moveCursor(delta) {
    if (!root.rows.length) return
    effortList.currentIndex = Math.max(
      0,
      Math.min(root.rows.length - 1, effortList.currentIndex + delta)
    )
    effortList.positionViewAtIndex(effortList.currentIndex, ListView.Contain)
  }

  function selectBoundary(index) {
    if (!root.rows.length) return
    effortList.currentIndex = index
    effortList.positionViewAtIndex(index, ListView.Contain)
  }

  function open() {
    if (root.enabled && root.choices.length > 0) effortPopup.open()
  }
  function close() { effortPopup.close() }
  function focusTrigger() { trigger.forceActiveFocus() }

  onChoicesChanged: rebuild()
  onValueChanged: rebuild()
  Component.onCompleted: rebuild()

  implicitWidth: Style.space(96)
  implicitHeight: Style.spacing.controlHeight

  BorderSurface {
    id: trigger
    anchors.fill: parent
    activeFocusOnTab: root.enabled && root.choices.length > 0
    radius: Style.cornerRadius
    color: Style.controlFill(
      activeFocus,
      triggerHover.hovered && root.choices.length > 0,
      root.foreground,
      root.accent
    )
    borderSpec: Border.controlSpec(
      activeFocus ? "focus"
        : (triggerHover.hovered && root.choices.length > 0
          ? "hover-cursor" : "normal"),
      root.foreground,
      root.accent
    )

    HoverHandler { id: triggerHover }

    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
          || event.key === Qt.Key_Space || event.key === Qt.Key_Down
          || event.key === Qt.Key_Up) {
        root.open()
        event.accepted = true
      } else if (event.key === Qt.Key_Escape && effortPopup.opened) {
        effortPopup.close()
        event.accepted = true
      }
    }

    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: trigger.borderLeft + Style.spacing.controlPaddingX
      anchors.rightMargin: trigger.borderRight + Style.spacing.controlGap
      spacing: Style.spacing.xs

      Text {
        text: "󰓅"
        color: root.enabled && root.choices.length > 0
          ? root.foreground : Qt.darker(root.foreground, 1.8)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        Layout.fillWidth: true
        text: root.currentLabel
        color: root.enabled && root.choices.length > 0
          ? root.foreground : Qt.darker(root.foreground, 1.8)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        visible: root.choices.length > 0
        text: effortPopup.opened ? "󰅃" : "󰅀"
        color: Qt.darker(root.foreground, 1.2)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        Layout.alignment: Qt.AlignVCenter
      }
    }

    MouseArea {
      anchors.fill: parent
      enabled: root.choices.length > 0 && root.enabled
      cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
      onClicked: {
        trigger.forceActiveFocus()
        effortPopup.opened ? root.close() : root.open()
      }
    }

    PanelToolTip {
      visible: triggerHover.hovered && !effortPopup.opened
      text: root.choices.length > 0
        ? "Choose thinking effort"
          + (root.shortcutHint ? " (" + root.shortcutHint + ")" : "")
        : "This model does not advertise thinking effort"
      fontFamily: root.fontFamily
    }

    QQC.Popup {
      id: effortPopup
      x: 0
      y: -height - Style.spacing.xs
      width: Math.max(trigger.width, Style.space(250))
      implicitHeight: Math.min(
        Style.space(310),
        effortList.contentHeight + effortHelp.implicitHeight
          + Style.spacing.controlPaddingX * 3
      )
      padding: Style.spacing.hairline
      leftPadding: Border.left(root.popupBorderSpec) + Style.spacing.hairline
      rightPadding: Border.right(root.popupBorderSpec) + Style.spacing.hairline
      topPadding: Border.top(root.popupBorderSpec) + Style.spacing.hairline
      bottomPadding: Border.bottom(root.popupBorderSpec) + Style.spacing.hairline
      modal: false
      focus: true
      closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside

      background: BorderSurface {
        color: root.background
        borderSpec: root.popupBorderSpec
        radius: Style.cornerRadius
      }

      onOpened: {
        root.rebuild()
        var selectedIndex = 0
        for (var index = 0; index < root.rows.length; index += 1) {
          if (root.rows[index].selected) {
            selectedIndex = index
            break
          }
        }
        effortList.currentIndex = selectedIndex
        effortList.positionViewAtIndex(selectedIndex, ListView.Contain)
        Qt.callLater(function() { effortList.forceActiveFocus() })
      }

      contentItem: ColumnLayout {
        spacing: Style.spacing.xs

        ListView {
          id: effortList
          Layout.fillWidth: true
          Layout.fillHeight: true
          Layout.minimumHeight: Math.min(contentHeight, Style.space(180))
          clip: true
          spacing: Style.spacing.xxs
          model: root.rows
          currentIndex: 0
          keyNavigationEnabled: false
          boundsBehavior: Flickable.StopAtBounds
          interactive: contentHeight > height

          QQC.ScrollBar.vertical: QQC.ScrollBar {
            policy: QQC.ScrollBar.AsNeeded
          }

          Keys.priority: Keys.BeforeItem
          Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape) {
              root.close()
              trigger.forceActiveFocus()
              event.accepted = true
            } else if (event.key === Qt.Key_Down) {
              root.moveCursor(1)
              event.accepted = true
            } else if (event.key === Qt.Key_Up) {
              root.moveCursor(-1)
              event.accepted = true
            } else if (event.key === Qt.Key_Home) {
              root.selectBoundary(0)
              event.accepted = true
            } else if (event.key === Qt.Key_End) {
              root.selectBoundary(root.rows.length - 1)
              event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                       || event.key === Qt.Key_Space) {
              root.selectCurrent()
              event.accepted = true
            }
          }

          delegate: CursorSurface {
            id: effortRow
            required property var modelData
            required property int index

            width: effortList.width
            height: modelData.description ? Style.space(48) : Style.space(36)
            hasCursor: index === effortList.currentIndex
            current: Boolean(modelData.selected)
            foreground: root.foreground
            accent: root.accent

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onEntered: effortList.currentIndex = effortRow.index
              onClicked: {
                effortList.currentIndex = effortRow.index
                root.selectCurrent()
              }
            }

            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: Style.spacing.controlPaddingX
              anchors.rightMargin: Style.spacing.controlPaddingX
              spacing: Style.spacing.controlGap

              Text {
                text: modelData.selected ? "󰄬" : "󰘦"
                color: effortRow.hasCursor || effortRow.current
                  ? Style.hoverStateColor(root.foreground, root.accent)
                  : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                Layout.alignment: Qt.AlignVCenter
              }

              ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.spacing.xxs
                Layout.alignment: Qt.AlignVCenter

                Text {
                  Layout.fillWidth: true
                  text: modelData.label
                  color: effortRow.hasCursor || effortRow.current
                    ? Style.hoverStateColor(root.foreground, root.accent)
                    : root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: Boolean(modelData.selected)
                  elide: Text.ElideRight
                }

                Text {
                  Layout.fillWidth: true
                  visible: Boolean(modelData.description)
                  text: modelData.description
                  color: Qt.darker(root.foreground, 1.45)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
              }
            }
          }
        }

        Text {
          id: effortHelp
          Layout.fillWidth: true
          Layout.leftMargin: Style.spacing.controlPaddingX
          Layout.rightMargin: Style.spacing.controlPaddingX
          Layout.bottomMargin: Style.spacing.sm
          text: "Higher effort may increase latency and usage."
          color: Qt.darker(root.foreground, 1.45)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          textFormat: Text.PlainText
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
