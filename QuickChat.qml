import QtQuick

Item {
  id: root

  property string omarchyPath: ""
  property var shell: null
  property var manifest: ({})
  property var pluginRegistry: null
  property string openingPayload: "{}"

  visible: false

  function open(payloadJson) {
    openingPayload = payloadJson || "{}"
    visible = true
  }

  function close() {
    visible = false
  }
}
