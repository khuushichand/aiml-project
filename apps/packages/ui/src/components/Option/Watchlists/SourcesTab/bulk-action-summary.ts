import type { SourceType } from "@/types/watchlists"

export interface SourceSelectionSummary {
  total: number
  active: number
  inactive: number
  byType: Record<SourceType, number>
}

export interface SourceSelectionItem {
  active: boolean
  source_type: SourceType
}

export const summarizeSourceSelection = (
  sources: SourceSelectionItem[]
): SourceSelectionSummary => {
  const summary: SourceSelectionSummary = {
    total: sources.length,
    active: 0,
    inactive: 0,
    byType: { rss: 0, site: 0, forum: 0 }
  }

  sources.forEach((source) => {
    if (source.active) {
      summary.active += 1
    } else {
      summary.inactive += 1
    }
    summary.byType[source.source_type] += 1
  })

  return summary
}

export const countToggleImpact = (
  sources: SourceSelectionItem[],
  targetActive: boolean
): number => sources.filter((source) => source.active !== targetActive).length
