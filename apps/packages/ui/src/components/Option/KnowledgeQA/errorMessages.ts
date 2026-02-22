const toErrorString = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === "string") return error
  return ""
}

const isConnectionError = (message: string): boolean =>
  /network|offline|failed to fetch|connection|unreachable/i.test(message)

const isTimeoutError = (message: string): boolean =>
  /timeout|timed out|etimedout/i.test(message)

export const mapKnowledgeQaSearchErrorMessage = (
  error: unknown,
  fallback: string = "Search failed"
): string => {
  const message = toErrorString(error)
  if (!message) return fallback
  if (isTimeoutError(message)) {
    return "Search timed out. Try the Fast preset or reduce sources."
  }
  if (isConnectionError(message)) {
    return "Cannot reach server. Check your connection and try again."
  }
  if (/no results|no relevant/i.test(message)) {
    return "No relevant documents found. Try broadening your query."
  }
  return message
}

export const mapKnowledgeQaExportErrorMessage = (
  error: unknown,
  fallback: string = "Chatbook export failed. Please try again."
): string => {
  const message = toErrorString(error)
  if (!message) return fallback
  if (isConnectionError(message)) {
    return "Chatbook export failed. Cannot reach server."
  }
  if (isTimeoutError(message)) {
    return "Chatbook export timed out. Please retry in a moment."
  }
  if (/404|not found|thread/i.test(message)) {
    return "Chatbook export failed. Thread was not found."
  }
  if (/401|unauthorized/i.test(message)) {
    return "Chatbook export failed. You are not authorized to export this thread."
  }
  if (/403|forbidden/i.test(message)) {
    return "Chatbook export failed. You do not have permission to export this thread."
  }
  if (/400|422|unprocessable|validation|required field|invalid request|invalid payload/i.test(message)) {
    return "Chatbook export failed. Export request is invalid. Check the selected thread and try again."
  }
  if (/429|rate limit|too many/i.test(message)) {
    return "Chatbook export failed. Too many export requests. Please wait and try again."
  }
  if (/5\d\d|server error|internal server/i.test(message)) {
    return "Chatbook export failed due to a server error. Please try again."
  }
  return `Chatbook export failed. ${message}`
}
