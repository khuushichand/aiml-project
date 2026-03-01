import type { WatchlistSource } from "@/types/watchlists"

export const SOURCE_DELETE_UNDO_WINDOW_SECONDS = 10

export interface RestoreSourcesSummary {
  restored: number
  failed: number
}

export interface SourceDeleteUndoWindowPayload {
  restore_window_seconds?: number | string | null
}

export interface SourceUndoWindowResolution {
  seconds: number
  hasMixedWindows: boolean
}

const toPositiveWindowSeconds = (value: unknown): number | null => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  const normalized = Math.floor(parsed)
  return normalized > 0 ? normalized : null
}

export const resolveSourceUndoWindowSeconds = (
  value: unknown,
  fallback = SOURCE_DELETE_UNDO_WINDOW_SECONDS
): number => {
  const resolved = toPositiveWindowSeconds(value)
  if (resolved != null) return resolved

  const fallbackSeconds = toPositiveWindowSeconds(fallback)
  return fallbackSeconds ?? SOURCE_DELETE_UNDO_WINDOW_SECONDS
}

export const resolveBulkSourceUndoWindow = (
  payloads: Array<SourceDeleteUndoWindowPayload | null | undefined>,
  fallback = SOURCE_DELETE_UNDO_WINDOW_SECONDS
): SourceUndoWindowResolution => {
  const windows = payloads
    .map((payload) => toPositiveWindowSeconds(payload?.restore_window_seconds))
    .filter((value): value is number => value != null)

  if (windows.length === 0) {
    return {
      seconds: resolveSourceUndoWindowSeconds(null, fallback),
      hasMixedWindows: false
    }
  }

  return {
    seconds: Math.min(...windows),
    hasMixedWindows: new Set(windows).size > 1
  }
}

export const toSourceRestoreId = (source: WatchlistSource): number => source.id

export const restoreDeletedSources = async (
  deletedSources: WatchlistSource[],
  restore: (sourceId: number) => Promise<unknown>
): Promise<RestoreSourcesSummary> => {
  if (deletedSources.length === 0) {
    return { restored: 0, failed: 0 }
  }

  const results = await Promise.allSettled(
    deletedSources.map((source) => restore(toSourceRestoreId(source)))
  )

  return results.reduce<RestoreSourcesSummary>(
    (acc, result) => {
      if (result.status === "fulfilled") {
        acc.restored += 1
      } else {
        acc.failed += 1
      }
      return acc
    },
    { restored: 0, failed: 0 }
  )
}
