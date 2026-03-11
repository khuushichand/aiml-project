import React from "react"
import { Select, Checkbox, Button, Spin } from "antd"
import type { MediaReviewState, MediaReviewActions } from "@/components/Review/media-review-types"
import type { MediaSortBy } from "@/components/Review/mediaSearchRequest"

interface MediaReviewFilterSidebarProps {
  state: MediaReviewState
  actions: MediaReviewActions
}

export const MediaReviewFilterSidebar: React.FC<MediaReviewFilterSidebarProps> = ({ state, actions }) => {
  const {
    t,
    types, setTypes,
    sortBy, setSortBy,
    dateRange, setDateRange,
    keywordTokens, setKeywordTokens,
    keywordOptions,
    includeContent, setIncludeContent,
    contentLoading,
    contentFilterProgress, contentProgressLabel,
    availableTypes,
    sortOptions,
    activeFilterCount,
    setPage, refetch
  } = state

  const { loadKeywordSuggestions, cancelContentFiltering } = actions

  return (
    <div id="filter-section" className="flex flex-wrap items-center gap-2 w-full mb-2 animate-in fade-in duration-150">
      <Select
        mode="multiple"
        allowClear
        placeholder={t('mediaPage.types', 'Media types')}
        aria-label={t('mediaPage.types', 'Media types') as string}
        className="min-w-[12rem]"
        value={types}
        onChange={(vals) => { setTypes(vals as string[]); setPage(1); refetch() }}
        options={availableTypes.map((t) => ({ label: t, value: t }))}
      />
      <Select
        value={sortBy}
        aria-label={t('mediaPage.sort', 'Sort') as string}
        className="min-w-[12rem]"
        onChange={(value) => {
          setSortBy(value as MediaSortBy)
          setPage(1)
          refetch()
        }}
        options={sortOptions.map((option) => ({
          value: option.value,
          label: option.label
        }))}
      />
      <div
        role="group"
        aria-label={t('mediaPage.dateRange', 'Date range') as string}
        className="flex items-center gap-2 rounded border border-border px-2 py-1"
      >
        <span className="text-xs text-text-muted">
          {t('mediaPage.dateRange', 'Date range')}
        </span>
        <input
          type="date"
          aria-label={t('mediaPage.startDate', 'Start date') as string}
          className="rounded border border-border bg-surface px-2 py-1 text-xs"
          value={dateRange.startDate ?? ""}
          onChange={(event) => {
            setDateRange((prev) => ({ ...prev, startDate: event.target.value || null }))
            setPage(1)
            refetch()
          }}
        />
        <span className="text-xs text-text-muted">{t('mediaPage.to', 'to')}</span>
        <input
          type="date"
          aria-label={t('mediaPage.endDate', 'End date') as string}
          className="rounded border border-border bg-surface px-2 py-1 text-xs"
          value={dateRange.endDate ?? ""}
          onChange={(event) => {
            setDateRange((prev) => ({ ...prev, endDate: event.target.value || null }))
            setPage(1)
            refetch()
          }}
        />
      </div>
      <Select
        mode="tags"
        allowClear
        showSearch
        placeholder={t('mediaPage.keywords', 'Keywords')}
        aria-label={t('mediaPage.keywords', 'Keywords') as string}
        className="min-w-[12rem]"
        value={keywordTokens}
        onSearch={(txt) => loadKeywordSuggestions(txt)}
        onChange={(vals) => { setKeywordTokens(vals as string[]); setPage(1); refetch() }}
        options={keywordOptions.map((k) => ({ label: k, value: k }))}
      />
      <div className="flex items-center gap-2">
        <Checkbox checked={includeContent} onChange={(e) => { setIncludeContent(e.target.checked); setPage(1); refetch() }}>
          {t('mediaPage.contentSearchLabel', 'Search full content (slower)')}
        </Checkbox>
        <span className="text-[11px] text-text-muted">
          {t('mediaPage.contentSearchScope', 'Scans current page results.')}
        </span>
        {contentLoading && (<Spin size="small" className="ml-1" />)}
        {contentFilterProgress.running && (
          <>
            <span
              role="status"
              aria-label={t("mediaPage.contentSearchProgressAria", "Content filtering progress") as string}
              className="text-[11px] text-text-muted"
            >
              {t("mediaPage.contentSearchProgress", "Content filtering {{progress}}", {
                progress: contentProgressLabel
              })}
            </span>
            <Button
              size="small"
              type="link"
              className="!px-1"
              onClick={cancelContentFiltering}
            >
              {t("mediaPage.cancel", "Cancel")}
            </Button>
          </>
        )}
      </div>
      {activeFilterCount > 0 && (
        <Button size="small" onClick={() => {
          setTypes([])
          setKeywordTokens([])
          setIncludeContent(false)
          setSortBy("relevance" as MediaSortBy)
          setDateRange({ startDate: null, endDate: null })
          setPage(1)
          refetch()
        }}>
          {t('mediaPage.resetFilters', 'Clear filters')}
        </Button>
      )}
    </div>
  )
}
