const assert = require("node:assert/strict")
const ChatModel = require("../models/ChatModel.js")

const state = ChatModel.initialState("conv-1", "codex")
const started = ChatModel.beginRun(state, "req-1", "Say hello", [], false)
const streamed = ChatModel.reduce(started, {
  type: "text_delta", requestId: "req-1", data: { text: "Hello" }
})
assert.equal(streamed.messages.at(-1).role, "assistant")
assert.equal(streamed.messages.at(-1).text, "Hello")
assert.equal(streamed.running, true)

const continued = ChatModel.reduce(streamed, {
  type: "text_delta", requestId: "req-1", data: { text: " world" }
})
assert.equal(continued.messages.at(-1).text, "Hello world")
assert.equal(
  ChatModel.reduce(continued, {
    type: "complete", requestId: "req-1", data: {}
  }).running,
  false
)

const ignored = ChatModel.reduce(started, {
  type: "text_delta", requestId: "another", data: { text: "wrong" }
})
assert.deepEqual(ignored, started)

const failed = ChatModel.reduce(started, {
  type: "error", requestId: "req-1", data: { message: "failed" }
})
const retried = ChatModel.retryRun(failed, "req-2")
assert.equal(retried.messages.filter(message => message.role === "user").length, 1)
assert.equal(retried.messages[0].attempts.length, 2)
assert.equal(ChatModel.clearError(failed).error, null)

console.log("qml model tests passed")
