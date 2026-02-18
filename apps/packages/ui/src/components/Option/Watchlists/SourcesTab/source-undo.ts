import type { WatchlistSource, WatchlistSourceCreate } from "@/types/watchlists"

export const SOURCE_DELETE_UNDO_WINDOW_SECONDS = 10

export interface RestoreSourcesSummary {
  restored: number
  failed: number
}

export const toSourceCreatePayload = (
  source: WatchlistSource
): WatchlistSourceCreate => ({
  name: source.name,
  url: source.url,
  source_type: source.source_type,
  active: source.active,
  tags: Array.isArray(source.tags) ? [...source.tags] : [],
  settings: source.settings ?? undefined
})

export const restoreDeletedSources = async (
  deletedSources: WatchlistSource[],
  restore: (payload: WatchlistSourceCreate) => Promise<unknown>
): Promise<RestoreSourcesSummary> => {
  if (deletedSources.length === 0) {
    return { restored: 0, failed: 0 }
  }

  const results = await Promise.allSettled(
    deletedSources.map((source) => restore(toSourceCreatePayload(source)))
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
