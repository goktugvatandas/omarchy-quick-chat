function parse(value) {
  try {
    var payload = JSON.parse(String(value || "{}"))
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return {}
    return payload
  } catch (error) {
    return {}
  }
}

if (typeof module !== "undefined") {
  module.exports = { parse: parse }
}
