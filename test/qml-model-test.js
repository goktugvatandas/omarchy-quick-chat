const assert = require("node:assert/strict")
const ChatModel = require("../models/ChatModel.js")
const ProfileModel = require("../models/ProfileModel.js")

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

const profiles = ProfileModel.normalize({
  historyLimit: 20,
  profiles: [{ id: "work", name: "Work", adapterId: "codex" }]
})
assert.equal(profiles.selectedId, "work")
assert.equal(ProfileModel.setHistoryLimit(profiles, null).historyLimit, null)
assert.throws(() => ProfileModel.setHistoryLimit(profiles, 0))
assert.equal(ProfileModel.update(profiles, {
  profileId: "work", values: { model: "gpt-5" }
}).profiles[0].model, "gpt-5")

const loaded = ChatModel.loadConversation(ChatModel.initialState("new", "codex"), {
  id: "saved",
  profileId: "work",
  messages: [{ role: "user", content: "Saved question" }],
  cliSessions: { codex: "session-1" }
})
assert.equal(loaded.conversationId, "saved")
assert.equal(loaded.sessionId, "session-1")

console.log("qml model tests passed")
