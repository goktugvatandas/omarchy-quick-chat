function copy(value) {
  return JSON.parse(JSON.stringify(value))
}

var UI_SHORTCUT_ACTIONS = [
  "focusInput", "model", "effort", "history", "settings", "private", "newChat"
]
var DEFAULT_UI_SHORTCUTS = {
  focusInput: "Ctrl+L",
  model: "Ctrl+K",
  effort: "Ctrl+.",
  history: "Ctrl+H",
  settings: "Ctrl+,",
  private: "Ctrl+Shift+P",
  newChat: "Ctrl+N"
}
var RESERVED_UI_SHORTCUTS = {
  Enter: true,
  "Ctrl+Enter": true,
  Escape: true,
  "Alt+Left": true,
  Tab: true,
  "Shift+Tab": true
}
var MODIFIER_ALIASES = {
  alt: "Alt",
  cmd: "Meta",
  command: "Meta",
  control: "Ctrl",
  ctrl: "Ctrl",
  meta: "Meta",
  shift: "Shift",
  super: "Meta",
  win: "Meta"
}
var MODIFIER_ORDER = ["Ctrl", "Alt", "Shift", "Meta"]
var NAMED_KEYS = {
  backspace: "Backspace",
  delete: "Delete",
  down: "Down",
  end: "End",
  enter: "Enter",
  escape: "Escape",
  esc: "Escape",
  home: "Home",
  insert: "Insert",
  left: "Left",
  pagedown: "PageDown",
  pageup: "PageUp",
  return: "Enter",
  right: "Right",
  space: "Space",
  tab: "Tab",
  up: "Up"
}

function canonicalizeShortcut(value) {
  if (typeof value !== "string" || !value.trim())
    throw new Error("shortcut must be a non-empty string")
  var tokens = value.split("+").map(function(token) { return token.trim() })
  if (tokens.some(function(token) { return !token }))
    throw new Error("shortcut contains an empty key")
  var modifiers = {}
  var keys = []
  tokens.forEach(function(token) {
    var modifier = MODIFIER_ALIASES[token.toLowerCase()]
    if (modifier) {
      if (modifiers[modifier]) throw new Error("shortcut repeats a modifier")
      modifiers[modifier] = true
    } else {
      keys.push(token)
    }
  })
  if (keys.length !== 1)
    throw new Error("shortcut must contain exactly one non-modifier key")
  var rawKey = keys[0]
  var lowered = rawKey.toLowerCase()
  var key = NAMED_KEYS[lowered]
  if (!key && /^f(?:[1-9]|1[0-9]|2[0-4])$/.test(lowered))
    key = lowered.toUpperCase()
  if (!key && rawKey.length === 1 && !/\s/.test(rawKey))
    key = /[a-z]/i.test(rawKey) ? rawKey.toUpperCase() : rawKey
  if (!key) throw new Error("shortcut key is not supported")
  return MODIFIER_ORDER.filter(function(modifier) { return modifiers[modifier] })
    .concat([key]).join("+")
}

function normalizeShortcuts(value) {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("uiShortcuts must be an object")
  var keys = Object.keys(value).sort()
  var required = UI_SHORTCUT_ACTIONS.slice().sort()
  if (JSON.stringify(keys) !== JSON.stringify(required))
    throw new Error("uiShortcuts must contain every Quick Chat action")
  var result = {}
  var seen = {}
  UI_SHORTCUT_ACTIONS.forEach(function(action) {
    var shortcut = canonicalizeShortcut(value[action])
    if (RESERVED_UI_SHORTCUTS[shortcut])
      throw new Error(shortcut + " is reserved for Quick Chat navigation")
    if (seen[shortcut]) throw new Error("duplicate Quick Chat shortcut: " + shortcut)
    seen[shortcut] = true
    result[action] = shortcut
  })
  return result
}

function normalizeEffort(value) {
  if (value === undefined || value === null) return null
  if (typeof value !== "string" || !/^[a-z0-9][a-z0-9._-]{0,31}$/.test(value))
    throw new Error("thinking effort has an invalid format")
  return value
}

