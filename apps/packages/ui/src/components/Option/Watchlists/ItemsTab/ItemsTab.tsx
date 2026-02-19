import React, { useCallback, useEffect, useMemo, useState } from "react"
import {
  Checkbox,
  Button,
  Empty,
  Input,
  Modal,
  Pagination,
  Select,
  Segmented,
  Space,
  Spin,
  Tag,
  Tooltip,
  message
} from "antd"
import DOMPurify from "dompurify"
import { CheckCircle2, ExternalLink, HelpCircle, RefreshCw, Rss, Sun } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"
import {
  fetchScrapedItems,
  fetchWatchlistSources,
  updateScrapedItem
} from "@/services/watchlists"
import type { FetchItemsParams } from "@/services/watchlists"
import { useWatchlistsStore } from "@/store/watchlists"
import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"
import { formatRelativeTime } from "@/utils/dateFormatters"
import {
  extractImageUrl,
  ITEM_PAGE_SIZE_OPTIONS,
  filterSourcesForReader,
  loadPersistedItemPageSize,
  loadPersistedItemsViewPresets,
  type PersistedItemsViewPreset,
  persistItemPageSize,
  persistItemsViewPresets,
  resolveSelectedItemId,
  SOURCE_LOAD_MAX_ITEMS,
  SOURCE_LOAD_PAGE_SIZE,
  stripHtmlToText
} from "./items-utils"

const { Search } = Input

type ReaderStatusFilter = "all" | "ingested" | "filtered"
type SmartFeedFilter = "all" | "today" | "unread" | "reviewed"
type BatchReviewScope = "selected" | "page" | "allFiltered"
type ItemsViewPreset = Omit<PersistedItemsViewPreset, "smartFilter" | "statusFilter"> & {
  smartFilter: SmartFeedFilter
  statusFilter: ReaderStatusFilter
}

const normalizeSmartFilter = (value: string): SmartFeedFilter => {
  if (value === "today" || value === "unread" || value === "reviewed") return value
  return "all"
}

const normalizeStatusFilter = (value: string): ReaderStatusFilter => {
  if (value === "ingested" || value === "filtered") return value
  return "all"
}

const startOfTodayIso = (): string => {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return now.toISOString()
}

const renderItemTimestamp = (item: ScrapedItem, t: TFunction) => {
  if (item.published_at) return formatRelativeTime(item.published_at, t)
  return formatRelativeTime(item.created_at, t)
}

const getItemPreviewText = (item: ScrapedItem): string | null => {
  const raw = item.summary || item.content || ""
  const text = stripHtmlToText(raw)
  if (!text) return null
  if (text.length <= 160) return text
  return `${text.slice(0, 159)}…`
}

const isLikelyHtml = (value: string): boolean => /<\/?[a-z][\s\S]*>/i.test(value)

const formatReaderDate = (value: string | null | undefined): string => {
  if (!value) return ""
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ""
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(parsed)
}

const getDomain = (url: string | null | undefined): string | null => {
  if (!url) return null
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tagName = target.tagName.toLowerCase()
  if (tagName === "input" || tagName === "textarea" || tagName === "select") {
    return true
  }
  if (target.closest("[contenteditable='true']")) return true
  if (target.closest(".ant-select-dropdown")) return true
  return false
}

