var MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

function relativeLabel(isoTimestamp, nowMs) {
  var parsed = Date.parse(String(isoTimestamp || ""))
  if (isNaN(parsed)) return ""
  var now = typeof nowMs === "number" ? nowMs : Date.now()
  var elapsedMs = now - parsed
  if (elapsedMs < 0) elapsedMs = 0

  var minutes = Math.floor(elapsedMs / 60000)
  if (minutes < 1) return "Just now"
  if (minutes < 60) return minutes + "m ago"

  var hours = Math.floor(minutes / 60)
  if (hours < 24) return hours + "h ago"

  var then = new Date(parsed)
  var reference = new Date(now)
  var startOfDay = function(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  }
  var dayDelta = Math.round((startOfDay(reference) - startOfDay(then)) / 86400000)
  if (dayDelta <= 1) return "Yesterday"
  if (dayDelta < 7) return dayDelta + "d ago"

  var label = MONTHS[then.getMonth()] + " " + then.getDate()
  if (then.getFullYear() !== reference.getFullYear())
    label += ", " + then.getFullYear()
  return label
}

if (typeof module !== "undefined") {
  module.exports = { relativeLabel: relativeLabel }
}
