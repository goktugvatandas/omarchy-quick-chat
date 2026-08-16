import Quickshell
import Quickshell.Io
import QtQuick

Item {
  id: root

  property var manifest: null
  property bool ready: false
  property bool stopping: false
  property int restartCount: 0
  property var pendingMessages: []
  property string diagnostic: ""
  readonly property string bridgePath: manifest && manifest.__sourceDir
    ? manifest.__sourceDir + "/bridge/quick-chat-bridge"
    : ""

  signal eventReceived(var event)
  signal bridgeFailed(string message)

  function start() {
    if (!bridgePath || bridgeProcess.running) return
    stopping = false
    bridgeProcess.command = [bridgePath]
    bridgeProcess.running = true
  }

  function stop() {
    stopping = true
    bridgeProcess.running = false
  }

  function send(object) {
    if (!object) return
    if (!ready) {
      pendingMessages = pendingMessages.concat([object])
      start()
      return
    }
    bridgeProcess.write(JSON.stringify(object) + "\n")
  }

  function handleLine(line) {
    var event
    try {
      event = JSON.parse(line)
    } catch (error) {
      bridgeFailed("The bridge returned malformed JSON.")
      return
    }
    if (event.type === "ready") {
      ready = true
      restartCount = 0
      var queued = pendingMessages
      pendingMessages = []
      for (var index = 0; index < queued.length; index += 1)
        bridgeProcess.write(JSON.stringify(queued[index]) + "\n")
    }
    eventReceived(event)
  }

  Process {
    id: bridgeProcess
    stdinEnabled: true

    stdout: SplitParser {
      onRead: function(line) { root.handleLine(line) }
    }

    stderr: SplitParser {
      onRead: function(line) {
        if (root.diagnostic.length < 16384)
          root.diagnostic += line + "\n"
      }
    }

    onExited: function(exitCode, exitStatus) {
      root.ready = false
      if (!root.stopping && root.restartCount < 1) {
        root.restartCount += 1
        restartTimer.restart()
      } else if (!root.stopping) {
        root.bridgeFailed("Quick Chat bridge exited unexpectedly (" + exitCode + ").")
      }
    }
  }

  Timer {
    id: restartTimer
    interval: 250
    onTriggered: root.start()
  }

  Component.onCompleted: start()
  Component.onDestruction: stop()
}
