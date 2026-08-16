import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property var profileState: null
  property var activeProfile: null
  property string shortcutError: ""
  signal historyLimitChanged(var value)
  signal profilePatchRequested(var values)
  signal duplicateRequested()
  signal removeRequested()

  function loadProfile() {
    if (!activeProfile) return
    nameField.text = activeProfile.name || ""
    iconField.text = activeProfile.icon || ""
    adapterPicker.value = activeProfile.adapterId || "codex"
    modelField.text = activeProfile.model || ""
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

  function values() {
    var historyValue = profileUnlimited.checked ? null : parseInt(profileRetention.text)
    if (historyValue !== null && (!historyValue || historyValue < 1))
      throw new Error("History limit must be positive")
    return {
      name: nameField.text.trim(),
      icon: iconField.text.trim(),
      adapterId: adapterPicker.value,
      model: modelField.text.trim() || null,
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

  color: Style.normalFillFor(Color.menu.text, Color.accent)
  borderSpec: Border.controlSpec("normal", Color.menu.text, Color.accent)
  radius: Style.cornerRadius
  onActiveProfileChanged: loadProfile()

  ThemedScrollView {
    anchors.fill: parent
    anchors.margins: Style.spacing.controlPaddingY
    clip: true

    ColumnLayout {
      width: parent.width
      spacing: Style.spacing.controlGap

      Text {
        Layout.fillWidth: true
        text: "Profile settings"
        color: Color.menu.text
        font.family: Style.font.menuFamily
        font.bold: true
        font.pixelSize: Style.font.title
      }

      TextField {
        id: nameField
        Layout.fillWidth: true
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Name"
      }
      TextField {
        id: iconField
        Layout.fillWidth: true
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Icon"
      }
      Dropdown {
        id: adapterPicker
        Layout.fillWidth: true
        showLabel: false
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        options: ["codex", "claude", "opencode", "grok", "cursor", "pi", "custom"]
        value: "codex"
      }
      Dropdown {
        id: transportPicker
        Layout.fillWidth: true
        showLabel: false
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        options: ["process", "auto", "acp"]
        value: "process"
      }
      TextField {
        id: modelField
        Layout.fillWidth: true
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Model"
      }
      ThemedTextArea {
        id: instructionsField
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(90)
        placeholderText: "System instructions"
        wrapMode: TextEdit.Wrap
      }

      Text {
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        text: "Custom command"
        color: Color.menu.text
        font.family: Style.font.menuFamily
        font.pixelSize: Style.font.subtitle
        font.bold: true
      }
      TextField {
        id: customExecutable
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Executable"
      }
      ThemedTextArea {
        id: customArguments
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        placeholderText: "Arguments, one per line"
      }
      Toggle {
        id: customStdin
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        label: "Send prompt on stdin"
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        onClicked: checked = !checked
      }
      ThemedTextArea {
        id: customReadOnly
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        placeholderText: "Read-only arguments, one per line"
      }
      Dropdown {
        id: customOutput
        Layout.fillWidth: true
        visible: adapterPicker.value === "custom"
        showLabel: false
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        options: ["plain", "jsonl"]
        value: "plain"
      }
      Dropdown {
        id: directoryStrategy
        Layout.fillWidth: true
        showLabel: false
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        options: ["home", "fixed", "active-project"]
        value: "home"
      }
      TextField {
        id: directoryField
        Layout.fillWidth: true
        visible: directoryStrategy.value === "fixed"
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Fixed working directory"
      }
      TextField {
        id: contextField
        Layout.fillWidth: true
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Allowed context (comma separated)"
      }
      Dropdown {
        id: permissionPicker
        Layout.fillWidth: true
        showLabel: false
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        options: ["read-only", "ask"]
        value: "read-only"
      }
      TextField {
        id: shortcutField
        Layout.fillWidth: true
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "SUPER ALT, SPACE"
      }
      Text {
        Layout.fillWidth: true
        visible: root.shortcutError.length > 0
        text: root.shortcutError
        color: Color.urgent
        font.family: Style.font.menuFamily
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        font.pixelSize: Style.font.caption
      }

      Toggle {
        id: profileUnlimited
        Layout.fillWidth: true
        label: "Use global history limit"
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        onClicked: checked = !checked
      }
      TextField {
        id: profileRetention
        Layout.fillWidth: true
        enabled: !profileUnlimited.checked
        foreground: Color.menu.text
        font.family: Style.font.menuFamily
        placeholderText: "Profile history limit"
        validator: IntValidator { bottom: 1 }
      }
      Toggle {
        id: privateDefault
        Layout.fillWidth: true
        label: "Private by default"
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        onClicked: checked = !checked
      }
      ThemedTextArea {
        id: advancedField
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(70)
        placeholderText: "Advanced arguments, one per line"
      }

      Toggle {
        id: globalUnlimited
        Layout.fillWidth: true
        label: "Unlimited global history"
        foreground: Color.menu.text
        fontFamily: Style.font.menuFamily
        checked: root.profileState && root.profileState.historyLimit === null
        onClicked: root.historyLimitChanged(checked ? 20 : null)
      }

      RowLayout {
        Layout.fillWidth: true
        Button {
          Layout.fillWidth: true
          text: "Save"
          enabled: Boolean(root.activeProfile) && nameField.text.trim().length > 0
          foreground: Color.menu.text
          fontFamily: Style.font.menuFamily
          bordered: true
          onClicked: root.profilePatchRequested(root.values())
        }
        Button {
          text: "Duplicate"
          foreground: Color.menu.text
          fontFamily: Style.font.menuFamily
          onClicked: root.duplicateRequested()
        }
        Button {
          text: "Remove"
          foreground: Color.urgent
          fontFamily: Style.font.menuFamily
          onClicked: removeDialog.opened = true
        }
      }
    }
  }

  ConfirmDialog {
    id: removeDialog
    anchors.fill: parent
    message: "Remove this profile? Existing history remains readable."
    confirmText: "Remove"
    background: Color.menu.background
    foreground: Color.menu.text
    scrim: Util.alpha(Color.menu.background, 0.72)
    selectedBackground: Color.menu.selectedBackground
    selectedText: Color.menu.selectedText
    fontFamily: Style.font.menuFamily
    onCanceled: opened = false
    onConfirmed: {
      opened = false
      root.removeRequested()
    }
  }
}
