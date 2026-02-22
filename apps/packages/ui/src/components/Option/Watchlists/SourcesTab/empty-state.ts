export interface SourcesEmptyStateInput {
  groupsCount: number
  sourcesCount: number
  hasActiveFilters: boolean
  groupsLoading: boolean
  sourcesLoading: boolean
}

export const shouldShowUnifiedWatchlistsEmptyState = ({
  groupsCount,
  sourcesCount,
  hasActiveFilters,
  groupsLoading,
  sourcesLoading
}: SourcesEmptyStateInput): boolean =>
  !groupsLoading &&
  !sourcesLoading &&
  !hasActiveFilters &&
  groupsCount === 0 &&
  sourcesCount === 0

export const getSourcesTableEmptyDescription = (
  hasActiveFilters: boolean
): string =>
  hasActiveFilters
    ? "No sources match the current filters"
    : "No sources yet. Add a source or import OPML to begin"
