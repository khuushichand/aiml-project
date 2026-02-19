import type { JobScope, WatchlistJob } from "@/types/watchlists"

export interface SourceUsage {
  id: number
  name: string
}

const extractScopeSourceIds = (scope: JobScope | null | undefined): number[] => {
  if (!scope || !Array.isArray(scope.sources)) return []
  return scope.sources
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    .map((value) => Math.floor(value))
}

export const findActiveSourceUsage = (
  jobs: Pick<WatchlistJob, "id" | "name" | "active" | "scope">[],
  sourceId: number
): SourceUsage[] => (
  jobs
    .filter((job) => job.active)
    .filter((job) => extractScopeSourceIds(job.scope).includes(sourceId))
    .map((job) => ({ id: job.id, name: job.name }))
)

export const mapActiveSourceUsage = (
  jobs: Pick<WatchlistJob, "id" | "name" | "active" | "scope">[],
  sourceIds: number[]
): Map<number, SourceUsage[]> => {
  const usageMap = new Map<number, SourceUsage[]>()
  const sourceIdSet = new Set(sourceIds)

  sourceIds.forEach((sourceId) => usageMap.set(sourceId, []))

  jobs
    .filter((job) => job.active)
    .forEach((job) => {
      const scopedSourceIds = extractScopeSourceIds(job.scope)
      scopedSourceIds.forEach((scopedSourceId) => {
        if (!sourceIdSet.has(scopedSourceId)) return
        const existing = usageMap.get(scopedSourceId) || []
        existing.push({ id: job.id, name: job.name })
        usageMap.set(scopedSourceId, existing)
      })
    })

  return usageMap
}
