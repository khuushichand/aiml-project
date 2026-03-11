import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { useStorage } from "@plasmohq/storage/hook"
import { useSetting } from "@/hooks/useSetting"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useServerOnline } from "@/hooks/useServerOnline"
import { getSetting, setSetting, clearSetting } from "@/services/settings/registry"
import {
  LAST_MEDIA_ID_SETTING,
  MEDIA_HIDE_TRANSCRIPT_TIMINGS_SETTING,
  MEDIA_REVIEW_ORIENTATION_SETTING,
  MEDIA_REVIEW_VIEW_MODE_SETTING,
  MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING,
  MEDIA_REVIEW_AUTO_VIEW_MODE_SETTING,
  MEDIA_REVIEW_SELECTION_SETTING,
  MEDIA_REVIEW_FOCUSED_ID_SETTING
} from "@/services/settings/ui-settings"
import {
  hasLeadingTranscriptTimings
} from "@/utils/media-transcript-display"
import type { MediaDateRange, MediaSortBy } from "@/components/Review/mediaSearchRequest"
import {
  IDLE_CONTENT_FILTER_PROGRESS,
  toProgressLabel,
  type ContentFilterProgress
} from "@/components/Review/content-filtering-progress"
import {
  STACK_VIRTUAL_ESTIMATE_SIZE,
  STACK_VIRTUAL_OVERSCAN,
  shouldVirtualizeStackMode
} from "@/components/Review/stack-virtualization"
import type { MediaMultiBatchExportFormat } from "@/components/Review/media-multi-batch-actions"
import {
  type MediaItem,
  type MediaDetail,
  getContent,
  DEFAULT_SORT_BY,
  SELECTION_WARNING_THRESHOLD,
  RESULTS_ROW_ESTIMATE_SIZE,
  MOBILE_REVIEW_MEDIA_QUERY,
  getIsMobileReviewViewport,
  type MediaReviewState
} from "@/components/Review/media-review-types"

