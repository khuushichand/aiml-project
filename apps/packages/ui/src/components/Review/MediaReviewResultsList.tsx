import React from "react"
import { Tag, Checkbox, Pagination, Skeleton, Empty, Button } from "antd"
import type { MediaReviewState, MediaReviewActions } from "@/components/Review/media-review-types"
import { includesId } from "@/components/Review/media-review-types"

interface MediaReviewResultsListProps {
  state: MediaReviewState
  actions: MediaReviewActions
}

export const MediaReviewResultsList: React.FC<MediaReviewResultsListProps> = ({ state, actions }) => {
  const {
    t,
    allResults, hasResults,
    selectedIds, previewedId,
    isFetching,
    total, page, pageSize, setPage, setPageSize,
    listParentRef, listVirtualizer
  } = state

  const { previewItem, toggleSelect, clearSelectionWithGuard } = actions

  return (
    <>
      <div className="flex items-center justify-between mb-1">
        <div
          className="text-sm text-text-muted"
          role="heading"
          aria-level={2}
          data-testid="media-review-results-header"
        >
          {t("mediaPage.results", "Results")}{" "}
          {hasResults ? `(${allResults.length})` : ""}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          <span className="text-xs text-text-muted">
            {t("mediaPage.resultsHint", "Click to preview. Use checkboxes to select. Shift+click for range.")}
          </span>
          {selectedIds.length > 0 && (
            <Button
              size="small"
              type="link"
              className="!px-1"
              onClick={clearSelectionWithGuard}
            >
              {t('mediaPage.clearSelection', 'Clear')}
            </Button>
          )}
        </div>
      </div>
      {isFetching && (
        <div
          className="mb-2 rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs text-primary"
          role="status"
          aria-live="polite">
          {t("mediaPage.searchingBanner", "Searching media…")}
        </div>
      )}
      {isFetching && !hasResults ? (
        <div className="relative flex-1 min-h-0 overflow-auto rounded border border-dashed border-border">
          <div className="divide-y divide-border">
            {Array.from({ length: 6 }).map((_, idx) => (
              <div key={idx} className="px-3 py-2">
                <Skeleton
                  active
                  title={{ width: "60%" }}
                  paragraph={{ rows: 2, width: ["40%", "80%"] }}
                />
              </div>
            ))}
          </div>
        </div>
      ) : hasResults ? (
        <>
          <div
            ref={listParentRef}
            data-testid="media-review-results-list"
            className="relative flex-1 min-h-0 overflow-auto rounded border border-dashed border-border"
          >
            <div
              style={{
                height: `${listVirtualizer.getTotalSize()}px`,
                position: "relative",
                width: "100%"
              }}
            >
              {listVirtualizer.getVirtualItems().map((virtualRow: any) => {
                const item = allResults[virtualRow.index]
                const isSelected = includesId(selectedIds, item.id)
                const isPreviewed = previewedId != null && String(previewedId) === String(item.id)
                return (
                  <div
                    key={item.id}
                    ref={(el: any) => {
                      if (el) listVirtualizer.measureElement(el)
                    }}
                    data-media-id={String(item.id)}
                    data-index={virtualRow.index}
                    role="button"
                    aria-selected={isSelected}
                    aria-current={isPreviewed ? "true" : undefined}
                    tabIndex={0}
                    onClick={() => previewItem(item.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        // Enter/Space on row = toggle selection (for keyboard a11y)
                        void toggleSelect(item.id)
                      }
                    }}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`
                    }}
                    className={`px-3 py-2 border-b border-border cursor-pointer hover:bg-surface2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary focus-visible:bg-surface2 ${isSelected ? "bg-surface2 ring-2 ring-primary" : ""} ${isPreviewed && !isSelected ? "bg-primary/5 border-l-2 border-l-primary" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div
                        className="min-w-[44px] min-h-[44px] flex items-center justify-center cursor-pointer -ml-2 -mt-1"
                        onClick={(e) => {
                          e.stopPropagation()
                          void toggleSelect(item.id, e)
                        }}
                      >
                        <Checkbox
                          checked={isSelected}
                          tabIndex={-1}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">{item.title}</div>
                        <div className="text-[11px] text-text-muted flex items-center gap-2 mt-1">
                          {item.type && <Tag>{item.type}</Tag>}
                          {item.created_at && <span>{new Date(item.created_at).toLocaleString()}</span>}
                        </div>
                        {item.snippet && (
                          <div className="text-xs text-text-muted line-clamp-2">
                            {item.snippet}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="mt-2 flex justify-between items-center">
            <div className="text-[11px] text-text-muted">{t("mediaPage.paginationHint", "Use pagination or open all visible items")}</div>
            <Pagination size="small" current={page} pageSize={pageSize} total={total} onChange={(p, ps) => { setPage(p); setPageSize(ps); }} />
          </div>
        </>
      ) : (
        <Empty description={t("mediaPage.noResults", "No results")} />
      )}
    </>
  )
}
