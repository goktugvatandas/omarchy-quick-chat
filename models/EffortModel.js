function safeOptions(value) {
  if (!Array.isArray(value)) return []
  var seen = {}
  var result = []
  value.forEach(function(option) {
    if (!option || typeof option.id !== "string"
        || !/^[a-z0-9][a-z0-9._-]{0,31}$/.test(option.id)
        || seen[option.id]) return
    seen[option.id] = true
    result.push({
      id: option.id,
      label: typeof option.label === "string" && option.label
        ? option.label : option.id,
      description: typeof option.description === "string"
        ? option.description : ""
    })
  })
  return result
}

function adapterOptions(adapterId, adapterStates) {
  if (!Array.isArray(adapterStates)) return []
  var adapter = adapterStates.find(function(item) {
    return item && String(item.id || "") === adapterId
  })
  return adapter ? safeOptions(adapter.efforts) : []
}

function choices(profile, adapterStates, catalogs) {
  if (!profile) return []
  var adapterId = String(profile.adapterId || "")
  if (!adapterId) return []
  var catalog = catalogs && Array.isArray(catalogs[adapterId])
    ? catalogs[adapterId] : []
  var configuredModel = profile.model === undefined || profile.model === null
    ? "" : String(profile.model)
  var model = catalog.find(function(option) {
    if (!option) return false
    return configuredModel
      ? String(option.id || "") === configuredModel
      : option.isDefault === true
  })
  if (model && Array.isArray(model.efforts)) return safeOptions(model.efforts)
  return adapterOptions(adapterId, adapterStates)
}

function reconcile(value, availableChoices) {
  if (value === undefined || value === null || value === "")
    return { value: null, reset: false }
  var identifier = String(value)
  var supported = safeOptions(availableChoices).some(function(option) {
    return option.id === identifier
  })
  return supported
    ? { value: identifier, reset: false }
    : { value: null, reset: true }
}

function rows(value, availableChoices) {
  var selected = value === undefined || value === null || value === ""
    ? null : String(value)
  return [{
    id: null,
    label: "Default",
    description: "Use the harness or model default",
    selected: selected === null
  }].concat(safeOptions(availableChoices).map(function(option) {
    return {
      id: option.id,
      label: option.label,
      description: option.description,
      selected: option.id === selected
    }
  }))
}

function label(value, availableChoices) {
  if (value === undefined || value === null || value === "") return "Default"
  var identifier = String(value)
  var option = safeOptions(availableChoices).find(function(item) {
    return item.id === identifier
  })
  return option ? option.label : "Default"
}

if (typeof module !== "undefined") {
  module.exports = {
    choices: choices,
    reconcile: reconcile,
    rows: rows,
    label: label
  }
}