function normalize(config) {
  if (!config || !Array.isArray(config.profiles) || config.profiles.length === 0)
    throw new Error("at least one profile is required")
  var sourceVersion = config.schemaVersion === undefined ? 1 : config.schemaVersion
  if (sourceVersion !== 1 && sourceVersion !== 2)
    throw new Error("unsupported config schema version")
  var selectedId = config.selectedProfileId || config.profiles[0].id
  if (!config.profiles.some(function(profile) { return profile.id === selectedId }))
    selectedId = config.profiles[0].id
  var historyLimit = config.historyLimit === undefined ? 20 : config.historyLimit
  if (historyLimit !== null && (!Number.isInteger(historyLimit) || historyLimit <= 0))
    throw new Error("history limit must be positive or unlimited")
  var profiles = copy(config.profiles).map(function(profile) {
    profile.thinkingEffort = normalizeEffort(profile.thinkingEffort)
    return profile
  })
  return {
    schemaVersion: 2,
    selectedId: selectedId,
    historyLimit: historyLimit,
    defaultShortcut: config.defaultShortcut
      || (sourceVersion === 1 ? "SUPER ALT, SPACE" : "SUPER ALT, C"),
    uiShortcuts: normalizeShortcuts(
      sourceVersion === 1 || config.uiShortcuts === undefined
        ? DEFAULT_UI_SHORTCUTS : config.uiShortcuts
    ),
    profiles: profiles
  }
}

function defaults(config) {
  return normalize(config)
}

function setHistoryLimit(state, value) {
  if (value !== null && (!Number.isInteger(value) || value <= 0))
    throw new Error("history limit must be positive or unlimited")
  var next = copy(state)
  next.historyLimit = value
  return next
}

function setUiShortcut(state, action, value) {
  if (UI_SHORTCUT_ACTIONS.indexOf(action) === -1)
    throw new Error("unknown Quick Chat shortcut action")
  var next = copy(state)
  var candidate = copy(next.uiShortcuts)
  candidate[action] = value
  next.uiShortcuts = normalizeShortcuts(candidate)
  return next
}

function update(state, patch) {
  if (!patch || !patch.profileId || !patch.values) throw new Error("invalid profile patch")
  var next = copy(state)
  var found = false
  next.profiles = next.profiles.map(function(profile) {
    if (profile.id !== patch.profileId) return profile
    found = true
    return Object.assign({}, profile, patch.values)
  })
  if (!found) throw new Error("profile not found")
  return next
}

function duplicate(state, profileId) {
  var source = state.profiles.find(function(profile) { return profile.id === profileId })
  if (!source) throw new Error("profile not found")
  var base = profileId + "-copy"
  var candidate = base
  var suffix = 2
  while (state.profiles.some(function(profile) { return profile.id === candidate })) {
    candidate = base + "-" + suffix
    suffix += 1
  }
  var next = copy(state)
  var duplicated = Object.assign({}, copy(source), {
    id: candidate,
    name: source.name + " Copy",
    shortcut: null
  })
  next.profiles.push(duplicated)
  return next
}

function remove(state, profileId, confirmed) {
  if (!confirmed) throw new Error("profile removal requires confirmation")
  if (state.profiles.length <= 1) throw new Error("at least one profile is required")
  var next = copy(state)
  next.profiles = next.profiles.filter(function(profile) { return profile.id !== profileId })
  if (next.profiles.length === state.profiles.length) throw new Error("profile not found")
  if (next.selectedId === profileId) next.selectedId = next.profiles[0].id
  return next
}

function serialize(state) {
  return {
    schemaVersion: 2,
    selectedProfileId: state.selectedId,
    historyLimit: state.historyLimit,
    defaultShortcut: state.defaultShortcut,
    uiShortcuts: normalizeShortcuts(state.uiShortcuts),
    profiles: copy(state.profiles)
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    normalize: normalize,
    defaults: defaults,
    setHistoryLimit: setHistoryLimit,
    setUiShortcut: setUiShortcut,
    update: update,
    duplicate: duplicate,
    remove: remove,
    serialize: serialize
  }
}
