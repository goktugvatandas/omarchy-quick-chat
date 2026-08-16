function list(value) {
  return Array.isArray(value) ? value : []
}

function text(value) {
  return value === undefined || value === null ? "" : String(value)
}

function profileById(profiles, profileId) {
  var items = list(profiles)
  for (var index = 0; index < items.length; index += 1) {
    if (text(items[index].id) === text(profileId)) return items[index]
  }
  return null
}

function catalogFor(profile, catalogs) {
  if (!profile || !catalogs) return []
  return list(catalogs[text(profile.adapterId)])
}

function normalizedModels(profile, catalogs) {
  var options = [{
    id: "",
    label: "CLI default",
    description: "Use the harness default model"
  }]
  var seen = { "": true }
  var catalog = catalogFor(profile, catalogs)

  for (var index = 0; index < catalog.length; index += 1) {
    var model = catalog[index] || {}
    var identifier = text(model.id)
    if (!identifier || seen[identifier]) continue
    seen[identifier] = true
    options.push({
      id: identifier,
      label: text(model.label) || identifier,
      description: text(model.description)
    })
  }

  var configured = text(profile && profile.model)
  if (configured && !seen[configured]) {
    options.push({
      id: configured,
      label: configured,
      description: "Configured model"
    })
  }
  return options
}

function modelMatches(model, query) {
  var needle = text(query).trim().toLowerCase()
  if (!needle) return true
  return (text(model.label) + " " + text(model.id) + " "
    + text(model.description)).toLowerCase().indexOf(needle) !== -1
}

function buildRows(options) {
  var input = options || {}
  var profiles = list(input.profiles)
  var activeProfileId = text(input.activeProfileId)
  var expandedProfileId = text(input.expandedProfileId)
  var catalogs = input.catalogs || {}
  var loadingAdapters = input.loadingAdapters || {}
  var errors = input.errors || {}
  var query = text(input.query)
  var rows = []

  for (var index = 0; index < profiles.length; index += 1) {
    var profile = profiles[index] || {}
    var profileId = text(profile.id)
    var adapterId = text(profile.adapterId) || "custom"
    var expanded = profileId === expandedProfileId
    rows.push({
      kind: "harness",
      profileId: profileId,
      adapterId: adapterId,
      label: text(profile.name) || profileId,
      icon: text(profile.icon) || "󰚩",
      expanded: expanded,
      selected: profileId === activeProfileId
    })

    if (!expanded) continue

    var models = normalizedModels(profile, catalogs)
    var visibleModels = []
    for (var modelIndex = 0; modelIndex < models.length; modelIndex += 1) {
      if (modelMatches(models[modelIndex], query)) visibleModels.push(models[modelIndex])
    }
    for (var visibleIndex = 0; visibleIndex < visibleModels.length; visibleIndex += 1) {
      var option = visibleModels[visibleIndex]
      rows.push({
        kind: "model",
        profileId: profileId,
        adapterId: adapterId,
        modelId: option.id,
        label: option.label,
        description: option.description,
        selected: profileId === activeProfileId
          && text(profile.model) === option.id
      })
    }

    if (loadingAdapters[adapterId]) {
      rows.push({
        kind: "status",
        profileId: profileId,
        adapterId: adapterId,
        label: "Discovering models…",
        error: false
      })
    } else if (text(errors[adapterId])) {
      rows.push({
        kind: "status",
        profileId: profileId,
        adapterId: adapterId,
        label: text(errors[adapterId]),
        error: true
      })
    } else if (visibleModels.length === 0) {
      rows.push({
        kind: "status",
        profileId: profileId,
        adapterId: adapterId,
        label: query ? "No matching models" : "No models discovered",
        error: false
      })
    }
  }
  return rows
}

function currentSelection(profiles, profileId, catalogs) {
  var profile = profileById(profiles, profileId)
  if (!profile) return {
    profileName: "Choose agent",
    profileIcon: "󰚩",
    modelLabel: ""
  }

  var configured = text(profile.model)
  var models = normalizedModels(profile, catalogs)
  var modelLabel = configured || "CLI default"
  for (var index = 0; index < models.length; index += 1) {
    if (models[index].id === configured) {
      modelLabel = models[index].label
      break
    }
  }
  return {
    profileName: text(profile.name) || text(profile.id),
    profileIcon: text(profile.icon) || "󰚩",
    modelLabel: modelLabel
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    buildRows: buildRows,
    currentSelection: currentSelection,
    normalizedModels: normalizedModels,
    profileById: profileById
  }
}
