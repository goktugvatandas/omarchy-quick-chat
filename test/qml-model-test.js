const assert = require("node:assert/strict")
const ChatModel = require("../models/ChatModel.js")
const ProfileModel = require("../models/ProfileModel.js")
const HarnessPickerModel = require("../models/HarnessPickerModel.js")
const EffortModel = require("../models/EffortModel.js")
const TimeModel = require("../models/TimeModel.js")

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
const duplicated = ProfileModel.duplicate(profiles, "work")
assert.equal(duplicated.profiles[1].id, "work-copy")
assert.equal(ProfileModel.duplicate(duplicated, "work").profiles[2].id, "work-copy-2")
assert.throws(() => ProfileModel.remove(profiles, "work", false))

const migratedProfiles = ProfileModel.normalize({
  schemaVersion: 1,
  selectedProfileId: "work",
  historyLimit: 20,
  defaultShortcut: "SUPER ALT, SPACE",
  profiles: [{ id: "work", name: "Work", adapterId: "codex" }]
})
assert.equal(migratedProfiles.schemaVersion, 2)
assert.equal(migratedProfiles.defaultShortcut, "SUPER ALT, SPACE")
assert.equal(migratedProfiles.profiles[0].thinkingEffort, null)
assert.equal(migratedProfiles.uiShortcuts.effort, "Ctrl+.")
assert.equal(
  ProfileModel.setUiShortcut(migratedProfiles, "private", "control+shift+p")
    .uiShortcuts.private,
  "Ctrl+Shift+P"
)
assert.throws(() => ProfileModel.setUiShortcut(migratedProfiles, "model", "Enter"))
assert.throws(() => ProfileModel.setUiShortcut(migratedProfiles, "history", "Ctrl+K"))
const resetShortcuts = ProfileModel.resetUiShortcuts(migratedProfiles)
assert.deepEqual(resetShortcuts.uiShortcuts, ProfileModel.defaultUiShortcuts())
const bulkShortcuts = ProfileModel.setUiShortcuts(migratedProfiles, {
  focusInput: "control+l",
  model: "Ctrl+K",
  effort: "Ctrl+.",
  history: "Ctrl+H",
  settings: "Ctrl+,",
  private: "Ctrl+Shift+P",
  newChat: "Ctrl+N"
})
assert.equal(bulkShortcuts.uiShortcuts.focusInput, "Ctrl+L")
assert.throws(() => ProfileModel.setUiShortcuts(migratedProfiles, {
  focusInput: "Ctrl+L",
  model: "Ctrl+K",
  effort: "Ctrl+.",
  history: "Ctrl+K",
  settings: "Ctrl+,",
  private: "Ctrl+Shift+P",
  newChat: "Ctrl+N"
}))
assert.throws(() => ProfileModel.setUiShortcuts(migratedProfiles, {
  focusInput: "Ctrl+L",
  model: "Ctrl+K",
  effort: "Enter",
  history: "Ctrl+H",
  settings: "Ctrl+,",
  private: "Ctrl+Shift+P",
  newChat: "Ctrl+N"
}))

