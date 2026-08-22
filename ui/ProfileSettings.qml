import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import qs.Commons
import qs.Ui
import "../models/EffortModel.js" as EffortModel
import "../models/TextBoundary.js" as TextBoundary

FocusScope {
  id: root

  property var profileState: null
  property var modelOptions: []
  property var adapterStates: []
  property bool modelsLoading: false
  property string modelsError: ""
  property string shortcutError: ""
  property bool manualModelEntry: false
  property string editingProfileId: ""
  property string loadedProfileId: ""
  readonly property bool editing: editingProfileId.length > 0
  readonly property var launchers: profileState && profileState.profiles
    ? profileState.profiles : []
  readonly property string defaultLauncherId: profileState
    ? String(profileState.selectedId || "") : ""
  readonly property var editingProfile: {
    for (var index = 0; index < launchers.length; index += 1) {
      if (launchers[index].id === editingProfileId) return launchers[index]
    }
    return null
  }
  readonly property string editingAdapterId: adapterPicker.value
  readonly property bool dialogOpen: removeDialog.opened
  readonly property bool shortcutCaptureActive: shortcutEditor.captureActive
  signal historyLimitChanged(var value)
  signal profilePatchRequested(string profileId, var values)
  signal createRequested()
  signal defaultChanged(string profileId)
  signal duplicateRequested(string profileId)
  signal removeRequested(string profileId)
  signal modelDiscoveryRequested(string adapterId, bool refresh)
  signal uiShortcutsChanged(var shortcuts)

  function launcherMeta(profile) {
    var parts = [String(profile.adapterId || "custom")]
    parts.push(profile.model ? String(profile.model) : "default model")
    if (profile.shortcut) parts.push(String(profile.shortcut))
    return parts.join(" · ")
  }

  function scrollToTop() {
    var flick = settingsScroll.contentItem
    if (flick && flick.contentY !== undefined) flick.contentY = 0
  }

  function focusPage() {
    if (root.editing) {
      nameField.forceActiveFocus()
      Qt.callLater(function() { root.ensureFocusedItemVisible(nameField) })
      return
    }
    var firstRow = launcherRepeater.count > 0 ? launcherRepeater.itemAt(0) : null
    var target = firstRow || addButton
    target.forceActiveFocus()
    Qt.callLater(function() { root.ensureFocusedItemVisible(target) })
  }

  function openEditor(profileId) {
    editingProfileId = profileId
    loadProfile()
    scrollToTop()
    discoverCurrentModels(false)
    Qt.callLater(function() {
      if (root.editing) nameField.forceActiveFocus()
    })
  }

  function closeEditor() {
    editingProfileId = ""
    loadedProfileId = ""
    scrollToTop()
    Qt.callLater(root.focusPage)
  }

  function closeTransient() {
    if (removeDialog.opened) {
      removeDialog.opened = false
      return true
    }
    if (root.editing) {
      closeEditor()
      return true
    }
    return false
  }

  function ensureFocusedItemVisible(item) {
    if (!item || !root.visible) return
    var flick = settingsScroll.contentItem
    if (!flick || flick.contentY === undefined) return
    var content = flick.contentItem || flick
    var point = item.mapToItem(content, 0, 0)
    var top = point.y
    var bottom = top + (item.height || 0)
    var margin = Style.space(16)
    if (top < flick.contentY + margin)
      flick.contentY = Math.max(0, top - margin)
    else if (bottom > flick.contentY + flick.height - margin)
      flick.contentY = Math.min(
        Math.max(0, flick.contentHeight - flick.height),
        bottom + margin - flick.height
      )
  }

  function loadProfile() {
    if (!editingProfile) return
    nameField.text = editingProfile.name || ""
    iconField.text = editingProfile.icon || ""
    adapterPicker.value = editingProfile.adapterId || "codex"
    modelPicker.value = editingProfile.model || ""
    effortPicker.value = editingProfile.thinkingEffort || null
    customModelField.text = modelPicker.value
    manualModelEntry = false
    instructionsField.text = editingProfile.systemInstructions || ""
    directoryStrategy.value = editingProfile.workingDirectoryStrategy || "home"
    directoryField.text = editingProfile.workingDirectory || ""
    contextField.text = (editingProfile.contextProviders || []).join(", ")
    permissionPicker.value = editingProfile.permissionPolicy || "read-only"
    shortcutField.text = editingProfile.shortcut || ""
    profileUnlimited.checked = editingProfile.historyLimit === null
    profileRetention.text = editingProfile.historyLimit === null
      ? "20" : String(editingProfile.historyLimit || 20)
    privateDefault.checked = Boolean(editingProfile.privateByDefault)
    advancedField.text = (editingProfile.advancedArgs || []).join("\n")
    customExecutable.text = editingProfile.customExecutable || ""
    customArguments.text = (editingProfile.customArgs || []).join("\n")
    customStdin.checked = Boolean(editingProfile.customStdin)
    customReadOnly.text = (editingProfile.customReadOnlyArgs || []).join("\n")
    customOutput.value = editingProfile.customOutput || "plain"
    transportPicker.value = editingProfile.transport || "process"
    advancedSection.expanded = adapterPicker.value === "custom"
    loadedProfileId = editingProfileId
  }

  function discoverCurrentModels(refresh) {
    if (!visible || !editingProfile) return
    Qt.callLater(function() {
      if (root.visible && root.editingProfile)
        root.modelDiscoveryRequested(adapterPicker.value, Boolean(refresh))
    })
  }

  function searchableModelOptions() {
    var options = [{
      value: "",
      label: "CLI default",
      description: "Use the harness default model"
    }]
    for (var index = 0; index < root.modelOptions.length; index += 1) {
      var model = root.modelOptions[index]
      options.push({
        value: String(model.id || ""),
        label: TextBoundary.safeMetadata(model.label || model.id || ""),
        description: TextBoundary.safeMetadata(model.description || "")
      })
    }
    return options
  }

  function editingEffortChoices() {
    var catalogs = ({})
    catalogs[adapterPicker.value] = root.modelOptions
    return EffortModel.choices({
      adapterId: adapterPicker.value,
      model: modelPicker.value || null
    }, root.adapterStates, catalogs)
  }

  function reconcileEditingEffort() {
    if (root.modelsLoading) return
    var reconciliation = EffortModel.reconcile(
      effortPicker.value,
      root.editingEffortChoices()
    )
    if (reconciliation.reset) effortPicker.value = null
  }

  function toggleManualModelEntry() {
    if (!manualModelEntry)
      customModelField.text = modelPicker.value
    manualModelEntry = !manualModelEntry
    Qt.callLater(function() {
      if (root.manualModelEntry) customModelField.forceActiveFocus()
      else modelPicker.forceActiveFocus()
    })
  }

  function values() {
    var historyValue = profileUnlimited.checked ? null : parseInt(profileRetention.text)
    if (historyValue !== null && (!historyValue || historyValue < 1))
      throw new Error("History limit must be positive")
    return {
      name: nameField.text.trim(),
      icon: iconField.text.trim(),
      adapterId: adapterPicker.value,
      model: modelPicker.value.trim() || null,
      thinkingEffort: effortPicker.value,
      systemInstructions: instructionsField.text,
      workingDirectoryStrategy: directoryStrategy.value,
      workingDirectory: directoryField.text.trim() || null,
      contextProviders: contextField.text.split(",").map(function(value) {
        return value.trim()
      }).filter(Boolean),
      permissionPolicy: permissionPicker.value,
      shortcut: shortcutField.text.trim() || null,
      historyLimit: historyValue,
      privateByDefault: privateDefault.checked,
      advancedArgs: advancedField.text.split("\n").map(function(value) {
        return value.trim()
      }).filter(Boolean),
      customExecutable: customExecutable.text.trim() || null,
      customArgs: customArguments.text.split("\n").map(function(value) {
        return value.trim()
      }).filter(Boolean),
      customStdin: customStdin.checked,
      customReadOnlyArgs: customReadOnly.text.split("\n").map(function(value) {
        return value.trim()
      }).filter(Boolean),
      customOutput: customOutput.value,
      transport: transportPicker.value
    }
  }

  function containsSettingsItem(item) {
    var candidate = item
    while (candidate) {
      if (candidate === root) return true
      candidate = candidate.parent
    }
    return false
  }

  function moveTabFocus(forward) {
    var current = root.Window.window ? root.Window.window.activeFocusItem : null
    var fallback = root.editing
      ? (forward ? nameField : saveButton) : addButton
    if (!current || !root.containsSettingsItem(current)
        || typeof current.nextItemInFocusChain !== "function") {
      fallback.forceActiveFocus()
      Qt.callLater(function() { root.ensureFocusedItemVisible(fallback) })
      return
    }
    var next = current.nextItemInFocusChain(forward)
    var steps = 0
    while (next && !root.containsSettingsItem(next) && steps < 256) {
      if (typeof next.nextItemInFocusChain !== "function") break
      next = next.nextItemInFocusChain(forward)
      steps += 1
    }
    if (!next || next === current || next === root
        || !root.containsSettingsItem(next)) next = fallback
    next.forceActiveFocus()
    Qt.callLater(function() { root.ensureFocusedItemVisible(next) })
  }

  onProfileStateChanged: {
    if (editing && loadedProfileId !== editingProfileId) loadProfile()
    if (editing && !editingProfile) closeEditor()
  }
  onVisibleChanged: discoverCurrentModels(false)
  onModelOptionsChanged: reconcileEditingEffort()
  onAdapterStatesChanged: reconcileEditingEffort()
  onModelsLoadingChanged: {
    if (!modelsLoading) reconcileEditingEffort()
  }

  Keys.priority: Keys.BeforeItem
  Keys.onPressed: function(event) {
    if (root.dialogOpen || root.shortcutCaptureActive) return
    var backwards = event.key === Qt.Key_Backtab
      || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))
    var forwards = event.key === Qt.Key_Tab && event.modifiers === Qt.NoModifier
    if (!backwards && !forwards) return
    root.moveTabFocus(!backwards)
    event.accepted = true
  }

  Connections {
    id: focusWindowConnection
    target: root.Window.window
    ignoreUnknownSignals: true
    function onActiveFocusItemChanged() {
      if (focusWindowConnection.target)
        root.ensureFocusedItemVisible(focusWindowConnection.target.activeFocusItem)
    }
  }

  ThemedScrollView {
    id: settingsScroll
    anchors.fill: parent

    ColumnLayout {
      width: settingsScroll.availableWidth
      spacing: Style.space(12)

      // ── Launcher list ────────────────────────────────────────────────
      ColumnLayout {
        Layout.fillWidth: true
        visible: !root.editing
        spacing: Style.space(12)

        PanelHero {
          Layout.fillWidth: true
          title: "Launchers"
          meta: "Each launcher pairs an agent with a shortcut"
          foreground: Color.popups.text
          fontFamily: Style.font.menuFamily

          iconComponent: Component {
            Text {
              text: "󱓞"
              color: Color.popups.text
              font.family: Style.font.menuFamily
              font.pixelSize: Style.font.display
            }
          }
        }

        PanelSeparator {
          Layout.fillWidth: true
          foreground: Color.popups.text
        }

        Repeater {
          id: launcherRepeater
          model: root.launchers

          BorderSurface {
            id: launcherRow
            required property var modelData
            required property int index
            readonly property bool isDefault:
              modelData.id === root.defaultLauncherId

            Layout.fillWidth: true
            implicitHeight: launcherRowContent.implicitHeight
              + Style.spacing.xl * 2
            radius: Style.cornerRadius
            activeFocusOnTab: true
            color: Style.controlFill(
              activeFocus, launcherRowHover.hovered,
              Color.popups.text, Color.accent
            )
            borderSpec: Border.controlSpec(
              activeFocus ? "focus"
                : (launcherRowHover.hovered ? "hover-cursor" : "normal"),
              Color.popups.text,
              Color.accent
            )

            HoverHandler { id: launcherRowHover }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.openEditor(launcherRow.modelData.id)
            }

            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                  || event.key === Qt.Key_Space) {
                root.openEditor(launcherRow.modelData.id)
                event.accepted = true
              }
            }

            RowLayout {
              id: launcherRowContent
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.leftMargin: Style.space(8)
              anchors.rightMargin: Style.space(8)
              spacing: Style.space(12)

              Text {
                text: launcherRow.modelData.icon || "󰚩"
                textFormat: Text.PlainText
                color: Color.popups.text
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.iconLarge
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: Style.space(34)
                Layout.alignment: Qt.AlignVCenter
              }

              ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.spacing.labelGap

                RowLayout {
                  Layout.fillWidth: true
                  spacing: Style.spacing.sm

                  Text {
                    text: launcherRow.modelData.name || "Untitled"
                    textFormat: Text.PlainText
                    color: Color.popups.text
                    font.family: Style.font.menuFamily
                    font.pixelSize: Style.font.heading
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                    Layout.maximumWidth:
                      launcherRowContent.width - Style.space(140)
                  }

                  BorderSurface {
                    visible: launcherRow.isDefault
                    implicitWidth: defaultPill.implicitWidth + Style.space(12)
                    implicitHeight: defaultPill.implicitHeight + Style.space(4)
                    radius: height / 2
                    color: Util.alpha(Color.accent, 0.16)
                    borderSpec: Border.flat(
                      Util.alpha(Color.accent, 0.4), Style.normalBorderWidth
                    )

                    Text {
                      id: defaultPill
                      anchors.centerIn: parent
                      text: "DEFAULT"
                      color: Color.popups.text
                      font.family: Style.font.menuFamily
                      font.pixelSize: Style.font.caption
                      font.letterSpacing: 1
                    }
                  }

                  Item { Layout.fillWidth: true }
                }

                Text {
                  Layout.fillWidth: true
                  text: root.launcherMeta(launcherRow.modelData)
                  textFormat: Text.PlainText
                  color: Qt.darker(Color.popups.text, 1.4)
                  font.family: Style.font.menuFamily
                  font.pixelSize: Style.font.bodySmall
                  elide: Text.ElideRight
                }
              }

              PanelActionButton {
                visible: !launcherRow.isDefault
                iconText: "󰄬"
                tooltipText: "Make default launcher"
                foreground: Color.popups.text
                fontFamily: Style.font.menuFamily
                focusable: true
                Layout.alignment: Qt.AlignVCenter
                onClicked: root.defaultChanged(launcherRow.modelData.id)
              }

              Text {
                text: "›"
                color: Qt.darker(Color.popups.text, 2.2)
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.heading
                Layout.alignment: Qt.AlignVCenter
              }
            }
          }
        }

        Button {
          id: addButton
          Layout.alignment: Qt.AlignRight
          text: "New launcher"
          iconText: "󰐕"
          foreground: Color.popups.text
          fontFamily: Style.font.menuFamily
          bordered: true
          focusable: true
          onClicked: root.createRequested()
        }

        PanelSeparator {
          Layout.fillWidth: true
          foreground: Color.popups.text
        }

        CollapsibleSection {
          Layout.fillWidth: true
          title: "Window shortcuts"
          hint: "Model, history, private mode…"

          ShortcutEditor {
            id: shortcutEditor
            Layout.fillWidth: true
            profileState: root.profileState
            shortcuts: root.profileState ? root.profileState.uiShortcuts : ({})
            onUpdateRequested: function(shortcuts) {
              root.uiShortcutsChanged(shortcuts)
            }
          }
        }

        CollapsibleSection {
          Layout.fillWidth: true
          title: "History"
          hint: root.profileState && root.profileState.historyLimit === null
            ? "Unlimited" : "Keep recent conversations"

          Toggle {
            id: globalUnlimited
            Layout.fillWidth: true
            label: "Unlimited global history"
            description: "Keep conversations until cleared"
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            checked: Boolean(root.profileState && root.profileState.historyLimit === null)
            onClicked: root.historyLimitChanged(checked ? 20 : null)
          }
        }
      }

      // ── Launcher editor ──────────────────────────────────────────────
      ColumnLayout {
        Layout.fillWidth: true
        visible: root.editing
        spacing: Style.space(12)

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.spacing.sm

          PanelActionButton {
            iconText: "󰁍"
            tooltipText: "Back to launchers"
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            focusable: true
            Layout.alignment: Qt.AlignVCenter
            onClicked: root.closeEditor()
          }

          PanelHero {
            Layout.fillWidth: true
            title: root.editingProfile ? (root.editingProfile.name || "Launcher") : "Launcher"
            meta: root.editingProfile ? root.launcherMeta(root.editingProfile) : ""
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily

            iconComponent: Component {
              Text {
                text: root.editingProfile ? (root.editingProfile.icon || "󰚩") : "󰚩"
                textFormat: Text.PlainText
                color: Color.popups.text
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.display
              }
            }

            trailingControl: Component {
              Row {
                spacing: Style.spacing.sm

                PanelActionButton {
                  iconText: "󰆏"
                  tooltipText: "Duplicate launcher"
                  foreground: Color.popups.text
                  fontFamily: Style.font.menuFamily
                  focusable: true
                  onClicked: root.duplicateRequested(root.editingProfileId)
                }

                PanelActionButton {
                  iconText: "󰆴"
                  tooltipText: "Remove launcher"
                  foreground: Color.popups.text
                  hoverColor: Color.urgent
                  fontFamily: Style.font.menuFamily
                  focusable: true
                  onClicked: removeDialog.opened = true
                }
              }
            }
          }
        }

        PanelSeparator {
          Layout.fillWidth: true
          foreground: Color.popups.text
        }

        GridLayout {
          Layout.fillWidth: true
          columns: 2
          columnSpacing: Style.spacing.controlGap
          rowSpacing: Style.spacing.controlGap

          FormField {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: "Name"
            TextField {
              id: nameField
              width: parent.width
              foreground: Color.popups.text
              font.family: Style.font.menuFamily
              placeholderText: "Launcher name"
            }
          }

          FormField {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: "Harness"
            Dropdown {
              id: adapterPicker
              width: parent.width
              showLabel: false
              foreground: Color.popups.text
              fontFamily: Style.font.menuFamily
              options: ["codex", "claude", "opencode", "grok", "cursor", "pi", "custom"]
              value: "codex"
              onChanged: function(adapterId) {
                modelPicker.value = ""
                effortPicker.value = null
                customModelField.text = ""
                root.manualModelEntry = false
                if (adapterId === "custom") advancedSection.expanded = true
                root.modelDiscoveryRequested(adapterId, false)
              }
            }
          }

          FormField {
            Layout.fillWidth: true
            Layout.columnSpan: 2
            label: "Model"
            ColumnLayout {
              width: parent.width
              spacing: Style.spacing.labelGap

              RowLayout {
                Layout.fillWidth: true
                spacing: Style.spacing.sm

                SearchableDropdown {
                  id: modelPicker
                  Layout.fillWidth: true
                  visible: !root.manualModelEntry
                  showLabel: false
                  foreground: Color.popups.text
                  fontFamily: Style.font.menuFamily
                  options: root.searchableModelOptions()
                  placeholderText: root.modelsLoading
                    ? "Discovering models..." : "Search models..."
                  emptyText: "No matching models"
                  onValueChanged: root.reconcileEditingEffort()
                }

                TextField {
                  id: customModelField
                  Layout.fillWidth: true
                  visible: root.manualModelEntry
                  foreground: Color.popups.text
                  font.family: Style.font.menuFamily
                  placeholderText: "Custom model ID"
                  onTextEdited: modelPicker.value = text
                }

                PanelActionButton {
                  iconText: root.manualModelEntry ? "󰅖" : "󰘦"
                  tooltipText: root.manualModelEntry
                    ? "Choose a discovered model" : "Enter a custom model ID"
                  foreground: Color.popups.text
                  fontFamily: Style.font.menuFamily
                  focusable: true
                  onClicked: root.toggleManualModelEntry()
                }

                PanelActionButton {
                  iconText: "󰑐"
                  tooltipText: "Refresh model catalog"
                  foreground: Color.popups.text
                  fontFamily: Style.font.menuFamily
                  focusable: true
                  enabled: adapterPicker.value !== "custom" && !root.modelsLoading
                  onClicked: root.modelDiscoveryRequested(adapterPicker.value, true)
                }
              }

              Text {
                Layout.fillWidth: true
                visible: root.modelsLoading || root.modelsError.length > 0
                text: root.modelsLoading ? "Discovering models..." : root.modelsError
                color: root.modelsError.length > 0
                  ? Color.urgent : Qt.darker(Color.popups.text, 1.5)
                font.family: Style.font.menuFamily
                font.pixelSize: Style.font.caption
                textFormat: Text.PlainText
                elide: Text.ElideRight
              }
            }
          }

          FormField {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            label: "Summon shortcut"
            TextField {
              id: shortcutField
              width: parent.width
              foreground: Color.popups.text
              font.family: Style.font.menuFamily
              placeholderText: "SUPER ALT, G"
            }
          }

          Toggle {
            id: defaultToggle
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignBottom
            label: "Default launcher"
            description: "Summoned by the main shortcut and menu"
            foreground: Color.popups.text
            fontFamily: Style.font.menuFamily
            checked: root.editingProfileId === root.defaultLauncherId
            onClicked: {
              if (!checked) root.defaultChanged(root.editingProfileId)
            }
          }
        }

        FormField {
          Layout.fillWidth: true
          label: "System instructions"
          ThemedTextArea {
            id: instructionsField
            width: parent.width
            height: Style.space(88)
            placeholderText: "Optional behavior, e.g. answer in one short paragraph"
            wrapMode: TextEdit.Wrap
          }
        }

        BorderSurface {
          Layout.fillWidth: true
          visible: root.shortcutError.length > 0
          implicitHeight: shortcutErrorText.implicitHeight + Style.spacing.xl * 2
          color: Util.alpha(Color.urgent, 0.10)
          borderSpec: Border.flat(Util.alpha(Color.urgent, 0.35), Style.normalBorderWidth)
          radius: Style.cornerRadius

          Text {
            id: shortcutErrorText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: Style.space(12)
            anchors.rightMargin: Style.space(12)
            text: root.shortcutError
            color: Color.popups.text
            font.family: Style.font.menuFamily
            font.pixelSize: Style.font.caption
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
          }
        }

        CollapsibleSection {
          id: advancedSection
          Layout.fillWidth: true
          title: "Advanced"
          hint: "Icon, effort, permissions, workspace…"

          GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Style.spacing.controlGap
            rowSpacing: Style.spacing.controlGap

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Icon"
              TextField {
                id: iconField
                width: parent.width
                foreground: Color.popups.text
                font.family: Style.font.menuFamily
                placeholderText: "Nerd Font glyph"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Thinking effort"
              ThinkingEffortPicker {
                id: effortPicker
                width: parent.width
                choices: root.editingEffortChoices()
                onSelectionRequested: function(value) { effortPicker.value = value }
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Transport"
              Dropdown {
                id: transportPicker
                width: parent.width
                showLabel: false
                foreground: Color.popups.text
                fontFamily: Style.font.menuFamily
                options: ["process", "auto", "acp"]
                value: "process"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Permission"
              Dropdown {
                id: permissionPicker
                width: parent.width
                showLabel: false
                foreground: Color.popups.text
                fontFamily: Style.font.menuFamily
                options: ["read-only", "ask"]
                value: "read-only"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Working directory"
              Dropdown {
                id: directoryStrategy
                width: parent.width
                showLabel: false
                foreground: Color.popups.text
                fontFamily: Style.font.menuFamily
                options: [
                  { value: "home", label: "Home" },
                  { value: "fixed", label: "Fixed path" },
                  { value: "active-project", label: "Active project" }
                ]
                value: "home"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              visible: directoryStrategy.value === "fixed"
              label: "Fixed path"
              TextField {
                id: directoryField
                width: parent.width
                foreground: Color.popups.text
                font.family: Style.font.menuFamily
                placeholderText: "/absolute/project/path"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.columnSpan: 2
              label: "Allowed context"
              TextField {
                id: contextField
                width: parent.width
                foreground: Color.popups.text
                font.family: Style.font.menuFamily
                placeholderText: "window, screen, app, selection"
              }
            }

            Toggle {
              id: privateDefault
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Private by default"
              description: "Do not write Quick Chat history"
              foreground: Color.popups.text
              fontFamily: Style.font.menuFamily
              onClicked: checked = !checked
            }

            Toggle {
              id: profileUnlimited
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Use global retention"
              description: "Ignore a launcher-specific limit"
              foreground: Color.popups.text
              fontFamily: Style.font.menuFamily
              onClicked: checked = !checked
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "History limit"
              TextField {
                id: profileRetention
                width: parent.width
                enabled: !profileUnlimited.checked
                foreground: Color.popups.text
                font.family: Style.font.menuFamily
                placeholderText: "20"
                validator: IntValidator { bottom: 1 }
              }
            }
          }

          GridLayout {
            Layout.fillWidth: true
            visible: adapterPicker.value === "custom"
            columns: 2
            columnSpacing: Style.spacing.controlGap
            rowSpacing: Style.spacing.controlGap

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Executable"
              TextField {
                id: customExecutable
                width: parent.width
                foreground: Color.popups.text
                font.family: Style.font.menuFamily
                placeholderText: "Executable"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Output"
              Dropdown {
                id: customOutput
                width: parent.width
                showLabel: false
                foreground: Color.popups.text
                fontFamily: Style.font.menuFamily
                options: ["plain", "jsonl"]
                value: "plain"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Arguments"
              ThemedTextArea {
                id: customArguments
                width: parent.width
                height: Style.space(76)
                placeholderText: "One argument per line"
              }
            }

            FormField {
              Layout.fillWidth: true
              Layout.preferredWidth: 1
              label: "Read-only arguments"
              ThemedTextArea {
                id: customReadOnly
                width: parent.width
                height: Style.space(76)
                placeholderText: "One argument per line"
              }
            }

            Toggle {
              id: customStdin
              Layout.fillWidth: true
              Layout.columnSpan: 2
              label: "Send prompt on stdin"
              description: "Avoid prompt interpolation in argv"
              foreground: Color.popups.text
              fontFamily: Style.font.menuFamily
              onClicked: checked = !checked
            }
          }

          FormField {
            Layout.fillWidth: true
            label: "Advanced arguments"
            ThemedTextArea {
              id: advancedField
              width: parent.width
              height: Style.space(76)
              placeholderText: "One argument per line"
            }
          }
        }

        Button {
          id: saveButton
          Layout.alignment: Qt.AlignRight
          text: "Save launcher"
          iconText: "󰆓"
          enabled: Boolean(root.editingProfile) && nameField.text.trim().length > 0
          foreground: Color.popups.text
          fontFamily: Style.font.menuFamily
          bordered: true
          focusable: true
          onClicked: root.profilePatchRequested(root.editingProfileId, root.values())
        }
      }
    }
  }

  ConfirmDialog {
    id: removeDialog
    anchors.fill: parent
    message: "Remove this launcher? Existing history remains readable."
    confirmText: "Remove"
    onOpenedChanged: if (opened) forceActiveFocus()
    Keys.onPressed: function(event) {
      if (handleKey(event)) event.accepted = true
    }
    background: Color.popups.background
    foreground: Color.popups.text
    scrim: Util.alpha(Color.popups.background, 0.72)
    selectedBackground: Style.selectedFillFor(Color.popups.text, Color.accent)
    selectedText: Style.selectedStateColor(Color.popups.text, Color.accent)
    fontFamily: Style.font.menuFamily
    onCanceled: {
      opened = false
      Qt.callLater(root.focusPage)
    }
    onConfirmed: {
      opened = false
      root.removeRequested(root.editingProfileId)
    }
  }
}
