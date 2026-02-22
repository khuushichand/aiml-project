import { describe, expect, it } from "vitest"
import {
  getSourcesTableEmptyDescription,
  shouldShowUnifiedWatchlistsEmptyState
} from "../empty-state"

describe("watchlists sources empty-state helpers", () => {
  it("shows unified empty state only on first-use with no filters", () => {
    expect(
      shouldShowUnifiedWatchlistsEmptyState({
        groupsCount: 0,
        sourcesCount: 0,
        hasActiveFilters: false,
        groupsLoading: false,
        sourcesLoading: false
      })
    ).toBe(true)
  })

  it("does not show unified empty state while loading or when filters are active", () => {
    expect(
      shouldShowUnifiedWatchlistsEmptyState({
        groupsCount: 0,
        sourcesCount: 0,
        hasActiveFilters: true,
        groupsLoading: false,
        sourcesLoading: false
      })
    ).toBe(false)

    expect(
      shouldShowUnifiedWatchlistsEmptyState({
        groupsCount: 0,
        sourcesCount: 0,
        hasActiveFilters: false,
        groupsLoading: true,
        sourcesLoading: false
      })
    ).toBe(false)
  })

  it("provides contextual table-empty descriptions", () => {
    expect(getSourcesTableEmptyDescription(true)).toBe(
      "No sources match the current filters"
    )
    expect(getSourcesTableEmptyDescription(false)).toBe(
      "No sources yet. Add a source or import OPML to begin"
    )
  })
})
