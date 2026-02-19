import React from "react"
import { Input, Button, Spin, Tag, Tooltip, Radio, Pagination, Empty, Select, Checkbox, Typography, Skeleton, Switch, Alert, Collapse, Dropdown, Modal } from "antd"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { bgRequest } from "@/services/background-proxy"
import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { useServerOnline } from "@/hooks/useServerOnline"
import { getNoteKeywords, searchNoteKeywords } from "@/services/note-keywords"
import { CopyIcon, HelpCircle, Settings2, ChevronLeft, ChevronRight, Layers, LayoutGrid, Focus, Rows3, Check, MessageSquare } from "lucide-react"
import { useVirtualizer, type VirtualItem } from "@tanstack/react-virtual"
import { ChevronDown, ChevronUp } from "lucide-react"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { useStorage } from "@plasmohq/storage/hook"
import { useSetting } from "@/hooks/useSetting"
import { useMessageOption } from "@/hooks/useMessageOption"
import { DiffViewModal } from "@/components/Media/DiffViewModal"
import {
  DISCUSS_MEDIA_PROMPT_SETTING,
  LAST_MEDIA_ID_SETTING,
  MEDIA_REVIEW_ORIENTATION_SETTING,
  MEDIA_REVIEW_VIEW_MODE_SETTING,
  MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING,
  MEDIA_REVIEW_AUTO_VIEW_MODE_SETTING,
  MEDIA_REVIEW_SELECTION_SETTING,
  MEDIA_REVIEW_FOCUSED_ID_SETTING
} from "@/services/settings/ui-settings"
import { clearSetting, getSetting, setSetting } from "@/services/settings/registry"
import { extractMediaDetailContent } from "@/utils/media-detail-content"

type MediaItem = {
  id: string | number
  title?: string
  snippet?: string
  type?: string
  created_at?: string
}

type MediaDetail = {
  id: string | number
  title?: string
  type?: string
  created_at?: string
  content?: string | Record<string, unknown>
  text?: string
  raw_text?: string
  summary?: string
  latest_version?: { content?: string | Record<string, unknown> }
}

const getContent = (d: MediaDetail): string => {
  return extractMediaDetailContent(d)
}

const getErrorStatusCode = (error: unknown): number | null => {
  if (!error || typeof error !== "object") return null
  const candidate = error as Record<string, unknown>
  const rawStatus =
    candidate.status ??
    (candidate.response &&
    typeof candidate.response === "object" &&
    (candidate.response as Record<string, unknown>).status != null
      ? (candidate.response as Record<string, unknown>).status
      : null) ??
    candidate.statusCode
  const parsed = Number(rawStatus)
  return Number.isFinite(parsed) ? parsed : null
}

const MINIMAP_COLLAPSE_THRESHOLD = 8
const SELECTION_WARNING_THRESHOLD = 25
const UNDO_DURATION_SECONDS = 15
const MOBILE_REVIEW_MEDIA_QUERY = '(max-width: 1023px)'

const getIsMobileReviewViewport = (): boolean => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(MOBILE_REVIEW_MEDIA_QUERY).matches
}

