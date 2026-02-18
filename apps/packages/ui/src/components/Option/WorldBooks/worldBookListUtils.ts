import dayjs from "dayjs"
import relativeTime from "dayjs/plugin/relativeTime"

dayjs.extend(relativeTime)

export const UNKNOWN_LAST_MODIFIED_LABEL = "Unknown"

const SECONDS_TO_MS = 1000
const SECOND_TIMESTAMP_CUTOFF = 1_000_000_000_000

export const parseWorldBookTimestamp = (value: unknown): number | null => {
  if (value == null) return null
  if (value instanceof Date) {
    const ts = value.getTime()
    return Number.isFinite(ts) ? ts : null
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value < SECOND_TIMESTAMP_CUTOFF ? value * SECONDS_TO_MS : value
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Date.parse(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const formatUtcTimestamp = (timestamp: number): string =>
  new Date(timestamp)
    .toISOString()
    .replace(/\.\d{3}Z$/, " UTC")
    .replace("T", " ")

export const formatWorldBookLastModified = (
  value: unknown,
  options?: { nowMs?: number }
): { relative: string; absolute: string | null; timestamp: number | null } => {
  const timestamp = parseWorldBookTimestamp(value)
  if (!timestamp) {
    return {
      relative: UNKNOWN_LAST_MODIFIED_LABEL,
      absolute: null,
      timestamp: null
    }
  }

  const nowMs =
    typeof options?.nowMs === "number" && Number.isFinite(options.nowMs)
      ? options.nowMs
      : Date.now()

  return {
    relative: dayjs(timestamp).from(dayjs(nowMs)),
    absolute: formatUtcTimestamp(timestamp),
    timestamp
  }
}
