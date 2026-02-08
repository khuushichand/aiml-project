import React from "react"
import { Spin } from "antd"
import { useTranslation } from "react-i18next"
import type { RagPinnedResult } from "@/utils/rag-format"
import type { RagResult, SortMode } from "../hooks"
import type { FileSearchMediaType } from "../hooks/useFileSearch"
import { SearchInput } from "../SearchTab/SearchInput"
import { SearchEmptyState } from "../SearchTab/SearchEmptyState"
import { FileSearchFilters } from "./FileSearchFilters"
import { FileResultItem } from "./FileResultItem"

type FileSearchTabProps = {
  // Query state
  query: string
  onQueryChange: (query: string) => void
  useCurrentMessage: boolean
  onUseCurrentMessageChange: (value: boolean) => void

  // Search execution
  onSearch: () => void
  loading: boolean
  queryError: string | null

  // Results
  results: RagResult[]
  sortMode: SortMode
  onSortModeChange: (mode: SortMode) => void
  sortResults: (results: RagResult[]) => RagResult[]
  hasAttemptedSearch: boolean
  timedOut: boolean

  // Filters
  mediaTypes: FileSearchMediaType[]
  onMediaTypesChange: (types: FileSearchMediaType[]) => void

  // Attached tracking
  attachedMediaIds: Set<number>

  // Pinned results
  pinnedResults: RagPinnedResult[]
  onPin: (result: RagResult) => void

  // Result actions
  onAttach: (result: RagResult) => void
  onPreview: (result: RagResult) => void
  onOpen: (result: RagResult) => void

  // Connection state
  isConnected?: boolean
  autoFocus?: boolean
  onOpenContext?: () => void
}

/**
 * File Search tab — search the media library for documents to attach.
 * Reuses SearchInput and SearchEmptyState from the original SearchTab.
 */
export const FileSearchTab: React.FC<FileSearchTabProps> = ({
  query,
  onQueryChange,
  useCurrentMessage,
  onUseCurrentMessageChange,
  onSearch,
  loading,
  queryError,
  results,
  sortMode,
  onSortModeChange,
  sortResults,
  hasAttemptedSearch,
  timedOut,
  mediaTypes,
  onMediaTypesChange,
  attachedMediaIds,
  pinnedResults,
  onPin,
  onAttach,
  onPreview,
  onOpen,
  isConnected = true,
  autoFocus = false,
  onOpenContext
}) => {
  const { t } = useTranslation(["sidepanel"])

  const sortedResults = React.useMemo(
    () => sortResults(results),
    [results, sortResults]
  )

  const statusAnnouncement = React.useMemo(() => {
    if (loading) return t("sidepanel:rag.searching", "Searching...")
    if (!hasAttemptedSearch) return ""
    if (timedOut) return t("sidepanel:rag.searchTimedOut", "Search timed out")
    if (results.length === 0)
      return t("sidepanel:rag.noResultsFound", "No results found")
    return t("sidepanel:rag.resultsFound", "{{count}} results found", {
      count: results.length
    })
  }, [loading, hasAttemptedSearch, timedOut, results.length, t])

  return (
    <div
      className="flex flex-col gap-4 p-3"
      role="tabpanel"
      id="knowledge-tabpanel-file-search"
      aria-labelledby="knowledge-tab-file-search"
    >
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusAnnouncement}
      </div>

      <SearchInput
        query={query}
        onQueryChange={onQueryChange}
        useCurrentMessage={useCurrentMessage}
        onUseCurrentMessageChange={onUseCurrentMessageChange}
        onSearch={onSearch}
        loading={loading}
        error={queryError}
        autoFocus={autoFocus}
        disabled={!isConnected}
      />

      <FileSearchFilters
        mediaTypes={mediaTypes}
        onMediaTypesChange={onMediaTypesChange}
        sortMode={sortMode}
        onSortModeChange={onSortModeChange}
        disabled={!isConnected}
      />

      {/* Results */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Spin size="default" />
          <span className="ml-2 text-sm text-text-muted">
            {t("sidepanel:rag.searching", "Searching...")}
          </span>
        </div>
      )}

      {!loading && timedOut && (
        <SearchEmptyState variant="timeout" onRetry={onSearch} />
      )}

      {!loading &&
        !timedOut &&
        hasAttemptedSearch &&
        sortedResults.length === 0 && (
          <SearchEmptyState variant="no-results" />
        )}

      {!loading && !timedOut && !hasAttemptedSearch && (
        <SearchEmptyState variant="initial" />
      )}

      {!loading && !timedOut && sortedResults.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text">
              {t("sidepanel:rag.resultsCount", "Results ({{count}})", {
                count: sortedResults.length
              })}
            </span>
          </div>
          <div
            className="flex flex-col gap-2 max-h-[400px] overflow-y-auto"
            role="list"
            aria-label={t(
              "sidepanel:fileSearch.resultsList",
              "File search results"
            )}
          >
            {sortedResults.map((result, idx) => (
              <div key={`file-${idx}`} role="listitem">
                <FileResultItem
                  result={result}
                  query={query}
                  onAttach={onAttach}
                  onPreview={onPreview}
                  onOpen={onOpen}
                  onPin={onPin}
                  isAttached={attachedMediaIds.has(
                    (result.metadata as Record<string, unknown>)
                      ?.media_id as number
                  )}
                  isPinned={pinnedResults.some(
                    (p) =>
                      p.mediaId ===
                      ((result.metadata as Record<string, unknown>)
                        ?.media_id as number)
                  )}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {pinnedResults.length > 0 && (
        <div className="flex items-center justify-between border-t border-border pt-2 text-xs text-text-muted">
          <span>
            {t("sidepanel:rag.savedResultsCount", "Saved results ({{count}})", {
              count: pinnedResults.length
            })}
          </span>
          {onOpenContext && (
            <button
              type="button"
              onClick={onOpenContext}
              className="text-xs text-accent hover:text-accent/80 transition-colors"
            >
              {t("sidepanel:rag.manageSavedResults", "Manage in Context")}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
