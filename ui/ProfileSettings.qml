import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "../models/EffortModel.js" as EffortModel

FocusScope {
  id: root

  property var profileState: null
  property var activeProfile: null
  property var modelOptions: []
  property var adapterStates: []
  property bool modelsLoading: false
  property string modelsError: ""
  property string shortcutError: ""
  property bool manualModelEntry: false
  readonly property string editingAdapterId: adapterPicker.value
  signal historyLimitChanged(var value)
  signal profilePatchRequested(var values)
  signal duplicateRequested()
  signal removeRequested()
  signal modelDiscoveryRequested(string adapterId, bool refresh)

  function focusPage() {
    settingsScroll.forceActiveFocus()
  }

  function loadProfile() {
    if (!activeProfile) return
    nameField.text = activeProfile.name || ""
    iconField.text = activeProfile.icon || ""
    adapterPicker.value = activeProfile.adapterId || "codex"
    modelPicker.value = activeProfile.model || ""
    effortPicker.value = activeProfile.thinkingEffort || null
    customModelField.text = modelPicker.value
    manualModelEntry = false
    instructionsField.text = activeProfile.systemInstructions || ""
    directoryStrategy.value = activeProfile.workingDirectoryStrategy || "home"
    directoryField.text = activeProfile.workingDirectory || ""
    contextField.text = (activeProfile.contextProviders || []).join(", ")
    permissionPicker.value = activeProfile.permissionPolicy || "read-only"
    shortcutField.text = activeProfile.shortcut || ""
    profileUnlimited.checked = activeProfile.historyLimit === null
    profileRetention.text = activeProfile.historyLimit === null
      ? "20" : String(activeProfile.historyLimit || 20)
    privateDefault.checked = Boolean(activeProfile.privateByDefault)
    advancedField.text = (activeProfile.advancedArgs || []).join("\n")
    customExecutable.text = activeProfile.customExecutable || ""
    customArguments.text = (activeProfile.customArgs || []).join("\n")
    customStdin.checked = Boolean(activeProfile.customStdin)
    customReadOnly.text = (activeProfile.customReadOnlyArgs || []).join("\n")
    customOutput.value = activeProfile.customOutput || "plain"
    transportPicker.value = activeProfile.transport || "process"
  }

  function discoverCurrentModels(refresh) {
    if (!visible || !activeProfile) return
    Qt.callLater(function() {
      if (root.visible && root.activeProfile)
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
        label: String(model.label || model.id || ""),
        description: String(model.description || "")
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

  onActiveProfileChanged: {
    loadProfile()
    discoverCurrentModels(false)
  }
  onVisibleChanged: discoverCurrentModels(false)
  onModelOptionsChanged: reconcileEditingEffort()
  onAdapterStatesChanged: reconcileEditingEffort()
  onModelsLoadingChanged: {
    if (!modelsLoading) reconcileEditingEffort()
  }

  ThemedScrollView {
    id: settingsScroll
    anchors.fill: parent

    ColumnLayout {
      width: settingsScroll.availableWidth
      spacing: Style.space(12)

      PanelHero {
        Layout.fillWidth: true
        title: root.activeProfile ? root.activeProfile.name : "Profile"
        meta: root.activeProfile
          ? (String(root.activeProfile.adapterId || "custom") + " · "
              + String(root.activeProfile.permissionPolicy || "read-only"))
          : ""
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily

        iconComponent: Component {
          Text {
            text: root.activeProfile ? (root.activeProfile.icon || "󰚩") : "󰚩"
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
              tooltipText: "Duplicate profile"
              foreground: Color.popups.text
              fontFamily: Style.font.menuFamily
              onClicked: root.duplicateRequested()
            }

            PanelActionButton {
              iconText: "󰆴"
              tooltipText: "Remove profile"
              foreground: Color.popups.text
              hoverColor: Color.urgent
              fontFamily: Style.font.menuFamily
              onClicked: removeDialog.opened = true
            }
          }
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.popups.text
      }

      PanelSectionHeader {
        text: "PROFILE"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
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
            placeholderText: "Profile name"
          }
        }

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
              root.modelDiscoveryRequested(adapterId, false)
            }
          }
        }

        FormField {
          Layout.fillWidth: true
          Layout.preferredWidth: 1
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
      }

      FormField {
        Layout.fillWidth: true
        label: "System instructions"
        ThemedTextArea {
          id: instructionsField
          width: parent.width
          height: Style.space(88)
          placeholderText: "Optional behavior for this profile"
          wrapMode: TextEdit.Wrap
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.popups.text
      }

      PanelSectionHeader {
        text: "WORKSPACE & CONTEXT"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
      }

      GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: Style.spacing.controlGap
        rowSpacing: Style.spacing.controlGap

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
          label: "Shortcut"
          TextField {
            id: shortcutField
            width: parent.width
            foreground: Color.popups.text
            font.family: Style.font.menuFamily
            placeholderText: "SUPER ALT, SPACE"
          }
        }

        FormField {
          Layout.fillWidth: true
          Layout.columnSpan: 2
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

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.popups.text
      }

      PanelSectionHeader {
        text: "PRIVACY & HISTORY"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
      }

      GridLayout {
        Layout.fillWidth: true
        columns: 2
        columnSpacing: Style.spacing.controlGap
        rowSpacing: Style.spacing.controlGap

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
          description: "Ignore a profile-specific limit"
          foreground: Color.popups.text
          fontFamily: Style.font.menuFamily
          onClicked: checked = !checked
        }

        FormField {
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          label: "Profile history limit"
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

        Toggle {
          id: globalUnlimited
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          label: "Unlimited global history"
          description: "Keep conversations until cleared"
          foreground: Color.popups.text
          fontFamily: Style.font.menuFamily
          checked: Boolean(root.profileState && root.profileState.historyLimit === null)
          onClicked: root.historyLimitChanged(checked ? 20 : null)
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        foreground: Color.popups.text
      }

      PanelSectionHeader {
        visible: adapterPicker.value === "custom"
        text: "CUSTOM COMMAND"
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
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

      PanelSeparator {
        Layout.fillWidth: true
        foreground: Color.popups.text
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

      Button {
        Layout.alignment: Qt.AlignRight
        text: "Save profile"
        iconText: "󰆓"
        enabled: Boolean(root.activeProfile) && nameField.text.trim().length > 0
        foreground: Color.popups.text
        fontFamily: Style.font.menuFamily
        bordered: true
        onClicked: root.profilePatchRequested(root.values())
      }
    }
  }

  ConfirmDialog {
    id: removeDialog
    anchors.fill: parent
    message: "Remove this profile? Existing history remains readable."
    confirmText: "Remove"
    background: Color.popups.background
    foreground: Color.popups.text
    scrim: Util.alpha(Color.popups.background, 0.72)
    selectedBackground: Style.selectedFillFor(Color.popups.text, Color.accent)
    selectedText: Style.selectedStateColor(Color.popups.text, Color.accent)
    fontFamily: Style.font.menuFamily
    onCanceled: opened = false
    onConfirmed: {
      opened = false
      root.removeRequested()
    }
  }
}
