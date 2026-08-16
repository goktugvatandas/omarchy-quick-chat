import Quickshell
import Quickshell.Hyprland
import QtQuick

Item {
  id: root

  required property string profileId
  required property string profileName

  GlobalShortcut {
    appid: "goktugvatandas.quick-chat"
    name: "profile-" + root.profileId
    onPressed: Quickshell.execDetached([
      "omarchy-shell",
      "shell",
      "summon",
      "goktugvatandas.quick-chat",
      JSON.stringify({ profileId: root.profileId })
    ])
  }
}
