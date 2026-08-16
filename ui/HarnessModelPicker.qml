import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "../models/HarnessPickerModel.js" as PickerModel

Item {
  id: root

  property string profileId: ""
  property var profiles: []
  property var modelCatalogs: ({})
  property var modelCatalogErrors: ({})
  property var modelRequests: ({})
  property string expandedProfileId: ""
  property string filterText: ""
  property var rows: []

  property color foreground: Color.popups.text
  property color background: Color.popups.background
  property color popupBorder: Color.popups.border
  property color accent: Color.accent
  property string fontFamily: Style.font.menuFamily
  readonly property var popupBorderSpec: Border.localOrSurfaceSpec(
    "popups", "border", popupBorder, Color.popups.border,
    Style.normalBorderWidth
  )
  readonly property bool popupOpen: pickerPopup.opened
  readonly property var currentSelection: PickerModel.currentSelection(
    profiles, profileId, modelCatalogs
  )

  signal selectionRequested(string profileId, string modelId)
  signal modelDiscoveryRequested(string profileId, string adapterId, bool refresh)

  function profileFor(identifier) {
    return PickerModel.profileById(root.profiles, identifier)
  }

  function loadingAdapters() {
    var result = ({})
    for (var requestId in root.modelRequests)
      result[String(root.modelRequests[requestId])] = true
    return result
  }

  function rebuildRows() {
    root.rows = PickerModel.buildRows({
      profiles: root.profiles,
      activeProfileId: root.profileId,
      expandedProfileId: root.expandedProfileId,
      catalogs: root.modelCatalogs,
      query: root.filterText,
      loadingAdapters: root.loadingAdapters(),
      errors: root.modelCatalogErrors
    })
    if (resultList.currentIndex >= root.rows.length)
      resultList.currentIndex = Math.max(0, root.rows.length - 1)
  }

  function requestProfileModels(identifier, refresh) {
    var profile = root.profileFor(identifier)
    if (!profile) return
    root.modelDiscoveryRequested(
      String(profile.id), String(profile.adapterId || "custom"), Boolean(refresh)
    )
  }

  function toggleHarness(identifier) {
    if (root.expandedProfileId === identifier) {
      root.expandedProfileId = ""
      root.filterText = ""
      Qt.callLater(function() {
        root.selectActiveHarness()
        resultList.forceActiveFocus()
      })
      return
    }
    root.filterText = ""
    root.expandedProfileId = identifier
    root.requestProfileModels(identifier, false)
    Qt.callLater(function() {
      resultList.currentIndex = 0
      resultList.positionViewAtBeginning()
      searchField.forceActiveFocus()
    })
  }

  function selectActiveHarness() {
    for (var index = 0; index < root.rows.length; index += 1) {
      if (root.rows[index].kind === "harness"
          && String(root.rows[index].profileId) === root.profileId) {
        resultList.currentIndex = index
        resultList.positionViewAtIndex(index, ListView.Contain)
        return
      }
    }
    resultList.currentIndex = root.rows.length > 0 ? 0 : -1
  }

  function activateRow(index) {
    if (index < 0 || index >= root.rows.length) return
    var row = root.rows[index]
    if (row.kind === "harness") {
      root.toggleHarness(String(row.profileId))
    } else if (row.kind === "model") {
      root.selectionRequested(String(row.profileId), String(row.modelId || ""))
      pickerPopup.close()
    }
  }

  function moveCursor(delta) {
    if (root.rows.length === 0) return
    var candidate = resultList.currentIndex
    for (var attempt = 0; attempt < root.rows.length; attempt += 1) {
      candidate = Math.max(0, Math.min(root.rows.length - 1, candidate + delta))
      if (root.rows[candidate].kind !== "status") {
        resultList.currentIndex = candidate
        resultList.positionViewAtIndex(candidate, ListView.Contain)
        return
      }
      if (candidate === 0 || candidate === root.rows.length - 1) return
    }
  }

  function open() { pickerPopup.open() }
  function close() { pickerPopup.close() }
  function toggle() { pickerPopup.opened ? pickerPopup.close() : pickerPopup.open() }
  function focusTrigger() { trigger.forceActiveFocus() }

  onProfilesChanged: rebuildRows()
  onProfileIdChanged: rebuildRows()
  onModelCatalogsChanged: rebuildRows()
  onModelCatalogErrorsChanged: rebuildRows()
  onModelRequestsChanged: rebuildRows()
  onExpandedProfileIdChanged: rebuildRows()
  onFilterTextChanged: rebuildRows()
  Component.onCompleted: rebuildRows()

  implicitWidth: Style.space(270)
  implicitHeight: Style.spacing.controlHeight

  BorderSurface {
    id: trigger
    anchors.fill: parent
    radius: Style.cornerRadius
    activeFocusOnTab: root.enabled

    readonly property bool hot: triggerHover.hovered
    color: Style.controlFill(activeFocus, hot, root.foreground, root.accent)
    borderSpec: Border.controlSpec(
      activeFocus ? "focus" : (hot ? "hover-cursor" : "normal"),
      root.foreground,
      root.accent
    )

    HoverHandler { id: triggerHover }

    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
          || event.key === Qt.Key_Space || event.key === Qt.Key_Down) {
        root.toggle()
        event.accepted = true
      } else if (event.key === Qt.Key_Escape && pickerPopup.opened) {
        pickerPopup.close()
        event.accepted = true
      }
    }

    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: trigger.borderLeft + Style.spacing.controlPaddingX
      anchors.rightMargin: trigger.borderRight + Style.spacing.controlGap
      spacing: Style.spacing.sm

      Text {
        text: root.currentSelection.profileIcon
        color: root.enabled ? root.foreground : Qt.darker(root.foreground, 2.0)
        font.family: root.fontFamily
        font.pixelSize: Style.font.icon
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        text: root.currentSelection.profileName
        color: root.enabled ? root.foreground : Qt.darker(root.foreground, 2.0)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
        elide: Text.ElideRight
        Layout.maximumWidth: Style.space(105)
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        text: "·"
        color: Qt.darker(root.foreground, 1.5)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        text: root.currentSelection.modelLabel
        color: Qt.darker(root.foreground, 1.25)
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
      }

      Text {
        text: pickerPopup.opened ? "󰅃" : "󰅀"
        color: Qt.darker(root.foreground, 1.2)
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        Layout.alignment: Qt.AlignVCenter
      }
    }

    MouseArea {
      anchors.fill: parent
      enabled: root.enabled
      cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
      onClicked: {
        trigger.forceActiveFocus()
        root.toggle()
      }
    }

    PanelToolTip {
      visible: triggerHover.hovered && !pickerPopup.opened
      text: "Choose agent and model"
      fontFamily: root.fontFamily
    }

    QQC.Popup {
      id: pickerPopup
      x: 0
      y: -height - Style.spacing.xs
      width: Math.max(trigger.width, Style.space(390))
      implicitHeight: Math.max(
        Style.space(230),
        Math.min(
          Style.space(430),
          resultList.contentHeight + searchHeader.height + Style.spacing.xxs + 1
        )
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
        root.filterText = ""
        root.expandedProfileId = ""
        root.rebuildRows()
        root.selectActiveHarness()
        Qt.callLater(function() { resultList.forceActiveFocus() })
      }
      onClosed: root.filterText = ""

      contentItem: Column {
        spacing: 0

        Item {
          id: searchHeader
          width: parent.width
          visible: root.expandedProfileId !== ""
          height: visible
            ? Style.spacing.popupRowHeight + Style.spacing.controlPaddingX
            : 0

          TextField {
            id: searchField
            anchors.fill: parent
            anchors.margins: Style.spacing.md
            placeholderText: "Filter models…"
            foreground: root.foreground
            accent: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            text: root.filterText
            onTextEdited: root.filterText = text

            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                pickerPopup.close()
                event.accepted = true
              } else if (event.key === Qt.Key_Down) {
                resultList.forceActiveFocus()
                root.moveCursor(1)
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                var models = root.rows.filter(function(row) { return row.kind === "model" })
                if (models.length === 1) {
                  root.selectionRequested(
                    String(models[0].profileId), String(models[0].modelId || "")
                  )
                  pickerPopup.close()
                }
                event.accepted = true
              }
            }
          }
        }

        Rectangle {
          width: parent.width
          height: 1
          color: Util.alpha(root.foreground, 0.10)
        }

        Item {
          width: parent.width
          height: pickerPopup.height - searchHeader.height - Style.spacing.xxs - 1

          Text {
            anchors.centerIn: parent
            visible: resultList.count === 0
            text: "No configured agents"
            color: Qt.darker(root.foreground, 1.6)
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          ListView {
            id: resultList
            anchors.fill: parent
            spacing: Style.spacing.xxs
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height
            model: root.rows
            currentIndex: -1
            keyNavigationEnabled: false

            QQC.ScrollBar.vertical: QQC.ScrollBar {
              policy: QQC.ScrollBar.AsNeeded
            }

            Keys.priority: Keys.BeforeItem
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                pickerPopup.close()
                event.accepted = true
              } else if (event.key === Qt.Key_Down || event.text === "j") {
                root.moveCursor(1)
                event.accepted = true
              } else if (event.key === Qt.Key_Up || event.text === "k") {
                if (resultList.currentIndex <= 0) searchField.forceActiveFocus()
                else root.moveCursor(-1)
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                         || event.key === Qt.Key_Space) {
                root.activateRow(resultList.currentIndex)
                event.accepted = true
              }
            }

            delegate: CursorSurface {
              id: pickerRow
              required property var modelData
              required property int index

              width: resultList.width
              height: modelData.kind === "harness"
                ? Style.space(42) : (modelData.description ? Style.space(42) : Style.space(34))
              hasCursor: index === resultList.currentIndex && modelData.kind !== "status"
              current: modelData.kind === "model" && Boolean(modelData.selected)
              foreground: root.foreground
              accent: root.accent

              MouseArea {
                anchors.fill: parent
                enabled: modelData.kind !== "status"
                hoverEnabled: true
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onEntered: resultList.currentIndex = pickerRow.index
                onClicked: root.activateRow(pickerRow.index)
              }

              RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Style.spacing.controlPaddingX
                  + (modelData.kind === "harness" ? 0 : Style.space(22))
                anchors.rightMargin: Style.spacing.controlPaddingX
                spacing: Style.spacing.controlGap

                Text {
                  text: modelData.kind === "harness"
                    ? (root.expandedProfileId
                      ? "󰁍" : String(modelData.icon || "󰚩"))
                    : (modelData.kind === "model"
                      ? (modelData.selected ? "󰄬" : "󰘦")
                      : (modelData.error ? "󰅚" : "󰔟"))
                  color: modelData.error
                    ? Color.urgent
                    : (pickerRow.hasCursor || pickerRow.current
                      ? Style.hoverStateColor(root.foreground, root.accent)
                      : root.foreground)
                  font.family: root.fontFamily
                  font.pixelSize: modelData.kind === "harness"
                    ? Style.font.icon : Style.font.body
                  Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                  Layout.fillWidth: true
                  spacing: Style.spacing.xxs
                  Layout.alignment: Qt.AlignVCenter

                  Text {
                    Layout.fillWidth: true
                    text: String(modelData.label || "")
                    color: modelData.error
                      ? Color.urgent
                      : (pickerRow.hasCursor || pickerRow.current
                        ? Style.hoverStateColor(root.foreground, root.accent)
                        : root.foreground)
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                    font.bold: modelData.kind === "harness"
                      ? Boolean(modelData.selected) : Boolean(modelData.selected)
                    elide: Text.ElideRight
                  }

                  Text {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: modelData.kind === "harness"
                      ? String(modelData.adapterId || "custom").toUpperCase()
                      : String(modelData.description || "")
                    color: Qt.darker(root.foreground, 1.5)
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                  }
                }

                PanelActionButton {
                  visible: modelData.kind === "harness"
                    && Boolean(modelData.expanded)
                    && modelData.adapterId !== "custom"
                  iconText: "󰑐"
                  tooltipText: "Refresh model catalog"
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  focusable: true
                  enabled: !root.loadingAdapters()[String(modelData.adapterId)]
                  Layout.alignment: Qt.AlignVCenter
                  onClicked: root.modelDiscoveryRequested(
                    String(modelData.profileId), String(modelData.adapterId), true
                  )
                }

                Text {
                  visible: modelData.kind === "harness"
                    && root.expandedProfileId === ""
                  text: "󰅀"
                  color: Qt.darker(root.foreground, 1.2)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  Layout.alignment: Qt.AlignVCenter
                }
              }
            }
          }
        }
      }
    }
  }
}