export const MediaReviewPage: React.FC = () => {
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
  const [orientation, setOrientation] = useSetting(
    MEDIA_REVIEW_ORIENTATION_SETTING
  )
  const [selectedIds, setSelectedIds] = React.useState<Array<string | number>>([])
  const [details, setDetails] = React.useState<Record<string | number, MediaDetail>>({})
  const [availableTypes, setAvailableTypes] = React.useState<string[]>([])
  const [types, setTypes] = React.useState<string[]>([])
  const [keywordTokens, setKeywordTokens] = React.useState<string[]>([])
  const [keywordOptions, setKeywordOptions] = React.useState<string[]>([])
  const [includeContent, setIncludeContent] = React.useState<boolean>(false)
  const [isMobileViewport, setIsMobileViewport] = React.useState<boolean>(() =>
    getIsMobileReviewViewport()
  )
  const [sidebarHidden, setSidebarHidden] = React.useState<boolean>(() =>
    getIsMobileReviewViewport()
  )
  const [contentLoading, setContentLoading] = React.useState<boolean>(false)
  const [contentExpandedIds, setContentExpandedIds] = React.useState<Set<string>>(new Set())
  const [analysisExpandedIds, setAnalysisExpandedIds] = React.useState<Set<string>>(new Set())
  const [detailLoading, setDetailLoading] = React.useState<Record<string | number, boolean>>({})
  const [failedIds, setFailedIds] = React.useState<Set<string | number>>(new Set())
  const [openAllLimit] = React.useState<number>(30)
  // Help modal state (for touch device accessibility)
  const [helpModalOpen, setHelpModalOpen] = React.useState(false)
  // Copy confirmation state (track which buttons show checkmark)
  const [copiedIds, setCopiedIds] = React.useState<Set<string>>(new Set())
  // Persisted view mode
  const [persistedViewMode, setPersistedViewMode] = useSetting(MEDIA_REVIEW_VIEW_MODE_SETTING)
  const [viewModeState, setViewModeState] = React.useState<"spread" | "list" | "all">("spread")
  const viewMode = isMobileViewport ? "list" : viewModeState
  const setViewMode = React.useCallback((mode: "spread" | "list" | "all") => {
    if (isMobileViewport) {
      setViewModeState("list")
      return
    }
    setViewModeState(mode)
    void setPersistedViewMode(mode)
  }, [isMobileViewport, setPersistedViewMode])
  // Initialize view mode from persisted setting
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
  const [collapseOthers, setCollapseOthers] = React.useState<boolean>(false)
  const [pendingInitialMediaId, setPendingInitialMediaId] = React.useState<string | null>(null)
  const [compareDiffOpen, setCompareDiffOpen] = React.useState(false)
  const [compareLeftText, setCompareLeftText] = React.useState("")
  const [compareRightText, setCompareRightText] = React.useState("")
  const [compareLeftLabel, setCompareLeftLabel] = React.useState("")
  const [compareRightLabel, setCompareRightLabel] = React.useState("")
  // Persisted filter collapse state
  const [filtersCollapsed, setFiltersCollapsed] = useSetting(MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING)
  // Auto view mode setting
  const [autoViewModeSetting, setAutoViewModeSetting] = useSetting(MEDIA_REVIEW_AUTO_VIEW_MODE_SETTING)
  const autoViewMode = autoViewModeSetting ?? true
  // Last clicked for Shift+click range selection
  const lastClickedRef = React.useRef<string | number | null>(null)
  // Ref for viewer panel focus management
  const viewerRef = React.useRef<HTMLDivElement>(null)
  // Track last Escape press for double-tap detection
  const lastEscapePressRef = React.useRef<number>(0)
  // Track previous view mode for auto-mode notification
  const prevAutoViewModeRef = React.useRef<string | null>(null)
  // Check for reduced motion preference
  const prefersReducedMotion = React.useMemo(() =>
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  )
  const isOnline = useServerOnline()

  // Track whether we've restored selection from storage
  const [selectionRestored, setSelectionRestored] = React.useState(false)

  // Restore selection state on mount
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const lastMediaId = await getSetting(LAST_MEDIA_ID_SETTING)
      if (!cancelled && lastMediaId) {
        setPendingInitialMediaId(lastMediaId)
      }
      // Restore persisted selection
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
    return () => {
      cancelled = true
    }
  }, [])

  // Persist selection state when it changes (after initial restore)
  React.useEffect(() => {
    if (!selectionRestored) return
    void setSetting(MEDIA_REVIEW_SELECTION_SETTING, selectedIds)
  }, [selectedIds, selectionRestored])

  // Persist focused ID when it changes (after initial restore)
  React.useEffect(() => {
    if (!selectionRestored) return
    void setSetting(MEDIA_REVIEW_FOCUSED_ID_SETTING, focusedId)
  }, [focusedId, selectionRestored])

  const fetchList = async (): Promise<MediaItem[]> => {
    const hasQuery = query.trim().length > 0
    if (hasQuery) {
      const body: any = { query, fields: ["title", "content"], sort_by: "relevance" }
      if (types.length > 0) body.media_types = types
      if (keywordTokens.length > 0) body.must_have = keywordTokens
      const res = await bgRequest<any>({
        path: `/api/v1/media/search?page=${page}&results_per_page=${pageSize}` as any,
        method: "POST" as any,
        headers: { "Content-Type": "application/json" },
        body
      })
      const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res?.results) ? res.results : [])
      const pagination = res?.pagination
      setTotal(Number(pagination?.total_items || items.length || 0))
      const mapped = items.map((m: any) => ({
        id: m?.id ?? m?.media_id ?? m?.pk ?? m?.uuid,
        title: m?.title || m?.filename || `Media ${m?.id}`,
        snippet: m?.snippet || m?.summary || "",
        type: String(m?.type || m?.media_type || "").toLowerCase(),
        created_at: m?.created_at
      }))
      // Update available types
      const typeSet = new Set(availableTypes)
      for (const it of mapped) if (it.type) typeSet.add(it.type)
      setAvailableTypes(Array.from(typeSet))
      let filtered = mapped
      if (types.length > 0) filtered = filtered.filter((m) => m.type && types.includes(m.type))
      if (keywordTokens.length > 0) {
        const toks = keywordTokens.map((k) => k.toLowerCase())
        filtered = filtered.filter((m) => {
          const hay = `${m.title || ''} ${m.snippet || ''}`.toLowerCase()
          return toks.every((k) => hay.includes(k))
        })
      }
      if (includeContent && (keywordTokens.length > 0 || hasQuery)) {
        setContentLoading(true)
        // Fetch details to include content in filtering
        const enriched = await Promise.all(filtered.map(async (m) => {
          let d = details[m.id]
          if (!d) {
            try {
              d = await bgRequest<MediaDetail>({
                path: `/api/v1/media/${m.id}?include_content=true&include_versions=false` as any,
                method: 'GET' as any
              })
              setDetails((prev) => (prev[m.id] ? prev : { ...prev, [m.id]: d! }))
            } catch {}
          }
          const content = d ? getContent(d) : ''
          return { m, content }
        }))
        const toks = keywordTokens.map((k) => k.toLowerCase())
        const ql = query.toLowerCase()
        filtered = enriched.filter(({ m, content }) => {
          const hay = `${m.title || ''} ${m.snippet || ''} ${content}`.toLowerCase()
          if (hasQuery && !hay.includes(ql)) return false
          if (toks.length > 0 && !toks.every((k) => hay.includes(k))) return false
          return true
        }).map(({ m }) => m)
        setContentLoading(false)
      }
      return filtered
    }
    // Browse listing when no query
    const res = await bgRequest<any>({ path: `/api/v1/media/?page=${page}&results_per_page=${pageSize}` as any, method: "GET" as any })
    const items = Array.isArray(res?.items) ? res.items : []
    const pagination = res?.pagination
    setTotal(Number(pagination?.total_items || items.length || 0))
    const mapped = items.map((m: any) => ({
      id: m?.id ?? m?.media_id ?? m?.pk ?? m?.uuid,
      title: m?.title || m?.filename || `Media ${m?.id}`,
      snippet: m?.snippet || m?.summary || "",
      type: String(m?.type || m?.media_type || "").toLowerCase(),
      created_at: m?.created_at
    }))
    const typeSet = new Set(availableTypes)
    for (const it of mapped) if (it.type) typeSet.add(it.type)
    setAvailableTypes(Array.from(typeSet))
    let filtered = mapped
    if (types.length > 0) filtered = filtered.filter((m) => m.type && types.includes(m.type))
    if (keywordTokens.length > 0) {
      const toks = keywordTokens.map((k) => k.toLowerCase())
      filtered = filtered.filter((m) => {
        const hay = `${m.title || ''} ${m.snippet || ''}`.toLowerCase()
        return toks.every((k) => hay.includes(k))
      })
    }
    if (includeContent && (keywordTokens.length > 0 || query.trim().length > 0)) {
      setContentLoading(true)
      const enriched = await Promise.all(filtered.map(async (m) => {
        let d = details[m.id]
        if (!d) {
          try {
            d = await bgRequest<MediaDetail>({
              path: `/api/v1/media/${m.id}?include_content=true&include_versions=false` as any,
              method: 'GET' as any
            })
            setDetails((prev) => (prev[m.id] ? prev : { ...prev, [m.id]: d! }))
          } catch {}
        }
        const content = d ? getContent(d) : ''
        return { m, content }
      }))
      const toks = keywordTokens.map((k) => k.toLowerCase())
      const ql = query.toLowerCase()
      filtered = enriched.filter(({ m, content }) => {
        const hay = `${m.title || ''} ${m.snippet || ''} ${content}`.toLowerCase()
        if (query.trim().length > 0 && !hay.includes(ql)) return false
        if (toks.length > 0 && !toks.every((k) => hay.includes(k))) return false
        return true
      }).map(({ m }) => m)
      setContentLoading(false)
    }
    return filtered
  }

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["media-review", query, page, pageSize],
    queryFn: fetchList,
    // React Query v5: use placeholderData helper to keep previous data
    placeholderData: keepPreviousData,
    enabled: isOnline
  })

  React.useEffect(() => {
    // auto fetch initial
    refetch()
  }, [])

  // Keyword suggestions: preload and on-demand search
  const loadKeywordSuggestions = React.useCallback(async (q?: string) => {
    try {
      if (q && q.trim().length > 0) {
        const arr = await searchNoteKeywords(q, 10)
        setKeywordOptions(arr)
      } else {
        const arr = await getNoteKeywords(200)
        setKeywordOptions(arr)
      }
    } catch {
      // Keyword load failed - feature will use empty suggestions
    }
  }, [])

  React.useEffect(() => { if (isOnline) void loadKeywordSuggestions() }, [loadKeywordSuggestions, isOnline])

  const ensureDetail = React.useCallback(async (id: string | number, isRetry = false) => {
    if (details[id] || detailLoading[id]) return
    setDetailLoading((prev) => ({ ...prev, [id]: true }))
    // Clear from failed set if retrying
    if (isRetry) {
      setFailedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
    try {
      const d = await bgRequest<MediaDetail>({
        path: `/api/v1/media/${id}?include_content=true&include_versions=false` as any,
        method: 'GET' as any
      })
      const base = Array.isArray(data) ? (data as MediaItem[]).find((x) => x.id === id) : undefined
      const enriched = { ...d, id, title: (d as any)?.title ?? base?.title, type: (d as any)?.type ?? base?.type, created_at: (d as any)?.created_at ?? base?.created_at } as any
      setDetails((prev) => ({ ...prev, [id]: enriched }))
      // Remove from failed set on success
      setFailedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch (error) {
      // Track failed fetch
      setFailedIds((prev) => new Set(prev).add(id))
      const statusCode = getErrorStatusCode(error)
      if (statusCode === 404 || statusCode === 410) {
        setSelectedIds((prev) => {
          const next = prev.filter((candidateId) => String(candidateId) !== String(id))
          return next.length === prev.length ? prev : next
        })
        setFocusedId((prev) => (prev != null && String(prev) === String(id) ? null : prev))
      }
    } finally {
      setDetailLoading((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    }
  }, [data, detailLoading, details])

  const ensureDetailRef = React.useRef(ensureDetail)
  React.useEffect(() => {
    ensureDetailRef.current = ensureDetail
  }, [ensureDetail])

  const retryFetch = React.useCallback((id: string | number) => {
    // Clear from details to allow re-fetch
    setDetails((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    void ensureDetail(id, true)
  }, [ensureDetail])

  const clearSelectionWithGuard = React.useCallback(() => {
    if (selectedIds.length === 0) return

    // Always provide undo for any selection size (hospital interruption recovery)
    const selectionToRestore = [...selectedIds]
    const focusToRestore = focusedId

    setSelectedIds([])
    setFocusedId(null)

    message.info(
      <span>
        {t('mediaPage.selectionClearedCount', 'Selection cleared ({{count}} items).', { count: selectionToRestore.length })}
        {' '}
        <Button
          type="link"
          size="small"
          className="!p-0"
          onClick={() => {
            setSelectedIds(selectionToRestore)
            setFocusedId(focusToRestore ?? selectionToRestore[0] ?? null)
            message.success(t('mediaPage.selectionRestored', 'Selection restored'))
          }}
        >
          {t('mediaPage.undo', 'Undo')}
        </Button>
      </span>,
      UNDO_DURATION_SECONDS // Extended to 15 seconds for hospital context
    )
  }, [selectedIds, focusedId, t])

  const toggleSelect = async (id: string | number, event?: React.MouseEvent) => {
    // Shift+click range selection
    if (event?.shiftKey && lastClickedRef.current != null && Array.isArray(data)) {
      const lastIdx = data.findIndex(r => r.id === lastClickedRef.current)
      const currIdx = data.findIndex(r => r.id === id)
      if (lastIdx !== -1 && currIdx !== -1) {
        const [start, end] = lastIdx < currIdx ? [lastIdx, currIdx] : [currIdx, lastIdx]
        const rangeIds = data.slice(start, end + 1).map(r => r.id)
        const prevSet = new Set(selectedIds)
        const remaining = openAllLimit - prevSet.size
        if (remaining <= 0) {
          message.warning(
            t('mediaPage.selectionLimitReached', {
              defaultValue: 'Selection limit reached ({{limit}} items)',
              limit: openAllLimit
            })
          )
          return
        }
        const newIds = rangeIds.filter((rid) => !prevSet.has(rid))
        let toAdd = newIds
        if (newIds.length > remaining) {
          message.warning(
            t('mediaPage.selectionLimitReached', {
              defaultValue: 'Selection limit reached ({{limit}} items)',
              limit: openAllLimit
            })
          )
          toAdd = newIds.slice(newIds.length - remaining)
        }
        toAdd.forEach((rid) => prevSet.add(rid))
        setSelectedIds(Array.from(prevSet))
        toAdd.forEach((rid) => void ensureDetail(rid))
        setFocusedId(id)
        lastClickedRef.current = id
        // Move focus to viewer after selecting
        setTimeout(() => viewerRef.current?.focus(), 100)
        return
      }
    }

    if (!selectedIds.includes(id) && selectedIds.length >= openAllLimit) {
      message.warning(
        t('mediaPage.selectionLimitReached', {
          defaultValue: 'Selection limit reached ({{limit}} items)',
          limit: openAllLimit
        })
      )
      return
    }

    lastClickedRef.current = id
    setSelectedIds((prev) => {
      const exists = prev.includes(id)
      const next = exists ? prev.filter((x) => x !== id) : [...prev, id]
      // If adding (not removing), move focus to viewer
      if (!exists && viewerRef.current) {
        setTimeout(() => viewerRef.current?.focus(), 100)
      }
      return next
    })
    setFocusedId(id)
    void ensureDetail(id)
  }

  React.useEffect(() => {
    selectedIds.forEach((id) => {
      void ensureDetailRef.current(id)
    })
  }, [selectedIds])

  const cardCls = orientation === 'vertical'
    ? 'border border-border rounded p-3 bg-surface w-full'
    : 'border border-border rounded p-3 bg-surface w-full md:w-[48%]'

  const allResults: MediaItem[] = Array.isArray(data) ? data : []
  const hasResults = allResults.length > 0
  const viewerItems = selectedIds.map((id) => details[id]).filter(Boolean)
  const visibleIds = viewMode === "spread"
    ? selectedIds
    : viewMode === "list"
      ? (focusedId != null ? [focusedId] : [])
      : selectedIds
  const focusedDetail = focusedId != null ? details[focusedId] : null
  const focusIndex = focusedId != null ? allResults.findIndex((r) => r.id === focusedId) : -1
  const listParentRef = React.useRef<HTMLDivElement | null>(null)
  const viewerParentRef = React.useRef<HTMLDivElement | null>(null)
  const cardRefs = React.useRef<Record<string, HTMLElement | null>>({})

  const listVirtualizer = useVirtualizer({
    count: allResults.length,
    getScrollElement: () => listParentRef.current,
    estimateSize: () => 110,
    overscan: 8,
    getItemKey: (index) => String((allResults[index] as any)?.id ?? index)
  })

  const viewerVirtualizer = useVirtualizer({
    count: viewMode === "spread" ? viewerItems.length : viewMode === "list" ? (focusedDetail ? 1 : 0) : viewerItems.length,
    getScrollElement: () => viewerParentRef.current,
    estimateSize: () => 520,
    overscan: 6,
    // allow dynamic measurement for long transcripts
    measureElement: (el) => el.getBoundingClientRect().height
  })

  const openAllCurrent = React.useCallback(() => {
    if (allResults.length === 0) return
    const slice = allResults.slice(0, Math.min(allResults.length, openAllLimit))
    setSelectedIds(slice.map((m) => m.id))
    slice.forEach((m) => void ensureDetail(m.id))
    if (allResults.length > openAllLimit) {
      message.info(
        t("mediaPage.openAllCapped", {
          defaultValue: "Showing first {{count}} items to keep things smooth",
          count: openAllLimit
        })
      )
    }
  }, [allResults, ensureDetail, openAllLimit, t])

  const resolveDetailForCompare = React.useCallback(async (id: string | number): Promise<MediaDetail | null> => {
    const existing = details[id]
    if (existing) return existing
    try {
      const fetched = await bgRequest<MediaDetail>({
        path: `/api/v1/media/${id}?include_content=true&include_versions=false` as any,
        method: 'GET' as any
      })
      const base = allResults.find((item) => item.id === id)
      const enriched = {
        ...fetched,
        id,
        title: (fetched as any)?.title ?? base?.title,
        type: (fetched as any)?.type ?? base?.type,
        created_at: (fetched as any)?.created_at ?? base?.created_at
      } as MediaDetail
      setDetails((prev) => ({ ...prev, [id]: enriched }))
      return enriched
    } catch {
      return null
    }
  }, [allResults, details])

  const handleCompareContent = React.useCallback(async () => {
    if (selectedIds.length !== 2) return
    const [leftId, rightId] = selectedIds
    const leftDetail = await resolveDetailForCompare(leftId)
    const rightDetail = await resolveDetailForCompare(rightId)

    if (!leftDetail || !rightDetail) {
      message.error(
        t('mediaPage.compareContentLoadFailed', 'Could not load both items for comparison. Retry and try again.')
      )
      return
    }

    const leftContent = getContent(leftDetail).trim()
    const rightContent = getContent(rightDetail).trim()
    if (!leftContent || !rightContent) {
      message.error(
        t('mediaPage.compareContentMissing', 'One or both selected items have no content to compare.')
      )
      return
    }

    setCompareLeftText(leftContent)
    setCompareRightText(rightContent)
    setCompareLeftLabel(leftDetail.title || `${t('mediaPage.media', 'Media')} ${leftId}`)
    setCompareRightLabel(rightDetail.title || `${t('mediaPage.media', 'Media')} ${rightId}`)
    setCompareDiffOpen(true)
  }, [message, resolveDetailForCompare, selectedIds, t])

  const handleChatAboutSelection = React.useCallback(() => {
    if (selectedIds.length === 0) return

    const numericIds = Array.from(
      new Set(
        selectedIds
          .map((id) => Number(id))
          .filter((id) => Number.isFinite(id) && id > 0)
          .map((id) => Math.trunc(id))
      )
    )

    if (numericIds.length === 0) {
      message.warning(
        t(
          'mediaPage.chatSelectionInvalid',
          'Selected items are unavailable for media-scoped chat.'
        )
      )
      return
    }

    const primaryId = String(numericIds[0])
    setSelectedKnowledge(null as any)
    setRagMediaIds(numericIds)
    setChatMode('rag')

    const payload = {
      mediaId: primaryId,
      mode: 'rag_media' as const
    }

    try {
      void setSetting(DISCUSS_MEDIA_PROMPT_SETTING, payload)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('tldw:discuss-media', {
            detail: {
              ...payload,
              mediaIds: numericIds
            }
          })
        )
      }
    } catch {
      // ignore storage/event errors
    }

    navigate('/')
    try {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('tldw:focus-composer'))
      }
    } catch {
      // ignore
    }

    message.success(
      t('mediaPage.chatSelectionOpened', {
        defaultValue: 'Opened media-scoped RAG chat for {{count}} selected items.',
        count: numericIds.length
      })
    )
  }, [message, navigate, selectedIds, setChatMode, setRagMediaIds, setSelectedKnowledge, t])

  const expandAllContent = React.useCallback(() => {
    setContentExpandedIds(new Set(visibleIds.map((id) => String(id))))
  }, [visibleIds])
  const collapseAllContent = React.useCallback(() => setContentExpandedIds(new Set()), [])
  const expandAllAnalysis = React.useCallback(() => {
    setAnalysisExpandedIds(new Set(visibleIds.map((id) => String(id))))
  }, [visibleIds])
  const collapseAllAnalysis = React.useCallback(() => setAnalysisExpandedIds(new Set()), [])

  const scrollToCard = React.useCallback(
    (id: string | number) => {
      const anchor = cardRefs.current[String(id)]
      if (anchor) {
        anchor.scrollIntoView({
          behavior: prefersReducedMotion ? "auto" : "smooth",
          block: "start"
        })
        return
      }
      if (viewMode !== "all") {
        const idx = viewerItems.findIndex((m) => m.id === id)
        if (idx >= 0) viewerVirtualizer.scrollToIndex(idx, { align: "start" })
      }
    },
    [viewMode, viewerItems, viewerVirtualizer, prefersReducedMotion]
  )

  React.useEffect(() => {
    if (!pendingInitialMediaId) return
    if (!Array.isArray(allResults) || allResults.length === 0) return
    const match = allResults.find((m) => String(m.id) === pendingInitialMediaId)
    if (!match) return
    setSelectedIds([match.id])
    setFocusedId(match.id)
    void ensureDetail(match.id)
    scrollToCard(match.id)
    setPendingInitialMediaId(null)
    void clearSetting(LAST_MEDIA_ID_SETTING)
  }, [pendingInitialMediaId, allResults, ensureDetail, scrollToCard])

  const goRelative = React.useCallback(
    (delta: number) => {
      if (allResults.length === 0) return
      const currentIdx = focusIndex >= 0 ? focusIndex : 0
      let next = currentIdx + delta
      if (next < 0) next = 0
      if (next >= allResults.length) next = allResults.length - 1
      const nextId = allResults[next]?.id
      if (nextId != null) {
        setFocusedId(nextId)
        void ensureDetail(nextId)
      }
    },
    [allResults, ensureDetail, focusIndex]
  )

  // Global keyboard shortcuts
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in input/textarea/select
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return

      switch (e.key) {
        case 'a': // Select all visible (with Ctrl/Cmd)
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault()
            if (allResults.length === 0) return
            const slice = allResults.slice(0, Math.min(allResults.length, openAllLimit))
            setSelectedIds(slice.map((m) => m.id))
            slice.forEach((m) => void ensureDetail(m.id))
            if (allResults.length > openAllLimit) {
              message.info(t("mediaPage.openAllCapped", { defaultValue: "Showing first {{count}} items to keep things smooth", count: openAllLimit }))
            }
          }
          break
        case '/': // Focus search field
          if (e.ctrlKey || e.metaKey || e.altKey) break
          e.preventDefault()
          {
            const searchTarget =
              searchInputRef.current ??
              document.querySelector<HTMLInputElement>(
                'input[aria-label="Search media (title/content)"]'
              )
            if (searchTarget) {
              searchTarget.focus()
              searchTarget.select()
            }
          }
          break
        case 'ArrowDown': // Next in list
          e.preventDefault()
          goRelative(1)
          break
        case 'ArrowUp': // Previous in list
          e.preventDefault()
          goRelative(-1)
          break
        case 'j': // Next item
          e.preventDefault()
          goRelative(1)
          break
        case 'k': // Previous item
          e.preventDefault()
          goRelative(-1)
          break
        case 'o': // Toggle expand on focused card
          e.preventDefault()
          if (focusedId != null) {
            const key = String(focusedId)
            setContentExpandedIds(prev => {
              const next = new Set(prev)
              if (next.has(key)) next.delete(key)
              else next.add(key)
              return next
            })
          }
          break
        case 'Escape': // Clear selection (double-tap required for >5 items)
          e.preventDefault()
          if (selectedIds.length > 5) {
            const now = Date.now()
            if (now - lastEscapePressRef.current < 500) {
              // Double-tap detected - clear with guard
              clearSelectionWithGuard()
              lastEscapePressRef.current = 0
            } else {
              // First tap - show hint
              lastEscapePressRef.current = now
              message.info(t('mediaPage.escapeDoubleTapHint', 'Press Escape again to clear {{count}} items', { count: selectedIds.length }), 2)
            }
          } else {
            clearSelectionWithGuard()
          }
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [goRelative, focusedId, selectedIds.length, clearSelectionWithGuard, t, allResults, openAllLimit, ensureDetail])

  // Auto-select view mode by item count with notification
  React.useEffect(() => {
    if (isMobileViewport) {
      prevAutoViewModeRef.current = "list"
      return
    }
    if (!autoViewMode) return
    const count = selectedIds.length
    if (count === 0) return

    let newMode: "spread" | "list" | "all"
    if (count === 1) newMode = "list"
    else if (count <= 4) newMode = "spread"
    else newMode = "all"

    // Only notify if mode actually changed and wasn't initial load
    if (prevAutoViewModeRef.current !== null && prevAutoViewModeRef.current !== newMode) {
      const modeNames = { spread: t('mediaPage.spreadMode', 'Compare'), list: t('mediaPage.listMode', 'Focus'), all: t('mediaPage.allMode', 'Stack') }
      message.info(
        t('mediaPage.autoViewModeSwitched', 'Switched to {{mode}} view ({{count}} items)', {
          mode: modeNames[newMode],
          count
        }),
        3
      )
    }

    prevAutoViewModeRef.current = newMode
    setViewModeState(newMode)
  }, [isMobileViewport, selectedIds.length, autoViewMode, t])

  // Compute active filter count for collapsed state display
  const activeFilterCount = types.length + keywordTokens.length + (includeContent ? 1 : 0)

  const renderCard = (
    d: MediaDetail,
    idx: number,
    opts?: {
      virtualRow?: VirtualItem
      isAllMode?: boolean
    }
  ) => {
    if (!d) return null
    const { virtualRow, isAllMode } = opts || {}
    const key = String(d.id)
    const isFocused = d.id === focusedId
    const content = getContent(d) || ""
    const analysisText =
      d.summary ||
      (d as any)?.analysis ||
      (d as any)?.analysis_content ||
      (d as any)?.analysisContent ||
      ""
    const contentIsLong = content.length > 2000
    const analysisIsLong = analysisText.length > 1600
    const contentExpanded = contentExpandedIds.has(key)
    const analysisExpanded = analysisExpandedIds.has(key)
    const contentShown = !contentIsLong || contentExpanded ? content : `${content.slice(0, 2000)}…`
    const analysisShown = !analysisIsLong || analysisExpanded ? analysisText : `${analysisText.slice(0, 1600)}…`
    const isLoadingDetail = detailLoading[d.id]
    const hasFailed = failedIds.has(d.id)
    const rawSource = (d as any)?.source || (d as any)?.url || (d as any)?.original_url
    const source =
      rawSource && typeof rawSource === "object"
        ? (rawSource.url || rawSource.title || rawSource.href || "")
        : rawSource
    const transcriptLen = content?.length ? Math.round(content.length / 1000) : null

    const style =
      virtualRow != null
        ? {
            position: "absolute" as const,
            top: 0,
            left: 0,
            width: "100%",
            transform: `translateY(${virtualRow.start}px)`
          }
        : undefined

    return (
      <div
        key={key}
        ref={(el) => {
          if (virtualRow) viewerVirtualizer.measureElement(el)
          cardRefs.current[key] = el
        }}
        data-index={virtualRow?.index ?? idx}
        style={style}
        className={`${cardCls} shadow-sm ${isFocused ? 'ring-2 ring-primary ring-offset-2 ring-offset-surface' : ''}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-semibold leading-tight flex items-center gap-2">
              <span>{d.title || `${t('mediaPage.media', 'Media')} ${d.id}`}</span>
              <ChevronDown className="h-4 w-4 text-text-subtle" />
            </div>
            <div className="text-[11px] text-text-muted flex items-center gap-2 mt-1 flex-wrap">
              {isAllMode && <Tag>{t("mediaPage.stackPosition", "#{{num}}", { num: idx + 1 })}</Tag>}
              {d.type && <Tag>{String(d.type).toLowerCase()}</Tag>}
              {d.created_at && <span>{new Date(d.created_at).toLocaleString()}</span>}
              {(d as any)?.duration && <span>{t("mediaPage.duration", "{{value}}", { value: (d as any).duration })}</span>}
              {source && <span className="truncate max-w-[10rem]">{String(source)}</span>}
              {transcriptLen ? <span>{t("mediaPage.transcriptLength", "{{k}}k chars", { k: transcriptLen })}</span> : null}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {viewMode === "spread" && (
              <Tooltip title={t("mediaPage.unstackTooltip", "Remove from current comparison view")}>
                <Button size="small" onClick={() => toggleSelect(d.id)}>
                  {t("mediaPage.unstack", "Unstack")}
                </Button>
              </Tooltip>
            )}
            <Tooltip title={t('mediaPage.copyContentTooltip', 'Copy content to clipboard')}>
              <Button
                size="small"
                onClick={async () => {
                  const copyKey = `content-${key}`
                  try {
                    await navigator.clipboard.writeText(content)
                    setCopiedIds(prev => new Set(prev).add(copyKey))
                    setTimeout(() => setCopiedIds(prev => {
                      const next = new Set(prev)
                      next.delete(copyKey)
                      return next
                    }), 2000)
                    message.success(t('mediaPage.contentCopied', 'Content copied'))
                  } catch {
                    message.error(t('mediaPage.copyFailed', 'Copy failed'))
                  }
                }}
                icon={copiedIds.has(`content-${key}`)
                  ? (<Check className="w-4 h-4 text-success" />) as any
                  : (<CopyIcon className="w-4 h-4" />) as any}
              >
                {t("mediaPage.copyContentLabel", "Copy Content")}
              </Button>
            </Tooltip>
            <Tooltip title={t('mediaPage.copyAnalysisTooltip', 'Copy analysis to clipboard')}>
              <Button
                size="small"
                onClick={async () => {
                  const copyKey = `analysis-${key}`
                  try {
                    await navigator.clipboard.writeText(analysisText || "")
                    setCopiedIds(prev => new Set(prev).add(copyKey))
                    setTimeout(() => setCopiedIds(prev => {
                      const next = new Set(prev)
                      next.delete(copyKey)
                      return next
                    }), 2000)
                    message.success(t('mediaPage.analysisCopied', 'Analysis copied'))
                  } catch {
                    message.error(t('mediaPage.copyFailed', 'Copy failed'))
                  }
                }}
                icon={copiedIds.has(`analysis-${key}`)
                  ? (<Check className="w-4 h-4 text-success" />) as any
                  : (<CopyIcon className="w-4 h-4" />) as any}
              >
                {t("mediaPage.copyAnalysisLabel", "Copy Analysis")}
              </Button>
            </Tooltip>
          </div>
        </div>

        {hasFailed && (
          <Alert
            type="error"
            showIcon
            className="mt-3"
            title={t('mediaPage.loadFailed', 'Failed to load content')}
            action={
              <Button size="small" onClick={() => retryFetch(d.id)}>
                {t('mediaPage.retry', 'Retry')}
              </Button>
            }
          />
        )}

        <div className="mt-3 rounded border border-border p-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Typography.Text type="secondary">{t('mediaPage.mediaContent', 'Media Content')}</Typography.Text>
              {isLoadingDetail && <Spin size="small" />}
            </div>
            <Button
              size="small"
              type="text"
              icon={contentExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              onClick={() => {
                setContentExpandedIds((prev) => {
                  const next = collapseOthers ? new Set<string>() : new Set(prev)
                  if (next.has(key)) next.delete(key)
                  else next.add(key)
                  return next
                })
              }}
            >
              {contentExpanded ? t('mediaPage.collapse', 'Collapse') : t('mediaPage.expand', 'Expand')}
            </Button>
          </div>
          <div className="mt-2 prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap break-words text-sm text-text min-h-[8rem] leading-relaxed">
            {isLoadingDetail ? (
              <Skeleton active paragraph={{ rows: 3 }} title={false} />
            ) : content ? (
              contentShown
            ) : (
              <span className="text-text-muted">{t('mediaPage.noContent', 'No content available')}</span>
            )}
          </div>
        </div>

        <div className="mt-3 rounded border border-border p-2">
          <div className="flex items-center justify-between">
            <Typography.Text type="secondary">{t("mediaPage.analysis", "Analysis")}</Typography.Text>
            <Button
              size="small"
              type="text"
              icon={analysisExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              onClick={() => {
                setAnalysisExpandedIds((prev) => {
                  const next = collapseOthers ? new Set<string>() : new Set(prev)
                  if (next.has(key)) next.delete(key)
                  else next.add(key)
                  return next
                })
              }}
            >
              {analysisExpanded ? t('mediaPage.collapse', 'Collapse') : t('mediaPage.expand', 'Expand')}
            </Button>
          </div>
          <div className="mt-2 prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap break-words text-sm text-text leading-relaxed">
            {isLoadingDetail ? (
              <Skeleton active paragraph={{ rows: 2 }} title={false} />
            ) : analysisText ? (
              analysisShown
            ) : (
              <span className="text-text-muted">{t("mediaPage.noAnalysis", "No analysis available")}</span>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-[calc(100dvh-4rem)] mt-16 flex flex-col">
      <div className="shrink-0 mb-3">
        <div className="w-full">
          {/* Search row - always visible */}
          <div className="flex items-center gap-2 w-full mb-2">
            <Input
              ref={(node: any) => {
                searchInputRef.current = node?.input ?? node ?? null
              }}
              placeholder={t('mediaPage.searchPlaceholder', 'Search media (title/content)')}
              aria-label={
                t(
                  'mediaPage.searchPlaceholder',
                  'Search media (title/content)'
                ) as string
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onPressEnter={() => { setPage(1); refetch() }}
              className="flex-1"
            />
            <Button type="primary" onClick={() => { setPage(1); refetch() }}>{t('mediaPage.search', 'Search')}</Button>
            <Button onClick={() => { setQuery(""); setPage(1); refetch() }}>{t('mediaPage.clear', 'Clear')}</Button>
            {/* Collapsible filters toggle */}
            <button
              onClick={() => void setFiltersCollapsed(v => !v)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-text-muted hover:text-text hover:bg-surface2 rounded border border-border"
              aria-expanded={!filtersCollapsed}
              aria-controls="filter-section"
            >
              {filtersCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              {t('mediaPage.filters', 'Filters')}
              {activeFilterCount > 0 && (
                <>
                  <Tag color="blue" className="ml-1">{activeFilterCount}</Tag>
                  {filtersCollapsed && (
                    <span className="text-xs text-text-muted max-w-[180px] truncate">
                      {[
                        ...types.slice(0, 2),
                        types.length > 2 ? `+${types.length - 2}` : null,
                        ...keywordTokens.slice(0, 2),
                        keywordTokens.length > 2 ? `+${keywordTokens.length - 2}` : null,
                        includeContent ? t('mediaPage.content', 'Content') : null
                      ].filter(Boolean).join(', ')}
                    </span>
                  )}
                </>
              )}
            </button>
            {/* Selection count with progress bar */}
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-surface2 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-200 ${
                    selectedIds.length >= openAllLimit
                      ? 'bg-danger'
                      : selectedIds.length >= SELECTION_WARNING_THRESHOLD
                        ? 'bg-warn'
                        : 'bg-primary'
                  }`}
                  style={{ width: `${Math.min((selectedIds.length / openAllLimit) * 100, 100)}%` }}
                />
              </div>
              <span className={`text-xs whitespace-nowrap ${
                selectedIds.length >= openAllLimit
                  ? 'text-danger font-medium'
                  : selectedIds.length >= SELECTION_WARNING_THRESHOLD
                    ? 'text-warn font-medium'
                    : 'text-text-muted'
              }`}>
                {t('mediaPage.selectionCount', '{{selected}} / {{limit}} selected', {
                  selected: selectedIds.length,
                  limit: openAllLimit
                })}
                {selectedIds.length >= SELECTION_WARNING_THRESHOLD && selectedIds.length < openAllLimit && (
                  <span className="ml-1">({openAllLimit - selectedIds.length} {t('mediaPage.remaining', 'left')})</span>
                )}
              </span>
            </div>
          </div>
          {selectedIds.length > 5 && (
            <div
              className="mb-2 text-[11px] text-text-muted"
              data-testid="escape-double-tap-hint-inline"
            >
              {t(
                'mediaPage.escapeDoubleTapInlineHint',
                'Tip: press Escape twice quickly to clear large selections.'
              )}
            </div>
          )}

          {/* Collapsible filter section */}
          {!filtersCollapsed && (
            <div id="filter-section" className="flex items-center gap-2 w-full mb-2 animate-in fade-in duration-150">
              <Select
                mode="multiple"
                allowClear
                placeholder={t('mediaPage.types', 'Media types')}
                aria-label={
                  t('mediaPage.types', 'Media types') as string
                }
                className="min-w-[12rem]"
                value={types}
                onChange={(vals) => { setTypes(vals as string[]); setPage(1); refetch() }}
                options={availableTypes.map((t) => ({ label: t, value: t }))}
              />
              <Select
                mode="tags"
                allowClear
                showSearch
                placeholder={t('mediaPage.keywords', 'Keywords')}
                aria-label={
                  t('mediaPage.keywords', 'Keywords') as string
                }
                className="min-w-[12rem]"
                value={keywordTokens}
                onSearch={(txt) => loadKeywordSuggestions(txt)}
                onChange={(vals) => { setKeywordTokens(vals as string[]); setPage(1); refetch() }}
                options={keywordOptions.map((k) => ({ label: k, value: k }))}
              />
              <Checkbox checked={includeContent} onChange={(e) => { setIncludeContent(e.target.checked); setPage(1); refetch() }}>
                {t('mediaPage.content', 'Content')} {contentLoading && (<Spin size="small" className="ml-1" />)}
              </Checkbox>
              {activeFilterCount > 0 && (
                <Button size="small" onClick={() => { setTypes([]); setKeywordTokens([]); setIncludeContent(false); setPage(1); refetch() }}>
                  {t('mediaPage.resetFilters', 'Clear filters')}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Aria-live region for selection count announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {selectedIds.length} {t('mediaPage.itemsSelected', 'items selected')}, {openAllLimit - selectedIds.length} {t('mediaPage.remaining', 'remaining')}
      </div>

      <div className="flex flex-1 min-h-0 w-full gap-4 flex-col lg:flex-row">
        {!sidebarHidden && (
          <div className="w-full lg:w-1/3 border border-border rounded p-2 bg-surface h-full flex flex-col">
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
                  {t("mediaPage.resultsHint", "Click to stack, Shift+click for range")}
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
                    {listVirtualizer.getVirtualItems().map((virtualRow) => {
                      const item = allResults[virtualRow.index]
                      const isSelected = selectedIds.includes(item.id)
                      return (
                        <div
                          key={item.id}
                          data-index={virtualRow.index}
                          role="button"
                          aria-selected={isSelected}
                          tabIndex={0}
                          onClick={(e) => toggleSelect(item.id, e)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault()
                              toggleSelect(item.id)
                            }
                          }}
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            transform: `translateY(${virtualRow.start}px)`
                          }}
                          className={`px-3 py-2 border-b border-border cursor-pointer hover:bg-surface2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary focus-visible:bg-surface2 ${isSelected ? "bg-surface2 ring-2 ring-primary" : ""}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div
                              className="min-w-[44px] min-h-[44px] flex items-center justify-center cursor-pointer -ml-2 -mt-1"
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleSelect(item.id, e)
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
          </div>
        )}
        {/* Toggle bar between sidebar and viewer */}
        <div
          className={
            isMobileViewport
              ? "w-full h-8 flex-shrink-0"
              : "w-6 flex-shrink-0 h-full flex items-center"
          }
        >
          <button
            title={sidebarHidden ? t('mediaPage.showSidebar', 'Show sidebar') : t('mediaPage.hideSidebar', 'Hide sidebar')}
            aria-label={
              sidebarHidden
                ? (t('mediaPage.showSidebar', 'Show sidebar') as string)
                : (t('mediaPage.hideSidebar', 'Hide sidebar') as string)
            }
            onClick={() => setSidebarHidden((v) => !v)}
            className={
              isMobileViewport
                ? "h-8 w-full rounded bg-surface2 hover:bg-surface flex items-center justify-center text-xs font-semibold text-text-muted"
                : "h-full w-6 rounded bg-surface2 hover:bg-surface flex items-center justify-center text-xs font-semibold text-text-muted"
            }
          >
            {isMobileViewport
              ? sidebarHidden
                ? t('mediaPage.showSidebar', 'Show sidebar')
                : t('mediaPage.hideSidebar', 'Hide sidebar')
              : sidebarHidden
                ? '>>'
                : '<<'}
          </button>
        </div>
        <div
          ref={viewerRef}
          tabIndex={-1}
          className="flex-1 border border-border rounded p-2 bg-surface h-full flex flex-col min-w-0 relative focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <div className="sticky top-0 z-20 bg-surface pb-2 border-b border-border">
            {/* Row 1: View Controls */}
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <div className="text-sm font-medium text-text">{t('mediaPage.viewer', 'Viewer')}</div>
                  <div className="text-xs text-text-muted">
                    {viewMode === "spread"
                      ? t("mediaPage.viewerCount", "{{count}} open", { count: viewerItems.length })
                      : viewMode === "list"
                        ? t("mediaPage.viewerSingle", "Single item view")
                        : t("mediaPage.viewerAll", "All items (stacked)")}
                  </div>
                </div>
                {isMobileViewport ? (
                  <Tag data-testid="mobile-view-mode-badge">
                    {t("mediaPage.listMode", "Focus")}
                  </Tag>
                ) : (
                  <Tooltip title={t("mediaPage.spreadModeTooltip", "View selected items side-by-side for comparison")}>
                    <span>
                      <Radio.Group
                        value={viewMode}
                        onChange={(e) => {
                          const next = e.target.value as "spread" | "list" | "all"
                          setViewMode(next)
                          if (next === "list") {
                            const id = focusedId ?? selectedIds[0] ?? allResults[0]?.id
                            if (id != null) {
                              setFocusedId(id)
                              void ensureDetail(id)
                            }
                          } else if (next === "all") {
                            const ids = selectedIds.length > 0 ? selectedIds : allResults.slice(0, openAllLimit).map((m) => m.id)
                            setSelectedIds(ids)
                            ids.forEach((id) => void ensureDetail(id))
                          }
                        }}
                        optionType="button"
                        size="small"
                      >
                        <Tooltip title={t("mediaPage.spreadModeTooltip", "View selected items side-by-side for comparison")}>
                          <Radio.Button value="spread">
                            <LayoutGrid className="w-3.5 h-3.5 inline mr-1" />
                            {t("mediaPage.spreadMode", "Compare")}
                            {selectedIds.length > 0 && <span className="ml-1 text-xs opacity-70">({selectedIds.length})</span>}
                          </Radio.Button>
                        </Tooltip>
                        <Tooltip title={t("mediaPage.listModeTooltip", "View one item at a time with navigation")}>
                          <Radio.Button value="list">
                            <Focus className="w-3.5 h-3.5 inline mr-1" />
                            {t("mediaPage.listMode", "Focus")}
                            {selectedIds.length > 0 && (
                              <span className="ml-1 text-xs opacity-70">
                                ({focusedId != null ? selectedIds.indexOf(focusedId) + 1 : 1}/{selectedIds.length})
                              </span>
                            )}
                          </Radio.Button>
                        </Tooltip>
                        <Tooltip title={t("mediaPage.allModeTooltip", "View all selected items in a scrollable list")}>
                          <Radio.Button value="all">
                            <Rows3 className="w-3.5 h-3.5 inline mr-1" />
                            {t("mediaPage.allMode", "Stack")}
                            {selectedIds.length > 0 && <span className="ml-1 text-xs opacity-70">({selectedIds.length})</span>}
                          </Radio.Button>
                        </Tooltip>
                      </Radio.Group>
                    </span>
                  </Tooltip>
                )}
                {viewMode === "list" && (
                  <Select
                    size="small"
                    className="min-w-[12rem]"
                    placeholder={t("mediaPage.pickItem", "Pick an item")}
                    value={focusedId ?? undefined}
                    onChange={(val) => {
                      setFocusedId(val as any)
                      void ensureDetail(val as any)
                    }}
                    options={allResults.map((m, idx) => ({
                      label: `${idx + 1}. ${m.title || `Media ${m.id}`}`,
                      value: m.id
                    }))}
                  />
                )}
                <div className="h-5 w-px bg-border mx-1" />
                <Radio.Group
                  size="small"
                  value={orientation}
                  onChange={(e) => {
                    void setOrientation(e.target.value)
                  }}
                  options={[
                    { label: t('mediaPage.vertical', 'Vertical'), value: 'vertical' },
                    { label: t('mediaPage.horizontal', 'Horizontal'), value: 'horizontal' }
                  ]}
                  optionType="button"
                />
                <Dropdown
                  menu={{
                    items: [
                      {
                        key: 'autoViewMode',
                        label: (
                          <div className="flex items-center justify-between gap-4">
                            <span>{t("mediaPage.autoViewMode", "Auto-select view mode")}</span>
                            <Switch size="small" checked={autoViewMode} onChange={(v) => void setAutoViewModeSetting(v)} />
                          </div>
                        )
                      },
                      {
                        key: 'collapseOthers',
                        label: (
                          <div className="flex items-center justify-between gap-4">
                            <span>{t("mediaPage.collapseOthers", "Collapse others on expand")}</span>
                            <Switch size="small" checked={collapseOthers} onChange={setCollapseOthers} />
                          </div>
                        )
                      },
                      { type: 'divider' },
                      {
                        key: 'openAll',
                        label: `${t("mediaPage.openAll", "Review all on page")} (${Math.min(allResults.length, openAllLimit)})`,
                        onClick: openAllCurrent,
                        disabled: allResults.length === 0
                      },
                      { type: 'divider' },
                      {
                        key: 'showGuide',
                        label: t("mediaPage.showGuide", "Show getting started guide"),
                        onClick: () => setHelpDismissed(false)
                      },
                      { type: 'divider' },
                      {
                        key: 'clearSession',
                        label: t("mediaPage.clearSession", "Clear review session"),
                        danger: true,
                        onClick: async () => {
                          // Clear all persisted review state
                          await clearSetting(MEDIA_REVIEW_SELECTION_SETTING)
                          await clearSetting(MEDIA_REVIEW_FOCUSED_ID_SETTING)
                          await clearSetting(MEDIA_REVIEW_VIEW_MODE_SETTING)
                          await clearSetting(MEDIA_REVIEW_ORIENTATION_SETTING)
                          await clearSetting(MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING)
                          // Reset local state
                          setSelectedIds([])
                          setFocusedId(null)
                          setDetails({})
                          setQuery("")
                          setTypes([])
                          setKeywordTokens([])
                          message.success(t("mediaPage.sessionCleared", "Review session cleared"))
                        }
                      }
                    ]
                  }}
                  trigger={['click']}
                >
                  <Button size="small" icon={<Settings2 className="w-3.5 h-3.5" />}>
                    {t("mediaPage.viewerOptions", "Options")}
                    <ChevronDown className="w-3 h-3 ml-1" />
                  </Button>
                </Dropdown>
              </div>
            </div>
            {/* Row 2: Navigation & Content Actions */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Tooltip title={t("mediaPage.prevItemTooltip", "Previous item (←)")}>
                  <Button
                    size="small"
                    onClick={() => goRelative(-1)}
                    disabled={focusIndex <= 0}
                    icon={<ChevronLeft className="w-4 h-4" />}
                  >
                    {t("mediaPage.prevItem", "Prev")}
                  </Button>
                </Tooltip>
                <span className="text-xs text-text-muted min-w-[5rem] text-center">
                  {focusIndex >= 0
                    ? t("mediaPage.itemPosition", "Item {{current}} of {{total}}", { current: focusIndex + 1, total: allResults.length })
                    : t("mediaPage.noItemSelected", "No item selected")}
                </span>
                <Tooltip title={t("mediaPage.nextItemTooltip", "Next item (→)")}>
                  <Button
                    size="small"
                    onClick={() => goRelative(1)}
                    disabled={focusIndex < 0 || focusIndex >= allResults.length - 1}
                    icon={<ChevronRight className="w-4 h-4" />}
                    iconPlacement="end"
                  >
                    {t("mediaPage.nextItem", "Next")}
                  </Button>
                </Tooltip>
              </div>
              <div className="flex items-center gap-2">
                <Dropdown
                  menu={{
                    items: [
                      { key: 'expandContent', label: t("mediaPage.expandAllContent", "Expand all content"), onClick: expandAllContent },
                      { key: 'collapseContent', label: t("mediaPage.collapseAllContent", "Collapse all content"), onClick: collapseAllContent },
                      { type: 'divider' },
                      { key: 'expandAnalysis', label: t("mediaPage.expandAllAnalysis", "Expand all analysis"), onClick: expandAllAnalysis },
                      { key: 'collapseAnalysis', label: t("mediaPage.collapseAllAnalysis", "Collapse all analysis"), onClick: collapseAllAnalysis }
                    ]
                  }}
                  trigger={['click']}
                >
                  <Button size="small" icon={<Layers className="w-3.5 h-3.5" />}>
                    {t("mediaPage.expandAllDropdown", "Expand/Collapse")}
                    <ChevronDown className="w-3 h-3 ml-1" />
                  </Button>
                </Dropdown>
                {selectedIds.length === 2 && (
                  <Button
                    size="small"
                    onClick={() => void handleCompareContent()}
                  >
                    {t('mediaPage.compareContent', 'Compare content')}
                  </Button>
                )}
                {selectedIds.length > 0 && (
                  <Tooltip
                    title={t('mediaPage.chatSelectionTooltip', {
                      defaultValue: 'Start a media-scoped RAG chat using the selected items.'
                    })}
                  >
                    <Button
                      size="small"
                      icon={<MessageSquare className="w-3.5 h-3.5" />}
                      onClick={handleChatAboutSelection}
                    >
                      {t('mediaPage.chatSelectionAction', {
                        defaultValue: 'Chat about selection ({{count}})',
                        count: selectedIds.length
                      })}
                    </Button>
                  </Tooltip>
                )}
                <Button
                  size="small"
                  shape="circle"
                  type="text"
                  onClick={() => setHelpModalOpen(true)}
                  aria-label={
                    t(
                      "mediaPage.viewerHelpLabel",
                      "Multi-Item Review keyboard shortcuts"
                    ) as string
                  }
                  className="text-text-subtle hover:text-text"
                >
                  ?
                </Button>
              </div>
            </div>
            {selectedIds.length > 0 && (
              <div className="mt-2 flex items-center gap-2 overflow-x-auto text-xs text-text-muted">
                <span className="font-medium">{t("mediaPage.openMiniMap", "Open items")}</span>
                {selectedIds.length <= MINIMAP_COLLAPSE_THRESHOLD ? (
                  // Horizontal button bar for ≤8 items
                  selectedIds.map((id, idx) => {
                    const d = details[id]
                    const isLoading = detailLoading[id]
                    const hasFailed = failedIds.has(id)
                    return (
                      <Button
                        key={String(id)}
                        size="small"
                        type={focusedId === id ? "primary" : "default"}
                        danger={hasFailed}
                        onClick={() => {
                          setFocusedId(id)
                          scrollToCard(id)
                        }}
                        className={isLoading ? "animate-pulse" : ""}
                      >
                        {isLoading && <Spin size="small" className="mr-1" />}
                        {idx + 1}. {d?.title || `${t('mediaPage.media', 'Media')} ${id}`} {d?.type ? `(${String(d.type)})` : ""}
                      </Button>
                    )
                  })
                ) : (
                  // Dropdown for >8 items
                  <Dropdown
                    menu={{
                      items: selectedIds.map((id, idx) => {
                        const d = details[id]
                        const isLoading = detailLoading[id]
                        const hasFailed = failedIds.has(id)
                        return {
                          key: String(id),
                          label: (
                            <span className={isLoading ? "animate-pulse" : ""}>
                              {isLoading && <Spin size="small" className="mr-1" />}
                              {idx + 1}. {d?.title || `${t('mediaPage.media', 'Media')} ${id}`} {d?.type ? `(${String(d.type)})` : ""}
                            </span>
                          ),
                          danger: hasFailed,
                          onClick: () => {
                            setFocusedId(id)
                            scrollToCard(id)
                          }
                        }
                      }),
                      selectedKeys: focusedId != null ? [String(focusedId)] : []
                    }}
                    trigger={['click']}
                  >
                    <Button size="small">
                      {t("mediaPage.jumpToItem", "Jump to item")} ({selectedIds.length})
                      <ChevronDown className="w-3 h-3 ml-1" />
                    </Button>
                  </Dropdown>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-1 min-h-0 gap-3">
            <div className="flex-1 flex flex-col min-h-0">
              {viewerItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                  {!helpDismissedLoading && !helpDismissed ? (
                    <div className="max-w-md">
                      <HelpCircle className="w-10 h-10 mx-auto mb-4 text-primary" />
                      <h3 className="text-lg font-medium text-text mb-3">
                        {t('mediaPage.firstUseTitle', 'Quick Guide: Multi-Item Review')}
                      </h3>
                      <ol className="text-left text-sm text-text-muted space-y-3 mb-6">
                        <li className="flex gap-2">
                          <span className="font-semibold text-primary">1.</span>
                          <span>
                            <strong>{t('mediaPage.firstUseStep1', 'Select items')}</strong> — {t('mediaPage.firstUseStep1Desc', 'Click items in the left panel to add them to your viewer.')}
                          </span>
                        </li>
                        <li className="flex gap-2">
                          <span className="font-semibold text-primary">2.</span>
                          <span>
                            <strong>{t('mediaPage.firstUseStep2', 'Choose a view')}</strong> — {t('mediaPage.firstUseStep2Desc', 'Use "Compare" for side-by-side, "Focus" for one at a time, or "Stack" to see all.')}
                          </span>
                        </li>
                        <li className="flex gap-2">
                          <span className="font-semibold text-primary">3.</span>
                          <span>
                            <strong>{t('mediaPage.firstUseStep3', 'Navigate')}</strong> — {t('mediaPage.firstUseStep3Desc', 'Use Prev/Next buttons or keyboard (Tab + Enter) to move through items.')}
                          </span>
                        </li>
                      </ol>
                      <Button type="primary" onClick={() => setHelpDismissed(true)}>
                        {t('mediaPage.gotIt', 'Got it')}
                      </Button>
                    </div>
                  ) : (
                    <div className="text-text-muted">
                      <Empty
                        description={t('mediaPage.selectItemsHint', 'Select items on the left to view here.')}
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div
                    ref={viewMode === "all" ? undefined : viewerParentRef}
                    className={`relative flex-1 min-h-0 ${viewMode === "all" ? "overflow-visible" : "overflow-auto"}`}
                  >
                    {viewMode === "all" ? (
                      <div className={orientation === 'horizontal' ? 'flex flex-wrap gap-3' : 'space-y-3'}>
                        {viewerItems.map((d, idx) => renderCard(d, idx, { isAllMode: true }))}
                      </div>
                    ) : (
                      <div
                        style={{
                          height: `${viewerVirtualizer.getTotalSize()}px`,
                          position: "relative"
                        }}
                      >
                        {viewerVirtualizer.getVirtualItems().map((virtualRow: VirtualItem) => {
                          const d = viewMode === "spread" ? viewerItems[virtualRow.index] : viewMode === "list" ? focusedDetail : viewerItems[virtualRow.index]
                          if (!d) return null
                          return renderCard(d, virtualRow.index, { virtualRow })
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Keyboard shortcuts modal (accessible on touch devices) */}
      <Modal
        title={t('mediaPage.keyboardShortcuts', 'Keyboard Shortcuts')}
        open={helpModalOpen}
        onCancel={() => setHelpModalOpen(false)}
        footer={null}
        width={400}
      >
        <div className="space-y-3 text-sm">
          <div className="font-medium text-text-muted mb-2">{t('mediaPage.navigationShortcuts', 'Navigation')}</div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutNextItem', 'Next item')}</span>
            <span><kbd className="px-2 py-1 bg-surface2 rounded text-xs">j</kbd> / <kbd className="px-2 py-1 bg-surface2 rounded text-xs">↓</kbd></span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutPrevItem', 'Previous item')}</span>
            <span><kbd className="px-2 py-1 bg-surface2 rounded text-xs">k</kbd> / <kbd className="px-2 py-1 bg-surface2 rounded text-xs">↑</kbd></span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutToggleExpand', 'Toggle content expand')}</span>
            <kbd className="px-2 py-1 bg-surface2 rounded text-xs">o</kbd>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutFocusSearch', 'Focus search')}</span>
            <kbd className="px-2 py-1 bg-surface2 rounded text-xs">/</kbd>
          </div>
          <div className="font-medium text-text-muted mt-4 mb-2">{t('mediaPage.selectionShortcuts', 'Selection')}</div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutSelectAll', 'Select all visible')}</span>
            <span><kbd className="px-2 py-1 bg-surface2 rounded text-xs">Ctrl</kbd>+<kbd className="px-2 py-1 bg-surface2 rounded text-xs">A</kbd></span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutClearSelection', 'Clear selection')}</span>
            <span><kbd className="px-2 py-1 bg-surface2 rounded text-xs">Esc</kbd> <span className="text-text-muted">×2</span></span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border">
            <span>{t('mediaPage.shortcutRangeSelect', 'Range selection')}</span>
            <span><kbd className="px-2 py-1 bg-surface2 rounded text-xs">Shift</kbd>+{t('mediaPage.click', 'Click')}</span>
          </div>
        </div>
      </Modal>

      <DiffViewModal
        open={compareDiffOpen}
        onClose={() => setCompareDiffOpen(false)}
        leftText={compareLeftText}
        rightText={compareRightText}
        leftLabel={compareLeftLabel}
        rightLabel={compareRightLabel}
      />
    </div>
  )
}

export default MediaReviewPage
