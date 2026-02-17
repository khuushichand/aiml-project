const TIMEOUT_HINTS = [
  "timeout",
  "timed out",
  "aborterror",
  "request_aborted",
  "aborted",
  "extension messaging timeout"
]

export const isTimeoutLikeError = (error: unknown): boolean => {
  if (error instanceof Error && error.name === "AbortError") return true

  const message =
    error instanceof Error
      ? `${error.name} ${error.message}`
      : typeof error === "string"
        ? error
        : ""

  const normalized = message.toLowerCase()
  return TIMEOUT_HINTS.some((hint) => normalized.includes(hint))
}
