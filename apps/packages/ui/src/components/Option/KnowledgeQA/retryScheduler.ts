export const KNOWLEDGE_QA_RETRY_INTERVAL_MS = 10_000
export const KNOWLEDGE_QA_RETRY_TICK_MS = 1_000

const MIN_RETRY_INTERVAL_MS = 5_000
const MAX_RETRY_INTERVAL_MS = 60_000

export const normalizeRetryIntervalMs = (intervalMs: number): number => {
  if (!Number.isFinite(intervalMs)) {
    return KNOWLEDGE_QA_RETRY_INTERVAL_MS
  }
  return Math.min(
    MAX_RETRY_INTERVAL_MS,
    Math.max(MIN_RETRY_INTERVAL_MS, Math.round(intervalMs))
  )
}

type RetryCountdownParams = {
  lastAttemptAt: number | null
  now?: number
  retryIntervalMs?: number
}

export const getRetryCountdownSeconds = ({
  lastAttemptAt,
  now = Date.now(),
  retryIntervalMs = KNOWLEDGE_QA_RETRY_INTERVAL_MS,
}: RetryCountdownParams): number => {
  const intervalMs = normalizeRetryIntervalMs(retryIntervalMs)

  if (typeof lastAttemptAt !== "number" || !Number.isFinite(lastAttemptAt)) {
    return Math.ceil(intervalMs / 1000)
  }

  const elapsedMs = Math.max(0, now - lastAttemptAt)
  const remainingMs = Math.max(0, intervalMs - elapsedMs)
  return Math.ceil(remainingMs / 1000)
}
