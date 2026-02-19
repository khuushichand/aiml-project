import type { WatchlistSource } from "@/types/watchlists"

export const SOURCE_DELETE_UNDO_WINDOW_SECONDS = 10

export interface RestoreSourcesSummary {
  restored: number
  failed: number
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
