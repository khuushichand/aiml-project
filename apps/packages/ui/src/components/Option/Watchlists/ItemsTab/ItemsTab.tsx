import React, { useCallback, useEffect, useMemo, useState } from "react"
import {
  Button,
  Empty,
  Input,
  Pagination,
  Segmented,
  Space,
  Spin,
  Tag,
  Tooltip,
  message
} from "antd"
import DOMPurify from "dompurify"
import { CheckCircle2, ExternalLink, RefreshCw, Rss, Sun } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"
import {
  fetchScrapedItems,
  fetchWatchlistSources,
  updateScrapedItem
} from "@/services/watchlists"
import type { FetchItemsParams } from "@/services/watchlists"
import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"
import { formatRelativeTime } from "@/utils/dateFormatters"
import {
  extractImageUrl,
  filterSourcesForReader,
  ITEM_PAGE_SIZE,
  resolveSelectedItemId,
  SOURCE_LOAD_MAX_ITEMS,
  SOURCE_LOAD_PAGE_SIZE,
  stripHtmlToText
} from "./items-utils"

const { Search } = Input

type ReaderStatusFilter = "all" | "ingested" | "filtered"
type SmartFeedFilter = "all" | "today" | "unread" | "reviewed"

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

export const ItemsTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])
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
  const [updatingItemId, setUpdatingItemId] = useState<number | null>(null)
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
          size: ITEM_PAGE_SIZE
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
  }, [buildBaseFilterParams, itemsPage, t])

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

  useEffect(() => {
    void loadSources()
  }, [loadSources])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  useEffect(() => {
    void loadSmartCounts()
  }, [loadSmartCounts])

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
        <Button
          icon={<RefreshCw className="h-4 w-4" />}
          onClick={() => {
            void loadSources()
            void loadItems()
            void loadSmartCounts()
          }}
          loading={sourcesLoading || itemsLoading}
        >
          {t("common:refresh", "Refresh")}
        </Button>
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
              <Pagination
                current={itemsPage}
                pageSize={ITEM_PAGE_SIZE}
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
                            onClick={() =>
                              window.open(
                                selectedItem.url || "",
                                "_blank",
                                "noopener,noreferrer"
                              )
                            }
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
    </div>
  )
}
