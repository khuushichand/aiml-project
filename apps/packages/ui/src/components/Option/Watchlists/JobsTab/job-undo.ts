import type { WatchlistJob } from "@/types/watchlists"

export const JOB_DELETE_UNDO_WINDOW_SECONDS = 10

const toPositiveWindowSeconds = (value: unknown): number | null => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  const normalized = Math.floor(parsed)
  return normalized > 0 ? normalized : null
}

export const resolveJobUndoWindowSeconds = (
  value: unknown,
  fallback = JOB_DELETE_UNDO_WINDOW_SECONDS
): number => {
  const resolved = toPositiveWindowSeconds(value)
  if (resolved != null) return resolved

  const fallbackSeconds = toPositiveWindowSeconds(fallback)
  return fallbackSeconds ?? JOB_DELETE_UNDO_WINDOW_SECONDS
}

export const toJobRestoreId = (job: WatchlistJob): number => job.id
