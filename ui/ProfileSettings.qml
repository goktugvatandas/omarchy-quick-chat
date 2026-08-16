import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Rectangle {
  id: root

  property var profileState: null
  property var activeProfile: null
  signal historyLimitChanged(var value)
  signal profilePatchRequested(var values)
  signal duplicateRequested()
  signal removeRequested()

  function loadProfile() {
    if (!activeProfile) return
    nameField.text = activeProfile.name || ""
    iconField.text = activeProfile.icon || ""
    adapterPicker.currentIndex = Math.max(0, adapterPicker.model.indexOf(activeProfile.adapterId))
    modelField.text = activeProfile.model || ""
    instructionsField.text = activeProfile.systemInstructions || ""
    directoryStrategy.currentIndex = Math.max(
      0, directoryStrategy.model.indexOf(activeProfile.workingDirectoryStrategy || "home")
    )
    directoryField.text = activeProfile.workingDirectory || ""
    contextField.text = (activeProfile.contextProviders || []).join(", ")
    permissionPicker.currentIndex = activeProfile.permissionPolicy === "ask" ? 1 : 0
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
    customOutput.currentIndex = activeProfile.customOutput === "jsonl" ? 1 : 0
  }

  function values() {
    var historyValue = profileUnlimited.checked ? null : parseInt(profileRetention.text)
    if (historyValue !== null && (!historyValue || historyValue < 1))
      throw new Error("History limit must be positive")
    return {
      name: nameField.text.trim(),
      icon: iconField.text.trim(),
      adapterId: adapterPicker.currentText,
      model: modelField.text.trim() || null,
      systemInstructions: instructionsField.text,
      workingDirectoryStrategy: directoryStrategy.currentText,
      workingDirectory: directoryField.text.trim() || null,
      contextProviders: contextField.text.split(",").map(function(value) {
        return value.trim()
      }).filter(Boolean),
      permissionPolicy: permissionPicker.currentText,
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
      customOutput: customOutput.currentText
    }
  }

  color: Qt.rgba(1, 1, 1, 0.025)
  radius: Style.cornerRadius
  onActiveProfileChanged: loadProfile()

  ScrollView {
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
        font.bold: true
        font.pixelSize: Style.font.title
      }

      TextField { id: nameField; Layout.fillWidth: true; placeholderText: "Name" }
      TextField { id: iconField; Layout.fillWidth: true; placeholderText: "Icon" }
      ComboBox {
        id: adapterPicker
        Layout.fillWidth: true
        model: ["codex", "claude", "opencode", "grok", "cursor", "pi", "custom"]
      }
      TextField { id: modelField; Layout.fillWidth: true; placeholderText: "Model" }
      TextArea {
        id: instructionsField
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(90)
        placeholderText: "System instructions"
        wrapMode: TextEdit.Wrap
      }

      Text {
        Layout.fillWidth: true
        visible: adapterPicker.currentText === "custom"
        text: "Custom command"
        color: Color.menu.text
        font.bold: true
      }
      TextField {
        id: customExecutable
        Layout.fillWidth: true
        visible: adapterPicker.currentText === "custom"
        placeholderText: "Executable"
      }
      TextArea {
        id: customArguments
        Layout.fillWidth: true
        visible: adapterPicker.currentText === "custom"
        placeholderText: "Arguments, one per line"
      }
      CheckBox {
        id: customStdin
        visible: adapterPicker.currentText === "custom"
        text: "Send prompt on stdin"
      }
      TextArea {
        id: customReadOnly
        Layout.fillWidth: true
        visible: adapterPicker.currentText === "custom"
        placeholderText: "Read-only arguments, one per line"
      }
      ComboBox {
        id: customOutput
        Layout.fillWidth: true
        visible: adapterPicker.currentText === "custom"
        model: ["plain", "jsonl"]
      }
      ComboBox {
        id: directoryStrategy
        Layout.fillWidth: true
        model: ["home", "fixed", "active-project"]
      }
      TextField {
        id: directoryField
        Layout.fillWidth: true
        visible: directoryStrategy.currentText === "fixed"
        placeholderText: "Fixed working directory"
      }
      TextField {
        id: contextField
        Layout.fillWidth: true
        placeholderText: "Allowed context (comma separated)"
      }
      ComboBox {
        id: permissionPicker
        Layout.fillWidth: true
        model: ["read-only", "ask"]
      }
      TextField {
        id: shortcutField
        Layout.fillWidth: true
        placeholderText: "SUPER ALT, SPACE"
      }

      CheckBox { id: profileUnlimited; text: "Unlimited profile history" }
      TextField {
        id: profileRetention
        Layout.fillWidth: true
        enabled: !profileUnlimited.checked
        placeholderText: "Profile history limit"
        validator: IntValidator { bottom: 1 }
      }
      CheckBox { id: privateDefault; text: "Private by default" }
      TextArea {
        id: advancedField
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(70)
        placeholderText: "Advanced arguments, one per line"
      }

      CheckBox {
        id: globalUnlimited
        text: "Unlimited global history"
        checked: root.profileState && root.profileState.historyLimit === null
        onToggled: root.historyLimitChanged(checked ? null : 20)
      }

      RowLayout {
        Layout.fillWidth: true
        Button {
          Layout.fillWidth: true
          text: "Save"
          enabled: Boolean(root.activeProfile) && nameField.text.trim().length > 0
          onClicked: root.profilePatchRequested(root.values())
        }
        Button { text: "Duplicate"; onClicked: root.duplicateRequested() }
        Button { text: "Remove"; onClicked: removeDialog.opened = true }
      }
    }
  }

  ConfirmDialog {
    id: removeDialog
    anchors.fill: parent
    message: "Remove this profile? Existing history remains readable."
    confirmText: "Remove"
    onCanceled: opened = false
    onConfirmed: {
      opened = false
      root.removeRequested()
    }
  }
}