export const ItemsTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])
  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const openSourceForm = useWatchlistsStore((s) => s.openSourceForm)
  const [sources, setSources] = useState<WatchlistSource[]>([])
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const [sourceSearch, setSourceSearch] = useState("")
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null)
  const [items, setItems] = useState<ScrapedItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [itemsTotal, setItemsTotal] = useState(0)
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [itemsSearch, setItemsSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<ReaderStatusFilter>("all")
  const [smartFilter, setSmartFilter] = useState<SmartFeedFilter>("all")
  const [itemsPage, setItemsPage] = useState(1)
  const [itemsPageSize, setItemsPageSize] = useState<number>(() =>
    loadPersistedItemPageSize(
      typeof window !== "undefined" ? window.localStorage : undefined
    )
  )
  const [updatingItemId, setUpdatingItemId] = useState<number | null>(null)
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([])
  const [batchReviewScope, setBatchReviewScope] = useState<BatchReviewScope | null>(null)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [viewPresets, setViewPresets] = useState<ItemsViewPreset[]>(() =>
    loadPersistedItemsViewPresets(
      typeof window !== "undefined" ? window.localStorage : undefined
    ).map((preset) => ({
      ...preset,
      smartFilter: normalizeSmartFilter(preset.smartFilter),
      statusFilter: normalizeStatusFilter(preset.statusFilter)
    }))
  )
  const [activePresetId, setActivePresetId] = useState<string | null>(null)
  const [saveViewModalOpen, setSaveViewModalOpen] = useState(false)
  const [newViewName, setNewViewName] = useState("")
  const [smartCounts, setSmartCounts] = useState<Record<SmartFeedFilter, number>>({
    all: 0,
    today: 0,
    unread: 0,
    reviewed: 0
  })

  const sourceNameById = useMemo(
    () => new Map<number, string>(sources.map((source) => [source.id, source.name])),
    [sources]
  )

  const selectedSourceName = useMemo(() => {
    if (selectedSourceId === null) {
      return t("watchlists:items.allFeeds", "All Feeds")
    }
    return (
      sourceNameById.get(selectedSourceId) ||
      t("watchlists:items.unknownSource", "Unknown source")
    )
  }, [selectedSourceId, sourceNameById, t])

  const filteredSources = useMemo(
    () => filterSourcesForReader(sources, sourceSearch),
    [sources, sourceSearch]
  )

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedItemId) || null,
    [items, selectedItemId]
  )

  const selectedItemRawBody = selectedItem
    ? selectedItem.content || selectedItem.summary || ""
    : ""

  const selectedItemBodyIsHtml = isLikelyHtml(selectedItemRawBody)

  const selectedItemBodyHtml = useMemo(() => {
    if (!selectedItemRawBody) return ""
    return DOMPurify.sanitize(selectedItemRawBody, { USE_PROFILES: { html: true } })
  }, [selectedItemRawBody])

  const selectedItemPreviewImage = useMemo(
    () => extractImageUrl(selectedItem?.content || selectedItem?.summary || null),
    [selectedItem]
  )

  const itemImagesById = useMemo(() => {
    const map = new Map<number, string>()
    for (const item of items) {
      const image = extractImageUrl(item.content || item.summary)
      if (image) map.set(item.id, image)
    }
    return map
  }, [items])

  const itemPreviewById = useMemo(() => {
    const map = new Map<number, string>()
    for (const item of items) {
      const preview = getItemPreviewText(item)
      if (preview) map.set(item.id, preview)
    }
    return map
  }, [items])

  const currentUnreadCount = useMemo(
    () => smartCounts.unread,
    [smartCounts.unread]
  )

  const searchQuery = itemsSearch.trim()

  const buildBaseFilterParams = useCallback(
    (overrides: Partial<FetchItemsParams> = {}): FetchItemsParams => {
      const params: FetchItemsParams = {
        source_id: selectedSourceId ?? undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        q: searchQuery || undefined,
        ...overrides
      }

      if (smartFilter === "today") {
        params.since = startOfTodayIso()
      } else if (smartFilter === "unread") {
        params.reviewed = false
      } else if (smartFilter === "reviewed") {
        params.reviewed = true
      }

      return params
    },
    [searchQuery, selectedSourceId, smartFilter, statusFilter]
  )

  const loadSources = useCallback(async () => {
    setSourcesLoading(true)
    try {
      const loaded: WatchlistSource[] = []
      let page = 1

      while (loaded.length < SOURCE_LOAD_MAX_ITEMS) {
        const response = await fetchWatchlistSources({
          page,
          size: SOURCE_LOAD_PAGE_SIZE
        })
        const batch = Array.isArray(response.items) ? response.items : []
        loaded.push(...batch)
        if (
          batch.length < SOURCE_LOAD_PAGE_SIZE ||
          loaded.length >= (response.total || 0)
        ) {
          break
        }
        page += 1
      }

      setSources(loaded)
    } catch (error) {
      console.error("Failed to load watchlist sources:", error)
      message.error(t("watchlists:items.sourcesError", "Failed to load sources"))
    } finally {
      setSourcesLoading(false)
    }
  }, [t])

  const loadItems = useCallback(async () => {
    setItemsLoading(true)
    try {
      const response = await fetchScrapedItems(
        buildBaseFilterParams({
          page: itemsPage,
          size: itemsPageSize
        })
      )
      const nextItems = Array.isArray(response.items) ? response.items : []
      setItems(nextItems)
      setItemsTotal(response.total || nextItems.length)
      setSelectedItemId((prev) => resolveSelectedItemId(prev, nextItems))
    } catch (error) {
      console.error("Failed to load watchlist items:", error)
      message.error(t("watchlists:items.fetchError", "Failed to load feed items"))
      setItems([])
      setItemsTotal(0)
      setSelectedItemId(null)
    } finally {
      setItemsLoading(false)
    }
  }, [buildBaseFilterParams, itemsPage, itemsPageSize, t])

  const loadSmartCounts = useCallback(async () => {
    try {
      const base: FetchItemsParams = {
        source_id: selectedSourceId ?? undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        q: searchQuery || undefined,
        page: 1,
        size: 1
      }

      const [allRes, todayRes, unreadRes, reviewedRes] = await Promise.all([
        fetchScrapedItems(base),
        fetchScrapedItems({ ...base, since: startOfTodayIso() }),
        fetchScrapedItems({ ...base, reviewed: false }),
        fetchScrapedItems({ ...base, reviewed: true })
      ])

      setSmartCounts({
        all: allRes.total || 0,
        today: todayRes.total || 0,
        unread: unreadRes.total || 0,
        reviewed: reviewedRes.total || 0
      })
    } catch (error) {
      console.error("Failed to load smart feed counts:", error)
    }
  }, [searchQuery, selectedSourceId, statusFilter])

  const refreshItemsView = useCallback(() => {
    void loadSources()
    void loadItems()
    void loadSmartCounts()
  }, [loadItems, loadSmartCounts, loadSources])

  useEffect(() => {
    void loadSources()
  }, [loadSources])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  useEffect(() => {
    void loadSmartCounts()
  }, [loadSmartCounts])

  useEffect(() => {
    persistItemPageSize(
      typeof window !== "undefined" ? window.localStorage : undefined,
      itemsPageSize
    )
  }, [itemsPageSize])

  useEffect(() => {
    persistItemsViewPresets(
      typeof window !== "undefined" ? window.localStorage : undefined,
      viewPresets
    )
  }, [viewPresets])

  useEffect(() => {
    const visibleIds = new Set(items.map((item) => item.id))
    setSelectedItemIds((prev) => {
      if (prev.length === 0) return prev
      const filtered = prev.filter((id) => visibleIds.has(id))
      return filtered.length === prev.length ? prev : filtered
    })
  }, [items])

  useEffect(() => {
    setSelectedItemIds((prev) => (prev.length === 0 ? prev : []))
  }, [selectedSourceId, smartFilter, statusFilter, searchQuery, itemsPage])

  useEffect(() => {
    const matchingPreset = viewPresets.find(
      (preset) =>
        preset.sourceId === selectedSourceId &&
        preset.smartFilter === smartFilter &&
        preset.statusFilter === statusFilter &&
        preset.searchQuery === searchQuery
    )
    const nextId = matchingPreset?.id ?? null
    setActivePresetId((prev) => (prev === nextId ? prev : nextId))
  }, [searchQuery, selectedSourceId, smartFilter, statusFilter, viewPresets])

  const handleSourceSelect = (sourceId: number | null) => {
    setSelectedSourceId(sourceId)
    setItemsPage(1)
  }

  const handleStatusChange = (nextStatus: ReaderStatusFilter) => {
    setStatusFilter(nextStatus)
    setItemsPage(1)
  }

  const handleSmartFilterChange = (nextFilter: SmartFeedFilter) => {
    setSmartFilter(nextFilter)
    setItemsPage(1)
  }

  const handleToggleReviewed = async (item: ScrapedItem) => {
    setUpdatingItemId(item.id)
    try {
      const updated = await updateScrapedItem(item.id, { reviewed: !item.reviewed })
      setItems((prev) =>
        prev.map((entry) => (entry.id === updated.id ? updated : entry))
      )
      message.success(
        updated.reviewed
          ? t("watchlists:items.markedReviewed", "Marked as reviewed")
          : t("watchlists:items.markedUnreviewed", "Marked as unreviewed")
      )
      void loadSmartCounts()
    } catch (error) {
      console.error("Failed to update watchlist item:", error)
      message.error(t("watchlists:items.updateError", "Failed to update item"))
    } finally {
      setUpdatingItemId(null)
    }
  }

  const pageItemIds = useMemo(() => items.map((item) => item.id), [items])

  const pageUnreviewedItemIds = useMemo(
    () => items.filter((item) => !item.reviewed).map((item) => item.id),
    [items]
  )

  const selectedItemIdSet = useMemo(
    () => new Set(selectedItemIds),
    [selectedItemIds]
  )

  const selectedUnreviewedItemIds = useMemo(
    () =>
      items
        .filter((item) => selectedItemIdSet.has(item.id) && !item.reviewed)
        .map((item) => item.id),
    [items, selectedItemIdSet]
  )

  const allPageItemsSelected = useMemo(
    () => pageItemIds.length > 0 && pageItemIds.every((id) => selectedItemIdSet.has(id)),
    [pageItemIds, selectedItemIdSet]
  )

  const somePageItemsSelected = useMemo(
    () => !allPageItemsSelected && pageItemIds.some((id) => selectedItemIdSet.has(id)),
    [allPageItemsSelected, pageItemIds, selectedItemIdSet]
  )

  const pageSizeOptions = useMemo(
    () =>
      ITEM_PAGE_SIZE_OPTIONS.map((value) => ({
        label: t("common:pagination.itemsPerPage", "{{count}} / page", { count: value }),
        value
      })),
    [t]
  )

  const viewPresetOptions = useMemo(
    () =>
      viewPresets.map((preset) => ({
        label: preset.name,
        value: preset.id
      })),
    [viewPresets]
  )

  const handleToggleItemSelected = useCallback((itemId: number, checked: boolean) => {
    setSelectedItemIds((prev) => {
      if (checked) return Array.from(new Set([...prev, itemId]))
      return prev.filter((id) => id !== itemId)
    })
  }, [])

  const handleToggleSelectPage = useCallback((checked: boolean) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev)
      if (checked) {
        pageItemIds.forEach((id) => next.add(id))
      } else {
        pageItemIds.forEach((id) => next.delete(id))
      }
      return Array.from(next)
    })
  }, [pageItemIds])

  const markItemsReviewed = useCallback(async (
    itemIds: number[],
    scope: BatchReviewScope
  ): Promise<void> => {
    const uniqueIds = Array.from(new Set(itemIds))
    if (uniqueIds.length === 0) return

    setBatchReviewScope(scope)
    try {
      const successfulIds: number[] = []
      let failedCount = 0
      const chunkSize = 20

      for (let index = 0; index < uniqueIds.length; index += chunkSize) {
        const chunk = uniqueIds.slice(index, index + chunkSize)
        const results = await Promise.allSettled(
          chunk.map((itemId) => updateScrapedItem(itemId, { reviewed: true }))
        )

        results.forEach((result, offset) => {
          if (result.status === "fulfilled") {
            const updatedId =
              typeof result.value?.id === "number"
                ? result.value.id
                : chunk[offset]
            successfulIds.push(updatedId)
          } else {
            failedCount += 1
          }
        })
      }

      if (successfulIds.length > 0) {
        const successfulIdSet = new Set(successfulIds)
        setItems((prev) =>
          prev.map((item) =>
            successfulIdSet.has(item.id)
              ? { ...item, reviewed: true }
              : item
          )
        )
        setSelectedItemIds((prev) => prev.filter((id) => !successfulIdSet.has(id)))
      }

      if (successfulIds.length > 0 && failedCount === 0) {
        message.success(
          t("watchlists:items.batch.completed", "Marked {{count}} item{{plural}} as reviewed.", {
            count: successfulIds.length,
            plural: successfulIds.length === 1 ? "" : "s"
          })
        )
      } else if (successfulIds.length > 0) {
        message.warning(
          t(
            "watchlists:items.batch.partial",
            "Marked {{success}} item{{successPlural}} as reviewed; {{failed}} failed.",
            {
              success: successfulIds.length,
              successPlural: successfulIds.length === 1 ? "" : "s",
              failed: failedCount
            }
          )
        )
      } else {
        message.error(t("watchlists:items.batch.failed", "Failed to mark items as reviewed."))
      }

      await Promise.all([loadItems(), loadSmartCounts()])
    } catch (error) {
      console.error("Failed to apply batch reviewed update:", error)
      message.error(t("watchlists:items.batch.failed", "Failed to mark items as reviewed."))
    } finally {
      setBatchReviewScope(null)
    }
  }, [loadItems, loadSmartCounts, t])

  const openBatchConfirm = useCallback((
    scope: BatchReviewScope,
    itemIds: number[],
    title: string
  ) => {
    if (itemIds.length === 0) return
    Modal.confirm({
      title,
      content: t(
        "watchlists:items.batch.confirmDescription",
        "This will mark {{count}} item{{plural}} as reviewed.",
        {
          count: itemIds.length,
          plural: itemIds.length === 1 ? "" : "s"
        }
      ),
      okText: t("watchlists:items.markReviewed", "Mark as reviewed"),
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => markItemsReviewed(itemIds, scope)
    })
  }, [markItemsReviewed, t])

  const handleMarkSelectedReviewed = useCallback(() => {
    if (selectedUnreviewedItemIds.length === 0) {
      message.info(
        t("watchlists:items.batch.noSelected", "Select one or more items to review.")
      )
      return
    }

    openBatchConfirm(
      "selected",
      selectedUnreviewedItemIds,
      t("watchlists:items.batch.confirmSelectedTitle", "Mark selected items as reviewed?")
    )
  }, [openBatchConfirm, selectedUnreviewedItemIds, t])

  const handleMarkPageReviewed = useCallback(() => {
    if (pageUnreviewedItemIds.length === 0) {
      message.info(
        t("watchlists:items.batch.noPage", "All items on this page are already reviewed.")
      )
      return
    }

    openBatchConfirm(
      "page",
      pageUnreviewedItemIds,
      t("watchlists:items.batch.confirmPageTitle", "Mark this page as reviewed?")
    )
  }, [openBatchConfirm, pageUnreviewedItemIds, t])

  const collectAllFilteredUnreadItemIds = useCallback(async (): Promise<number[]> => {
    const allIds: number[] = []
    const lookupPageSize = 200
    let page = 1

    while (true) {
      const response = await fetchScrapedItems(
        buildBaseFilterParams({
          reviewed: false,
          page,
          size: lookupPageSize
        })
      )
      const batch = Array.isArray(response.items) ? response.items : []
      allIds.push(...batch.map((item) => item.id))
      const total = response.total || allIds.length
      if (batch.length < lookupPageSize || allIds.length >= total) {
        break
      }
      page += 1
    }

    return allIds
  }, [buildBaseFilterParams])

  const handleMarkAllFilteredReviewed = useCallback(async () => {
    try {
      const candidateIds = await collectAllFilteredUnreadItemIds()
      if (candidateIds.length === 0) {
        message.info(
          t(
            "watchlists:items.batch.noFiltered",
            "No matching unread items to review."
          )
        )
        return
      }

      openBatchConfirm(
        "allFiltered",
        candidateIds,
        t("watchlists:items.batch.confirmAllFilteredTitle", "Mark all filtered items as reviewed?")
      )
    } catch (error) {
      console.error("Failed to collect filtered unread item ids:", error)
      message.error(t("watchlists:items.batch.failed", "Failed to mark items as reviewed."))
    }
  }, [collectAllFilteredUnreadItemIds, openBatchConfirm, t])

  const applyViewPreset = useCallback((presetId: string) => {
    const preset = viewPresets.find((candidate) => candidate.id === presetId)
    if (!preset) return
    setSelectedSourceId(preset.sourceId)
    setSmartFilter(preset.smartFilter)
    setStatusFilter(preset.statusFilter)
    setItemsSearch(preset.searchQuery)
    setItemsPage(1)
    setActivePresetId(preset.id)
  }, [viewPresets])

  const saveCurrentView = useCallback(() => {
    if (activePresetId) {
      setViewPresets((prev) =>
        prev.map((preset) =>
          preset.id === activePresetId
            ? {
                ...preset,
                sourceId: selectedSourceId,
                smartFilter,
                statusFilter,
                searchQuery
              }
            : preset
        )
      )
      message.success(t("watchlists:items.savedViews.updated", "Saved view updated."))
      return
    }

    setNewViewName(
      t("watchlists:items.savedViews.defaultName", "My view")
    )
    setSaveViewModalOpen(true)
  }, [activePresetId, searchQuery, selectedSourceId, smartFilter, statusFilter, t])

  const createViewPreset = useCallback(() => {
    const trimmedName = newViewName.trim()
    if (!trimmedName) {
      message.error(
        t("watchlists:items.savedViews.nameRequired", "Saved view name is required.")
      )
      return
    }
    const newPreset: ItemsViewPreset = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      name: trimmedName,
      sourceId: selectedSourceId,
      smartFilter,
      statusFilter,
      searchQuery
    }
    setViewPresets((prev) => [newPreset, ...prev])
    setActivePresetId(newPreset.id)
    setSaveViewModalOpen(false)
    setNewViewName("")
    message.success(t("watchlists:items.savedViews.created", "Saved view created."))
  }, [newViewName, searchQuery, selectedSourceId, smartFilter, statusFilter, t])

  const deleteActiveView = useCallback(() => {
    if (!activePresetId) return
    const preset = viewPresets.find((candidate) => candidate.id === activePresetId)
    if (!preset) return
    Modal.confirm({
      title: t("watchlists:items.savedViews.deleteTitle", "Delete saved view?"),
      content: t(
        "watchlists:items.savedViews.deleteDescription",
        "Delete saved view \"{{name}}\"?",
        { name: preset.name }
      ),
      okText: t("common:delete", "Delete"),
      okButtonProps: { danger: true },
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => {
        setViewPresets((prev) => prev.filter((candidate) => candidate.id !== activePresetId))
        setActivePresetId((prev) => (prev === activePresetId ? null : prev))
        message.success(t("watchlists:items.savedViews.deleted", "Saved view deleted."))
      }
    })
  }, [activePresetId, t, viewPresets])

  const moveSelectionBy = useCallback((offset: number) => {
    if (items.length === 0) return
    const currentIndex = items.findIndex((item) => item.id === selectedItemId)
    const baseIndex =
      currentIndex === -1 ? (offset >= 0 ? 0 : items.length - 1) : currentIndex
    const nextIndex = Math.max(0, Math.min(items.length - 1, baseIndex + offset))
    setSelectedItemId(items[nextIndex]?.id ?? null)
  }, [items, selectedItemId])

  const openSelectedItemOriginal = useCallback(() => {
    if (!selectedItem?.url) return
    window.open(selectedItem.url, "_blank", "noopener,noreferrer")
  }, [selectedItem])

  const openQuickCreateFlow = useCallback(() => {
    setActiveTab("sources")
    openSourceForm()
  }, [openSourceForm, setActiveTab])

  const shortcutRows = useMemo(
    () => [
      {
        keys: "j / k",
        description: t(
          "watchlists:items.shortcuts.nextPrevious",
          "Move to next or previous article in the list."
        )
      },
      {
        keys: "space",
        description: t(
          "watchlists:items.shortcuts.toggleReviewed",
          "Toggle reviewed state for the selected article."
        )
      },
      {
        keys: "o",
        description: t(
          "watchlists:items.shortcuts.openOriginal",
          "Open the selected article in a new tab."
        )
      },
      {
        keys: "r",
        description: t(
          "watchlists:items.shortcuts.refresh",
          "Refresh feeds, article list, and smart counts."
        )
      },
      {
        keys: "n",
        description: t(
          "watchlists:items.shortcuts.newFlow",
          "Start a new feed flow by opening Add Source."
        )
      },
      {
        keys: "?",
        description: t(
          "watchlists:items.shortcuts.help",
          "Open this shortcuts help panel."
        )
      }
    ],
    [t]
  )

  const handleShortcutKeyDown = useCallback((event: KeyboardEvent) => {
    if (event.defaultPrevented) return
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isEditableTarget(event.target)) return
    if (shortcutsOpen && event.key !== "Escape") return

    const normalizedKey = event.key.toLowerCase()

    if (normalizedKey === "j") {
      event.preventDefault()
      moveSelectionBy(1)
      return
    }

    if (normalizedKey === "k") {
      event.preventDefault()
      moveSelectionBy(-1)
      return
    }

    if (event.key === " ") {
      if (!selectedItem || updatingItemId !== null || batchReviewScope !== null) return
      event.preventDefault()
      void handleToggleReviewed(selectedItem)
      return
    }

    if (normalizedKey === "o") {
      if (!selectedItem?.url) return
      event.preventDefault()
      openSelectedItemOriginal()
      return
    }

    if (normalizedKey === "r") {
      event.preventDefault()
      refreshItemsView()
      return
    }

    if (normalizedKey === "n") {
      event.preventDefault()
      openQuickCreateFlow()
      return
    }

    const isQuestionMark = event.key === "?" || (event.key === "/" && event.shiftKey)
    if (isQuestionMark) {
      event.preventDefault()
      setShortcutsOpen(true)
    }
  }, [
    batchReviewScope,
    handleToggleReviewed,
    moveSelectionBy,
    openQuickCreateFlow,
    openSelectedItemOriginal,
    refreshItemsView,
    selectedItem,
    shortcutsOpen,
    updatingItemId
  ])

  useEffect(() => {
    document.addEventListener("keydown", handleShortcutKeyDown)
    return () => document.removeEventListener("keydown", handleShortcutKeyDown)
  }, [handleShortcutKeyDown])

  const smartFeedRows: Array<{ key: SmartFeedFilter; label: string; count: number; icon: React.ReactNode }> = [
    {
      key: "today",
      label: t("watchlists:items.today", "Today"),
      count: smartCounts.today,
      icon: <Sun className="h-4 w-4" />
    },
    {
      key: "unread",
      label: t("watchlists:items.unread", "All Unread"),
      count: smartCounts.unread,
      icon: <Rss className="h-4 w-4" />
    },
    {
      key: "reviewed",
      label: t("watchlists:items.reviewedOnly", "Reviewed"),
      count: smartCounts.reviewed,
      icon: <CheckCircle2 className="h-4 w-4" />
    },
    {
      key: "all",
      label: t("watchlists:items.filters.all", "All"),
      count: smartCounts.all,
      icon: <RefreshCw className="h-4 w-4" />
    }
  ]

  return (
    <div className="space-y-3" data-testid="watchlists-items-tab">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          {t(
            "watchlists:items.description",
            "Browse scraped feed items and open the selected source content."
          )}
        </p>
        <Space>
          <Tooltip title={t("watchlists:items.shortcuts.helpHint", "Keyboard shortcuts (?)")}>
            <Button
              icon={<HelpCircle className="h-4 w-4" />}
              onClick={() => setShortcutsOpen(true)}
              data-testid="watchlists-items-shortcuts-help"
            >
              {t("watchlists:items.shortcuts.button", "Shortcuts")}
            </Button>
          </Tooltip>
          <Button
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={refreshItemsView}
            loading={sourcesLoading || itemsLoading}
          >
            {t("common:refresh", "Refresh")}
          </Button>
        </Space>
      </div>

      <div
        className="overflow-hidden rounded-2xl border border-border bg-surface"
        data-testid="watchlists-items-layout">
        <div className="grid min-h-[720px] grid-cols-1 xl:grid-cols-[280px_minmax(420px,34vw)_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(500px,36vw)_minmax(0,1fr)]">
          <aside
            className="border-b border-border bg-surface/70 p-4 xl:border-b-0 xl:border-r"
            data-testid="watchlists-items-left-pane">
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
                  {t("watchlists:items.smartFeeds", "Smart Feeds")}
                </p>
                <div className="space-y-1">
                  {smartFeedRows.map((row) => {
                    const isActive = smartFilter === row.key
                    return (
                      <button
                        key={row.key}
                        type="button"
                        className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition ${
                          isActive
                            ? "bg-primary/15 text-text"
                            : "text-text-muted hover:bg-surface-hover hover:text-text"
                        }`}
                        onClick={() => handleSmartFilterChange(row.key)}
                      >
                        <span className="flex items-center gap-2">
                          {row.icon}
                          <span>{row.label}</span>
                        </span>
                        <span className="text-xs font-semibold tabular-nums text-text-subtle">
                          {row.count}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
                  {t("watchlists:items.feeds", "Feeds")}
                </p>
                <Search
                  placeholder={t("watchlists:items.sourceSearchPlaceholder", "Search feeds...")}
                  value={sourceSearch}
                  onChange={(event) => setSourceSearch(event.target.value)}
                  allowClear
                  className="mb-2"
                />
                <div className="max-h-[430px] space-y-1 overflow-y-auto pr-1">
                  <button
                    type="button"
                    className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition ${
                      selectedSourceId === null
                        ? "bg-primary/15 text-text"
                        : "text-text-muted hover:bg-surface-hover hover:text-text"
                    }`}
                    onClick={() => handleSourceSelect(null)}
                  >
                    <span className="truncate">{t("watchlists:items.allFeeds", "All Feeds")}</span>
                    <span className="text-xs font-semibold tabular-nums text-text-subtle">
                      {smartCounts.all}
                    </span>
                  </button>

                  {sourcesLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Spin size="small" />
                    </div>
                  ) : filteredSources.length === 0 ? (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={t("watchlists:items.noFeeds", "No feeds found")}
                    />
                  ) : (
                    filteredSources.map((source) => {
                      const selected = selectedSourceId === source.id
                      return (
                        <button
                          key={source.id}
                          type="button"
                          className={`w-full rounded-lg px-2.5 py-2 text-left text-sm transition ${
                            selected
                              ? "bg-primary/15 text-text"
                              : "text-text-muted hover:bg-surface-hover hover:text-text"
                          }`}
                          onClick={() => handleSourceSelect(source.id)}
                        >
                          <div className="truncate font-medium">{source.name}</div>
                          <div className="truncate text-xs text-text-subtle">{source.url}</div>
                        </button>
                      )
                    })
                  )}
                </div>
              </div>
            </div>
          </aside>

          <section
            className="border-b border-border p-4 xl:border-b-0 xl:border-r"
            data-testid="watchlists-items-list-pane">
            <div className="mb-3 space-y-2">
              <div className="flex items-end justify-between gap-2">
                <div>
                  <h3 className="text-xl font-semibold text-text">{selectedSourceName}</h3>
                  <p className="text-sm text-text-muted">
                    {t("watchlists:items.unreadCount", "{{count}} unread", {
                      count: currentUnreadCount
                    })}
                  </p>
                </div>
              </div>

              <Search
                placeholder={t("watchlists:items.searchPlaceholder", "Search feed items...")}
                value={itemsSearch}
                onChange={(event) => {
                  setItemsSearch(event.target.value)
                  setItemsPage(1)
                }}
                allowClear
              />

              <Segmented<ReaderStatusFilter>
                block
                value={statusFilter}
                onChange={(value) => handleStatusChange(value)}
                options={[
                  { label: t("watchlists:items.filters.all", "All"), value: "all" },
                  {
                    label: t("watchlists:items.filters.ingested", "Ingested"),
                    value: "ingested"
                  },
                  {
                    label: t("watchlists:items.filters.filtered", "Filtered"),
                    value: "filtered"
                  }
                ]}
              />

              <div className="rounded-lg border border-border bg-surface/70 p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
                    {t("watchlists:items.savedViews.label", "Saved views")}
                  </span>
                  <Select
                    size="small"
                    allowClear
                    value={activePresetId ?? undefined}
                    placeholder={t("watchlists:items.savedViews.placeholder", "Select a saved view")}
                    options={viewPresetOptions}
                    onChange={(presetId) => {
                      if (!presetId) {
                        setActivePresetId(null)
                        return
                      }
                      applyViewPreset(presetId)
                    }}
                    className="min-w-[220px]"
                    data-testid="watchlists-items-view-presets-select"
                  />
                  <Button
                    size="small"
                    onClick={saveCurrentView}
                    data-testid="watchlists-items-view-save"
                  >
                    {activePresetId
                      ? t("watchlists:items.savedViews.update", "Update view")
                      : t("watchlists:items.savedViews.save", "Save view")}
                  </Button>
                  <Button
                    size="small"
                    danger
                    disabled={!activePresetId}
                    onClick={deleteActiveView}
                    data-testid="watchlists-items-view-delete"
                  >
                    {t("watchlists:items.savedViews.delete", "Delete view")}
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-border bg-surface/70 p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Checkbox
                    checked={allPageItemsSelected}
                    indeterminate={somePageItemsSelected}
                    onChange={(event) => handleToggleSelectPage(event.target.checked)}
                    data-testid="watchlists-items-select-page"
                  >
                    {t("watchlists:items.batch.selectPage", "Select page")}
                  </Checkbox>

                  <span
                    className="text-xs text-text-muted"
                    data-testid="watchlists-items-selected-count"
                  >
                    {t("watchlists:items.batch.selectedCount", "{{count}} selected", {
                      count: selectedItemIds.length
                    })}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button
                    size="small"
                    onClick={handleMarkSelectedReviewed}
                    disabled={selectedUnreviewedItemIds.length === 0}
                    loading={batchReviewScope === "selected"}
                    data-testid="watchlists-items-mark-selected"
                  >
                    {t("watchlists:items.batch.markSelected", "Mark selected as reviewed")}
                  </Button>

                  <Button
                    size="small"
                    onClick={handleMarkPageReviewed}
                    disabled={pageUnreviewedItemIds.length === 0}
                    loading={batchReviewScope === "page"}
                    data-testid="watchlists-items-mark-page"
                  >
                    {t("watchlists:items.batch.markPage", "Mark page as reviewed")}
                  </Button>

                  <Button
                    size="small"
                    onClick={() => void handleMarkAllFilteredReviewed()}
                    loading={batchReviewScope === "allFiltered"}
                    data-testid="watchlists-items-mark-all-filtered"
                  >
                    {t(
                      "watchlists:items.batch.markAllFiltered",
                      "Mark all filtered as reviewed"
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <div
              className="max-h-[560px] space-y-2 overflow-y-auto pr-1"
              data-testid="watchlists-items-list">
              {itemsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spin />
                </div>
              ) : items.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={t("watchlists:items.empty", "No feed items found")}
                />
              ) : (
                items.map((item) => {
                  const selected = item.id === selectedItemId
                  const sourceLabel =
                    sourceNameById.get(item.source_id) ||
                    t("watchlists:items.unknownSource", "Unknown source")
                  const previewText =
                    itemPreviewById.get(item.id) ||
                    t("watchlists:items.noSummary", "No summary available")
                  const imageUrl = itemImagesById.get(item.id)

                  return (
                    <button
                      key={item.id}
                      type="button"
                      data-testid={`watchlists-item-row-${item.id}`}
                      className={`flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition ${
                        selected
                          ? "border-primary bg-primary/15"
                          : "border-transparent hover:border-border hover:bg-surface-hover"
                      }`}
                      onClick={() => setSelectedItemId(item.id)}
                    >
                      <div className="pt-0.5">
                        <Checkbox
                          checked={selectedItemIdSet.has(item.id)}
                          onChange={(event) =>
                            handleToggleItemSelected(item.id, event.target.checked)
                          }
                          onClick={(event) => event.stopPropagation()}
                          data-testid={`watchlists-item-select-${item.id}`}
                        />
                      </div>

                      <div className="mt-1 shrink-0">
                        {!item.reviewed ? (
                          <span className="block h-2.5 w-2.5 rounded-full bg-primary" />
                        ) : (
                          <span className="block h-2.5 w-2.5 rounded-full bg-border" />
                        )}
                      </div>

                      {imageUrl ? (
                        <img
                          src={imageUrl}
                          alt={item.title || "article"}
                          className="h-12 w-12 shrink-0 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-surface-hover text-sm font-semibold uppercase text-text-subtle">
                          {sourceLabel.charAt(0) || "?"}
                        </div>
                      )}

                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="line-clamp-2 text-base font-semibold text-text">
                            {item.title || t("watchlists:items.untitled", "Untitled item")}
                          </h4>
                          <span className="shrink-0 text-xs font-medium text-text-subtle">
                            {renderItemTimestamp(item, t)}
                          </span>
                        </div>
                        <p className="line-clamp-2 text-sm text-text-muted">{previewText}</p>
                        <p className="truncate text-xs font-medium text-text-subtle">
                          {sourceLabel}
                        </p>
                      </div>
                    </button>
                  )
                })
              )}
            </div>

            <div className="mt-3">
              <div className="mb-2 flex items-center justify-end gap-2">
                <span className="text-xs text-text-muted">
                  {t("watchlists:items.pageSizeLabel", "Items per page")}
                </span>
                <Select
                  size="small"
                  value={itemsPageSize}
                  options={pageSizeOptions}
                  onChange={(nextPageSize) => {
                    setItemsPage(1)
                    setItemsPageSize(nextPageSize)
                  }}
                  className="min-w-[132px]"
                  data-testid="watchlists-items-page-size-select"
                />
              </div>
              <Pagination
                current={itemsPage}
                pageSize={itemsPageSize}
                total={itemsTotal}
                onChange={(page) => setItemsPage(page)}
                showSizeChanger={false}
                size="small"
                showTotal={(total) =>
                  t("watchlists:items.totalItems", "{{total}} items", { total })
                }
              />
            </div>
          </section>

          <section className="min-h-[720px] p-5" data-testid="watchlists-items-reader-pane">
            {itemsLoading && !selectedItem ? (
              <div className="flex h-full items-center justify-center">
                <Spin />
              </div>
            ) : !selectedItem ? (
              <div className="flex h-full items-center justify-center">
                <Empty
                  description={t(
                    "watchlists:items.selectPrompt",
                    "Select an item to view its content"
                  )}
                />
              </div>
            ) : (
              <article className="space-y-5" data-testid="watchlists-item-reader">
                <header className="space-y-3 border-b border-border pb-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-3xl font-semibold leading-tight text-text">
                        {selectedItem.title ||
                          t("watchlists:items.untitled", "Untitled item")}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-text-muted">
                        <Tag>
                          {sourceNameById.get(selectedItem.source_id) ||
                            t("watchlists:items.unknownSource", "Unknown source")}
                        </Tag>
                        <Tag color={selectedItem.status === "ingested" ? "green" : "orange"}>
                          {selectedItem.status}
                        </Tag>
                        {!selectedItem.reviewed && (
                          <Tag color="blue">{t("watchlists:items.unread", "All Unread")}</Tag>
                        )}
                        {selectedItem.reviewed && (
                          <Tag color="default">
                            {t("watchlists:items.reviewed", "Reviewed")}
                          </Tag>
                        )}
                      </div>
                      <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-text-subtle">
                        {formatReaderDate(selectedItem.published_at || selectedItem.created_at)}
                      </p>
                      {getDomain(selectedItem.url) && (
                        <p className="mt-1 text-sm text-text-muted">
                          {getDomain(selectedItem.url)}
                        </p>
                      )}
                    </div>

                    <Space>
                      {selectedItem.url && (
                        <Tooltip title={selectedItem.url}>
                          <Button
                            size="small"
                            icon={<ExternalLink className="h-3.5 w-3.5" />}
                            onClick={openSelectedItemOriginal}
                          >
                            {t("watchlists:items.openOriginal", "Open Original")}
                          </Button>
                        </Tooltip>
                      )}
                      <Button
                        size="small"
                        loading={updatingItemId === selectedItem.id}
                        onClick={() => void handleToggleReviewed(selectedItem)}
                      >
                        {selectedItem.reviewed
                          ? t(
                              "watchlists:items.markUnreviewed",
                              "Mark as unreviewed"
                            )
                          : t("watchlists:items.markReviewed", "Mark as reviewed")}
                      </Button>
                    </Space>
                  </div>
                </header>

                {selectedItemPreviewImage && !selectedItemBodyHtml.includes("<img") && (
                  <img
                    src={selectedItemPreviewImage}
                    alt={selectedItem.title || "article image"}
                    className="max-h-[420px] w-full rounded-xl object-cover"
                  />
                )}

                {selectedItemRawBody ? (
                  selectedItemBodyIsHtml ? (
                    <div
                      className="space-y-4 text-[15px] leading-7 text-text [&_a]:text-primary [&_a]:underline [&_h1]:text-3xl [&_h1]:font-semibold [&_h2]:text-2xl [&_h2]:font-semibold [&_img]:my-4 [&_img]:max-h-[460px] [&_img]:w-full [&_img]:rounded-lg [&_img]:object-cover [&_p]:my-3"
                      dangerouslySetInnerHTML={{ __html: selectedItemBodyHtml }}
                    />
                  ) : (
                    <div className="whitespace-pre-wrap text-[15px] leading-7 text-text">
                      {selectedItemRawBody}
                    </div>
                  )
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={t(
                      "watchlists:items.noSummary",
                      "No summary available"
                    )}
                  />
                )}

                {!selectedItem.url && (
                  <Tag>
                    {t(
                      "watchlists:items.noUrlHint",
                      "This item does not include an original URL."
                    )}
                  </Tag>
                )}
              </article>
            )}
          </section>
        </div>
      </div>

      <Modal
        title={t("watchlists:items.savedViews.saveTitle", "Save current view")}
        open={saveViewModalOpen}
        onCancel={() => {
          setSaveViewModalOpen(false)
          setNewViewName("")
        }}
        onOk={createViewPreset}
        okText={t("watchlists:items.savedViews.save", "Save view")}
        cancelText={t("common:cancel", "Cancel")}
        destroyOnHidden
      >
        <div className="space-y-2" data-testid="watchlists-items-view-save-modal">
          <p className="text-sm text-text-muted">
            {t(
              "watchlists:items.savedViews.saveDescription",
              "Save the current source, smart feed, status, and search filters."
            )}
          </p>
          <Input
            value={newViewName}
            onChange={(event) => setNewViewName(event.target.value)}
            placeholder={t("watchlists:items.savedViews.namePlaceholder", "Daily triage")}
            maxLength={64}
            autoFocus
            data-testid="watchlists-items-view-name-input"
          />
        </div>
      </Modal>

      <Modal
        title={t("watchlists:items.shortcuts.title", "Keyboard shortcuts")}
        open={shortcutsOpen}
        onCancel={() => setShortcutsOpen(false)}
        footer={null}
        destroyOnHidden
      >
        <div className="space-y-2" data-testid="watchlists-items-shortcuts-modal">
          {shortcutRows.map((shortcut) => (
            <div
              key={shortcut.keys}
              className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface/70 px-3 py-2.5"
            >
              <kbd className="rounded-md border border-border bg-surface px-2 py-0.5 font-mono text-xs font-semibold text-text">
                {shortcut.keys}
              </kbd>
              <p className="flex-1 text-sm text-text-muted">{shortcut.description}</p>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  )
}