const pickerProfiles = [
  { id: "codex", name: "Codex", icon: "C", adapterId: "codex", model: "gpt-5.6-sol" },
  { id: "claude", name: "Claude Code", icon: "A", adapterId: "claude", model: null }
]
const pickerCatalogs = {
  codex: [
    { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", description: "Frontier coding" },
    { id: "gpt-5.6-terra", label: "GPT-5.6 Terra" }
  ],
  claude: [{ id: "sonnet", label: "Sonnet" }]
}
const pickerRows = HarnessPickerModel.buildRows({
  profiles: pickerProfiles,
  activeProfileId: "codex",
  expandedProfileId: "codex",
  catalogs: pickerCatalogs,
  query: "",
  loadingAdapters: {},
  errors: {}
})
assert.deepEqual(pickerRows.map(row => row.kind), [
  "harness", "model", "model", "model"
])
assert.equal(pickerRows[1].label, "CLI default")
assert.equal(pickerRows[2].selected, true)
assert.equal(pickerRows[2].profileId, "codex")
assert.equal(pickerRows[2].modelId, "gpt-5.6-sol")

const harnessRows = HarnessPickerModel.buildRows({
  profiles: pickerProfiles,
  activeProfileId: "codex",
  expandedProfileId: "",
  catalogs: pickerCatalogs,
  query: "",
  loadingAdapters: {},
  errors: {}
})
assert.deepEqual(
  harnessRows.map(row => [row.kind, row.profileId]),
  [["harness", "codex"], ["harness", "claude"]]
)

const filteredPickerRows = HarnessPickerModel.buildRows({
  profiles: pickerProfiles,
  activeProfileId: "codex",
  expandedProfileId: "codex",
  catalogs: pickerCatalogs,
  query: "terra",
  loadingAdapters: {},
  errors: {}
})
assert.deepEqual(
  filteredPickerRows.filter(row => row.kind === "model").map(row => row.modelId),
  ["gpt-5.6-terra"]
)

assert.deepEqual(
  HarnessPickerModel.currentSelection(pickerProfiles, "codex", pickerCatalogs),
  { profileName: "Codex", profileIcon: "C", modelLabel: "GPT-5.6 Sol" }
)

const configuredModelRows = HarnessPickerModel.buildRows({
  profiles: [{ id: "custom", name: "Custom", adapterId: "custom", model: "local/model" }],
  activeProfileId: "custom",
  expandedProfileId: "custom",
  catalogs: { custom: [] },
  query: "",
  loadingAdapters: {},
  errors: {}
})
assert.deepEqual(
  configuredModelRows.filter(row => row.kind === "model").map(row => row.modelId),
  ["", "local/model"]
)

const effortProfile = {
  id: "codex",
  adapterId: "codex",
  model: "gpt-5.6-sol",
  thinkingEffort: "high"
}
const effortCatalogs = {
  codex: [{
    id: "gpt-5.6-sol",
    isDefault: true,
    efforts: [
      { id: "low", label: "Low", description: "Faster" },
      { id: "high", label: "High", description: "Deeper" }
    ]
  }]
}
const effortChoices = EffortModel.choices(effortProfile, [], effortCatalogs)
assert.deepEqual(effortChoices.map(item => item.id), ["low", "high"])
assert.deepEqual(
  EffortModel.reconcile("xhigh", effortChoices),
  { value: null, reset: true }
)
assert.deepEqual(
  EffortModel.reconcile("high", effortChoices),
  { value: "high", reset: false }
)
assert.deepEqual(
  EffortModel.rows("high", effortChoices).map(row => row.id),
  [null, "low", "high"]
)
assert.equal(EffortModel.rows("high", effortChoices)[2].selected, true)

const adapterEfforts = [{
  id: "claude",
  efforts: [{ id: "medium", label: "Medium" }]
}]
assert.deepEqual(
  EffortModel.choices(
    { adapterId: "claude", model: null },
    adapterEfforts,
    { claude: [{ id: "sonnet", isDefault: true, efforts: null }] }
  ).map(item => item.id),
  ["medium"]
)
assert.deepEqual(
  EffortModel.choices(
    { adapterId: "claude", model: "sonnet" },
    adapterEfforts,
    { claude: [{ id: "sonnet", efforts: [] }] }
  ),
  []
)
assert.deepEqual(EffortModel.reconcile(null, []), { value: null, reset: false })

assert.equal(ChatModel.statusLabel("idle"), "Ready")
assert.equal(ChatModel.statusLabel("complete"), "Ready")
assert.equal(ChatModel.statusLabel("starting"), "Starting…")
assert.equal(ChatModel.statusLabel("working"), "Thinking…")
assert.equal(ChatModel.statusLabel("canceled"), "Stopped")
assert.equal(ChatModel.statusLabel("error"), "Error")
assert.equal(ChatModel.statusLabel("Starting bridge"), "Starting bridge")
assert.equal(ChatModel.statusLabel(""), "")

const now = Date.parse("2026-08-16T15:30:00+00:00")
assert.equal(TimeModel.relativeLabel("", now), "")
assert.equal(TimeModel.relativeLabel("not a date", now), "")
assert.equal(TimeModel.relativeLabel("2026-08-16T15:29:40+00:00", now), "Just now")
assert.equal(TimeModel.relativeLabel("2026-08-16T15:05:00+00:00", now), "25m ago")
assert.equal(TimeModel.relativeLabel("2026-08-16T10:20:07.299629+00:00", now), "5h ago")
assert.equal(TimeModel.relativeLabel("2026-08-15T09:00:00+00:00", now), "Yesterday")
assert.equal(TimeModel.relativeLabel("2026-08-13T09:00:00+00:00", now), "3d ago")
assert.equal(TimeModel.relativeLabel("2026-08-16T18:00:00+00:00", now), "Just now")
const oldSameYear = TimeModel.relativeLabel("2026-01-05T09:00:00+00:00", now)
assert.ok(/^Jan \d+$/.test(oldSameYear), oldSameYear)
const oldOtherYear = TimeModel.relativeLabel("2025-12-31T09:00:00+00:00", now)
assert.ok(/^Dec \d+, 2025$/.test(oldOtherYear), oldOtherYear)

const loaded = ChatModel.loadConversation(ChatModel.initialState("new", "codex"), {
  id: "saved",
  profileId: "work",
  messages: [{ role: "user", content: "Saved question" }],
  cliSessions: { codex: "session-1" }
})
assert.equal(loaded.conversationId, "saved")
assert.equal(loaded.sessionId, "session-1")

console.log("qml model tests passed")