export function useMediaReviewState(
  fetchListFn: React.MutableRefObject<(() => Promise<MediaItem[]>) | null>
): MediaReviewState {
  const { t } = useTranslation(['review'])
  const navigate = useNavigate()
  const message = useAntdMessage()
  const { setChatMode, setSelectedKnowledge, setRagMediaIds } = useMessageOption()
  const [helpDismissed, setHelpDismissed, { isLoading: helpDismissedLoading }] = useStorage<boolean>('mediaReviewHelpDismissed', false)
  const [query, setQuery] = React.useState("")
  const searchInputRef = React.useRef<HTMLInputElement | null>(null)
  const [page, setPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(20)
  const [total, setTotal] = React.useState(0)
  const [orientation, setOrientation] = useSetting(MEDIA_REVIEW_ORIENTATION_SETTING)
  const [hideTranscriptTimings, setHideTranscriptTimings] = useSetting(MEDIA_HIDE_TRANSCRIPT_TIMINGS_SETTING)
  const [selectedIds, setSelectedIds] = React.useState<Array<string | number>>([])
  const [batchKeywordsDraft, setBatchKeywordsDraft] = React.useState("")
  const [batchExportFormat, setBatchExportFormat] = React.useState<MediaMultiBatchExportFormat>("json")
  const [batchActionLoading, setBatchActionLoading] = React.useState<
    null | "keywords" | "trash" | "export" | "reprocess"
  >(null)
  const [batchTrashHandoffIds, setBatchTrashHandoffIds] = React.useState<Array<string | number>>([])
  const [details, setDetails] = React.useState<Record<string | number, MediaDetail>>({})
  const [availableTypes, setAvailableTypes] = React.useState<string[]>([])
  const [types, setTypes] = React.useState<string[]>([])
  const [keywordTokens, setKeywordTokens] = React.useState<string[]>([])
  const [keywordOptions, setKeywordOptions] = React.useState<string[]>([])
  const [includeContent, setIncludeContent] = React.useState<boolean>(false)
  const [sortBy, setSortBy] = React.useState<MediaSortBy>(DEFAULT_SORT_BY)
  const [dateRange, setDateRange] = React.useState<MediaDateRange>({
    startDate: null,
    endDate: null
  })
  const [isMobileViewport, setIsMobileViewport] = React.useState<boolean>(() =>
    getIsMobileReviewViewport()
  )
  const [sidebarHidden, setSidebarHidden] = React.useState<boolean>(() =>
    getIsMobileReviewViewport()
  )
  const [contentLoading, setContentLoading] = React.useState<boolean>(false)
  const [contentFilterProgress, setContentFilterProgress] =
    React.useState<ContentFilterProgress>(IDLE_CONTENT_FILTER_PROGRESS)
  const [contentExpandedIds, setContentExpandedIds] = React.useState<Set<string>>(new Set())
  const [analysisExpandedIds, setAnalysisExpandedIds] = React.useState<Set<string>>(new Set())
  const [showEmptyAnalysisIds, setShowEmptyAnalysisIds] = React.useState<Set<string>>(new Set())
  const [detailLoading, setDetailLoading] = React.useState<Record<string | number, boolean>>({})
  const [failedIds, setFailedIds] = React.useState<Set<string | number>>(new Set())
  const [openAllLimit] = React.useState<number>(30)
  const [helpModalOpen, setHelpModalOpen] = React.useState(false)
  const [selectedItemsDrawerOpen, setSelectedItemsDrawerOpen] = React.useState(false)
  const [copiedIds, setCopiedIds] = React.useState<Set<string>>(new Set())
  const [persistedViewMode, setPersistedViewMode] = useSetting(MEDIA_REVIEW_VIEW_MODE_SETTING)
  const [viewModeState, setViewModeState] = React.useState<"spread" | "list" | "all">("spread")
  const shouldHideTranscriptTimings = hideTranscriptTimings ?? true
  const viewMode = isMobileViewport
    ? (viewModeState === "all" && selectedIds.length > 1 ? "all" : "list")
    : viewModeState
  const setViewMode = React.useCallback((mode: "spread" | "list" | "all") => {
    if (isMobileViewport) {
      setViewModeState(mode === "all" && selectedIds.length > 1 ? "all" : "list")
      return
    }
    setViewModeState(mode)
    void setPersistedViewMode(mode)
  }, [isMobileViewport, selectedIds.length, setPersistedViewMode])

  React.useEffect(() => {
    if (persistedViewMode) setViewModeState(persistedViewMode)
  }, [persistedViewMode])

  React.useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mediaQuery = window.matchMedia(MOBILE_REVIEW_MEDIA_QUERY)
    const handleMediaQueryChange = (event: MediaQueryListEvent) => {
      setIsMobileViewport(event.matches)
    }
    setIsMobileViewport(mediaQuery.matches)
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', handleMediaQueryChange)
      return () => mediaQuery.removeEventListener('change', handleMediaQueryChange)
    }
    mediaQuery.addListener(handleMediaQueryChange)
    return () => mediaQuery.removeListener(handleMediaQueryChange)
  }, [])

  React.useEffect(() => {
    if (!isMobileViewport) return
    setViewModeState("list")
    setSidebarHidden((prev) => (prev ? prev : true))
  }, [isMobileViewport])

  const [focusedId, setFocusedId] = React.useState<string | number | null>(null)
  const [previewedId, setPreviewedId] = React.useState<string | number | null>(null)
  const [collapseOthers, setCollapseOthers] = React.useState<boolean>(false)
  const [pendingInitialMediaId, setPendingInitialMediaId] = React.useState<string | null>(null)
  const [compareDiffOpen, setCompareDiffOpen] = React.useState(false)
  const [compareLeftText, setCompareLeftText] = React.useState("")
  const [compareRightText, setCompareRightText] = React.useState("")
  const [compareLeftLabel, setCompareLeftLabel] = React.useState("")
  const [compareRightLabel, setCompareRightLabel] = React.useState("")
  const [filtersCollapsed, setFiltersCollapsed] = useSetting(MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING)
  const [autoViewModeSetting, setAutoViewModeSetting] = useSetting(MEDIA_REVIEW_AUTO_VIEW_MODE_SETTING)
  const autoViewMode = autoViewModeSetting ?? true
  const [manualViewModePinned, setManualViewModePinned] = React.useState(false)
  const [autoModeInlineNotice, setAutoModeInlineNotice] = React.useState<string | null>(null)
  const lastClickedRef = React.useRef<string | number | null>(null)
  const viewerRef = React.useRef<HTMLDivElement>(null)
  const pendingRestoreFocusIdRef = React.useRef<string | number | null>(null)
  const lastEscapePressRef = React.useRef<number>(0)
  const prevAutoViewModeRef = React.useRef<string | null>(null)
  const contentFilterRunRef = React.useRef(0)
  const prefersReducedMotion = React.useMemo(() =>
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  )
  const isOnline = useServerOnline()
  const [selectionRestored, setSelectionRestored] = React.useState(false)

  // Restore selection state on mount
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const lastMediaId = await getSetting(LAST_MEDIA_ID_SETTING)
      if (!cancelled && lastMediaId) {
        setPendingInitialMediaId(lastMediaId)
      }
      const savedSelection = await getSetting(MEDIA_REVIEW_SELECTION_SETTING)
      const savedFocusedId = await getSetting(MEDIA_REVIEW_FOCUSED_ID_SETTING)
      if (!cancelled) {
        if (savedSelection && savedSelection.length > 0) {
          setSelectedIds(savedSelection)
        }
        if (savedFocusedId != null) {
          setFocusedId(savedFocusedId)
        }
        setSelectionRestored(true)
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Persist selection state
  React.useEffect(() => {
    if (!selectionRestored) return
    void setSetting(MEDIA_REVIEW_SELECTION_SETTING, selectedIds)
  }, [selectedIds, selectionRestored])

  React.useEffect(() => {
    if (!selectionRestored) return
    void setSetting(MEDIA_REVIEW_FOCUSED_ID_SETTING, focusedId)
  }, [focusedId, selectionRestored])

  // Query integration
  const { data, isFetching, refetch } = useQuery({
    queryKey: [
      "media-review",
      query,
      page,
      pageSize,
      types.join(","),
      keywordTokens.join(","),
      includeContent,
      sortBy,
      dateRange.startDate ?? "",
      dateRange.endDate ?? ""
    ],
    queryFn: () => {
      if (fetchListFn.current) return fetchListFn.current()
      return Promise.resolve([] as MediaItem[])
    },
    placeholderData: keepPreviousData,
    enabled: isOnline
  })

  React.useEffect(() => { refetch() }, [])

  // Derived values
  const cardCls = orientation === 'vertical'
    ? 'border border-border rounded p-3 bg-surface w-full'
    : 'border border-border rounded p-3 bg-surface w-full md:w-[48%]'

  const allResults: MediaItem[] = Array.isArray(data) ? data : []
  const hasResults = allResults.length > 0
  const viewerItems = selectedIds.map((id) => details[id]).filter(Boolean)
  const hasTranscriptTimingContentInViewer = React.useMemo(
    () =>
      viewerItems.some((detail) =>
        hasLeadingTranscriptTimings(getContent(detail) || "")
      ),
    [viewerItems]
  )
  const visibleIds = viewMode === "spread"
    ? selectedIds
    : viewMode === "list"
      ? (focusedId != null ? [focusedId] : [])
      : selectedIds
  const focusedDetail = focusedId != null ? details[focusedId] : null
  const focusIndex = focusedId != null ? allResults.findIndex((r) => r.id === focusedId) : -1
  const previewedDetail = previewedId != null ? details[previewedId] : null
  const previewIndex = previewedId != null ? allResults.findIndex((r) => r.id === previewedId) : -1
  const listParentRef = React.useRef<HTMLDivElement | null>(null)
  const viewerParentRef = React.useRef<HTMLDivElement | null>(null)
  const stackParentRef = React.useRef<HTMLDivElement | null>(null)
  const cardRefs = React.useRef<Record<string, HTMLElement | null>>({})

  // Virtualizers
  const listVirtualizer = useVirtualizer({
    count: allResults.length,
    getScrollElement: () => listParentRef.current,
    estimateSize: () => RESULTS_ROW_ESTIMATE_SIZE,
    overscan: 8,
    getItemKey: (index) => String((allResults[index] as any)?.id ?? index),
    measureElement: (el) => el.getBoundingClientRect().height
  })

  const viewerVirtualizer = useVirtualizer({
    count: viewMode === "spread" ? viewerItems.length : viewMode === "list" ? (focusedDetail ? 1 : 0) : 0,
    getScrollElement: () => viewerParentRef.current,
    estimateSize: () => 520,
    overscan: 6,
    measureElement: (el) => el.getBoundingClientRect().height
  })

  const stackVirtualizer = useVirtualizer({
    count: viewMode === "all" && shouldVirtualizeStackMode(viewerItems.length) ? viewerItems.length : 0,
    getScrollElement: () => stackParentRef.current,
    estimateSize: () => STACK_VIRTUAL_ESTIMATE_SIZE,
    overscan: STACK_VIRTUAL_OVERSCAN,
    getItemKey: (index) => String(viewerItems[index]?.id ?? index),
    measureElement: (el) => el.getBoundingClientRect().height
  })

  // Close drawer when selection empties
  React.useEffect(() => {
    if (selectedIds.length === 0) setSelectedItemsDrawerOpen(false)
  }, [selectedIds.length])

  // Selection status
  const hasDateRangeFilter = Boolean(dateRange.startDate || dateRange.endDate)
  const selectionStatusLevel =
    selectedIds.length >= openAllLimit
      ? "limit" as const
      : selectedIds.length >= SELECTION_WARNING_THRESHOLD
        ? "warning" as const
        : "safe" as const
  const selectionStatusText =
    selectionStatusLevel === "limit"
      ? t("mediaPage.selectionStatusLimit", "Limit reached")
      : selectionStatusLevel === "warning"
        ? t("mediaPage.selectionStatusWarning", "Warning")
        : t("mediaPage.selectionStatusSafe", "Safe")
  const activeFilterCount =
    types.length +
    keywordTokens.length +
    (includeContent ? 1 : 0) +
    (sortBy !== DEFAULT_SORT_BY ? 1 : 0) +
    (hasDateRangeFilter ? 1 : 0)
  const contentProgressLabel = toProgressLabel(contentFilterProgress)
  const sortOptions = React.useMemo(
    () => [
      { value: "relevance" as MediaSortBy, label: t("mediaPage.sortRelevance", "Relevance") },
      { value: "date_desc" as MediaSortBy, label: t("mediaPage.sortDateDesc", "Date: newest first") },
      { value: "date_asc" as MediaSortBy, label: t("mediaPage.sortDateAsc", "Date: oldest first") },
      { value: "title_asc" as MediaSortBy, label: t("mediaPage.sortTitleAsc", "Title: A-Z") },
      { value: "title_desc" as MediaSortBy, label: t("mediaPage.sortTitleDesc", "Title: Z-A") }
    ],
    [t]
  )
  const sortLabelLookup = React.useMemo(
    () => Object.fromEntries(sortOptions.map((option) => [option.value, option.label])),
    [sortOptions]
  )
  const dateRangeLabel = React.useMemo(() => {
    if (!hasDateRangeFilter) return null
    const start = dateRange.startDate || t("mediaPage.dateRangeAnyStart", "Any start")
    const end = dateRange.endDate || t("mediaPage.dateRangeAnyEnd", "Any end")
    return `${start} → ${end}`
  }, [dateRange.endDate, dateRange.startDate, hasDateRangeFilter, t])

  // ensureDetail ref (will be set by actions hook)
  const ensureDetailRef = React.useRef<(id: string | number, isRetry?: boolean) => Promise<void>>(
    async () => {}
  )

  return {
    t, navigate, message,
    query, setQuery, page, setPage, pageSize, setPageSize, total, setTotal,
    types, setTypes, keywordTokens, setKeywordTokens, keywordOptions, setKeywordOptions,
    includeContent, setIncludeContent, sortBy, setSortBy, dateRange, setDateRange,
    availableTypes, setAvailableTypes,
    selectedIds, setSelectedIds, focusedId, setFocusedId, previewedId, setPreviewedId, selectionRestored, setSelectionRestored,
    details, setDetails, contentLoading, setContentLoading,
    contentFilterProgress, setContentFilterProgress,
    contentExpandedIds, setContentExpandedIds, analysisExpandedIds, setAnalysisExpandedIds,
    showEmptyAnalysisIds, setShowEmptyAnalysisIds,
    detailLoading, setDetailLoading, failedIds, setFailedIds, openAllLimit,
    orientation, setOrientation, hideTranscriptTimings, setHideTranscriptTimings,
    shouldHideTranscriptTimings,
    isMobileViewport, setIsMobileViewport, sidebarHidden, setSidebarHidden,
    viewMode, viewModeState, setViewModeState, setViewMode,
    filtersCollapsed, setFiltersCollapsed,
    autoViewMode, autoViewModeSetting, setAutoViewModeSetting,
    manualViewModePinned, setManualViewModePinned,
    autoModeInlineNotice, setAutoModeInlineNotice,
    collapseOthers, setCollapseOthers,
    pendingInitialMediaId, setPendingInitialMediaId,
    batchKeywordsDraft, setBatchKeywordsDraft,
    batchExportFormat, setBatchExportFormat,
    batchActionLoading, setBatchActionLoading,
    batchTrashHandoffIds, setBatchTrashHandoffIds,
    compareDiffOpen, setCompareDiffOpen,
    compareLeftText, setCompareLeftText, compareRightText, setCompareRightText,
    compareLeftLabel, setCompareLeftLabel, compareRightLabel, setCompareRightLabel,
    helpDismissed: helpDismissed ?? false, setHelpDismissed, helpDismissedLoading: helpDismissedLoading ?? false,
    helpModalOpen, setHelpModalOpen,
    selectedItemsDrawerOpen, setSelectedItemsDrawerOpen,
    copiedIds, setCopiedIds,
    searchInputRef, listParentRef, viewerRef, viewerParentRef, stackParentRef,
    cardRefs, lastClickedRef, lastEscapePressRef,
    pendingRestoreFocusIdRef, contentFilterRunRef, prevAutoViewModeRef, ensureDetailRef,
    allResults, hasResults, viewerItems, hasTranscriptTimingContentInViewer,
    visibleIds, focusedDetail, focusIndex, previewedDetail, previewIndex, cardCls, prefersReducedMotion, isOnline,
    selectionStatusLevel, selectionStatusText, activeFilterCount, contentProgressLabel,
    hasDateRangeFilter, sortOptions, sortLabelLookup, dateRangeLabel,
    collapsedFilterChips: [], // Will be computed in main component or actions
    setChatMode, setSelectedKnowledge, setRagMediaIds,
    data, isFetching, refetch,
    listVirtualizer, viewerVirtualizer, stackVirtualizer
  } as MediaReviewState
}
