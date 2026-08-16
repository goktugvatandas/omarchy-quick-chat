function initialState(conversationId, profileId) {
  return {
    conversationId: conversationId,
    profileId: profileId,
    messages: [],
    running: false,
    activeRequestId: null,
    activeUserIndex: -1,
    error: null,
    sessionId: null,
    status: "idle"
  }
}

function cloneState(state) {
  return Object.assign({}, state, {
    messages: state.messages.map(function(message) {
      return Object.assign({}, message, {
        attempts: message.attempts ? message.attempts.map(function(attempt) {
          return Object.assign({}, attempt)
        }) : undefined
      })
    })
  })
}

function beginRun(state, requestId, prompt, attachments, privateMode) {
  if (state.running) throw new Error("a run is already active")
  var next = cloneState(state)
  var userMessage = {
    role: "user",
    text: prompt,
    attachments: (attachments || []).slice(),
    private: Boolean(privateMode),
    attempts: [{ requestId: requestId, status: "running" }]
  }
  next.messages.push(userMessage)
  next.running = true
  next.activeRequestId = requestId
  next.activeUserIndex = next.messages.length - 1
  next.error = null
  next.status = "starting"
  return next
}

function finishAttempt(state, status) {
  var user = state.messages[state.activeUserIndex]
  if (!user || !user.attempts || !user.attempts.length) return
  user.attempts[user.attempts.length - 1].status = status
}

function reduce(state, event) {
  if (!event || event.requestId !== state.activeRequestId) return state
  var next = cloneState(state)
  var data = event.data || {}

  if (event.type === "status") {
    next.status = data.status || data.message || "working"
  } else if (event.type === "text_delta") {
    var last = next.messages[next.messages.length - 1]
    if (!last || last.role !== "assistant" || last.requestId !== event.requestId) {
      last = { role: "assistant", text: "", requestId: event.requestId }
      next.messages.push(last)
    }
    last.text += data.text || ""
  } else if (event.type === "session") {
    next.sessionId = data.sessionId || null
  } else if (event.type === "complete") {
    finishAttempt(next, data.stopReason || "complete")
    next.running = false
    next.status = data.stopReason || "complete"
  } else if (event.type === "error") {
    finishAttempt(next, "error")
    next.running = false
    next.status = "error"
    next.error = data
  }
  return next
}

function retryRun(state, requestId) {
  if (state.running || state.activeUserIndex < 0) throw new Error("nothing to retry")
  var next = cloneState(state)
  next.messages = next.messages.filter(function(message) {
    return !(message.role === "assistant" && message.requestId === state.activeRequestId)
  })
  var user = next.messages[next.activeUserIndex]
  user.attempts.push({ requestId: requestId, status: "running" })
  next.activeRequestId = requestId
  next.running = true
  next.error = null
  next.status = "starting"
  return next
}

function clearError(state) {
  var next = cloneState(state)
  next.error = null
  return next
}

function loadConversation(state, conversation) {
  if (!conversation || !conversation.id) throw new Error("invalid conversation")
  var next = initialState(conversation.id, conversation.profileId || state.profileId)
  next.messages = (conversation.messages || []).map(function(message) {
    return {
      role: message.role,
      text: message.content || message.text || "",
      attempts: message.role === "user" ? [] : undefined
    }
  })
  var sessions = conversation.cliSessions || {}
  var sessionKeys = Object.keys(sessions)
  next.sessionId = sessions[next.profileId]
    || (sessionKeys.length ? sessions[sessionKeys[0]] : null)
  return next
}

function withFailedRun(prompt, code) {
  var state = beginRun(initialState("conversation-test", "codex"), "request-1", prompt, [], false)
  return reduce(state, {
    type: "error",
    requestId: "request-1",
    data: { code: code, message: code }
  })
}

if (typeof module !== "undefined") {
  module.exports = {
    initialState: initialState,
    beginRun: beginRun,
    reduce: reduce,
    retryRun: retryRun,
    clearError: clearError,
    loadConversation: loadConversation,
    withFailedRun: withFailedRun
  }
}
