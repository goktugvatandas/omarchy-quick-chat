function safeMarkdown(value) {
  var text = String(value || "")
  // Markdown images become ordinary links. They keep their alt text and target
  // visible/copyable, but the text engine no longer fetches the target.
  text = text.replace(/!\[/g, "[image: ")
  text = text.replace(
    /\]\(\s*(?:file|data|javascript|qrc|resource):[^)\r\n]*\)/gi,
    "]([blocked link])"
  )
  // Raw HTML is not needed for Quick Chat's Markdown subset. Neutralize every
  // tag or autolink so Qt never interprets provider text as a resource-bearing
  // document element; ordinary Markdown links remain available.
  text = text.replace(/</g, "‹").replace(/>/g, "›")
  return text.slice(0, 256 * 1024 + 128)
}

function isSafeExternalLink(value) {
  var link = String(value || "").trim().toLowerCase()
  return link.startsWith("https://")
    || link.startsWith("http://")
    || link.startsWith("mailto:")
}

function safeMetadata(value) {
  // External Omarchy controls may still use Text.AutoText internally. The
  // Markdown boundary removes images and raw tags; replacing ampersands also
  // prevents an entity from reconstructing an angle bracket in that sink.
  return safeMarkdown(value).replace(/&/g, "＆")
}

if (typeof module !== "undefined") {
  module.exports = {
    safeMarkdown: safeMarkdown,
    safeMetadata: safeMetadata,
    isSafeExternalLink: isSafeExternalLink
  }
}
