function copy(value) {
  return JSON.parse(JSON.stringify(value))
}

function normalize(config) {
  if (!config || !Array.isArray(config.profiles) || config.profiles.length === 0)
    throw new Error("at least one profile is required")
  var selectedId = config.selectedProfileId || config.profiles[0].id
  if (!config.profiles.some(function(profile) { return profile.id === selectedId }))
    selectedId = config.profiles[0].id
  var historyLimit = config.historyLimit === undefined ? 20 : config.historyLimit
  if (historyLimit !== null && (!Number.isInteger(historyLimit) || historyLimit <= 0))
    throw new Error("history limit must be positive or unlimited")
  return {
    schemaVersion: config.schemaVersion || 1,
    selectedId: selectedId,
    historyLimit: historyLimit,
    defaultShortcut: config.defaultShortcut || "SUPER ALT, SPACE",
    profiles: copy(config.profiles)
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
    schemaVersion: state.schemaVersion || 1,
    selectedProfileId: state.selectedId,
    historyLimit: state.historyLimit,
    defaultShortcut: state.defaultShortcut,
    profiles: copy(state.profiles)
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    normalize: normalize,
    defaults: defaults,
    setHistoryLimit: setHistoryLimit,
    update: update,
    duplicate: duplicate,
    remove: remove,
    serialize: serialize
  }
}
