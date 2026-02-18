import React, { useCallback, useEffect, useMemo, useState } from "react"
import {
  Button,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  message
} from "antd"
import type { ColumnsType } from "antd/es/table"
import { Download, Edit2, ExternalLink, Eye, Plus, RefreshCw, Trash2, UploadCloud } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useWatchlistsStore } from "@/store/watchlists"
import {
  checkWatchlistSourcesNow,
  createWatchlistSource,
  deleteWatchlistSource,
  exportOpml,
  getSourceSeenStats,
  fetchWatchlistSources,
  fetchWatchlistGroups,
  fetchWatchlistTags,
  updateWatchlistSource
} from "@/services/watchlists"
import type { SourceSeenStats, WatchlistSource, SourceType } from "@/types/watchlists"
import { formatRelativeTime } from "@/utils/dateFormatters"
import { SourceFormModal } from "./SourceFormModal"
import { GroupsTree } from "./GroupsTree"
import { SourcesBulkImport } from "./SourcesBulkImport"
import { SourceSeenDrawer } from "./SourceSeenDrawer"
import {
  getSourcesTableEmptyDescription,
  shouldShowUnifiedWatchlistsEmptyState
} from "./empty-state"
import {
  normalizeSourceIds,
  resolveCheckNowTargets,
  shouldConfirmMultiSourceCheck
} from "./check-now-utils"
import { getSourceStatusVisual } from "./sourceStatus"

const { Search } = Input

const SOURCE_TYPE_COLORS: Record<SourceType, string> = {
  rss: "blue",
  site: "green",
  forum: "purple"
}
type SourceHealthSnapshot = Pick<SourceSeenStats, "defer_until" | "consec_not_modified">
const CLIENT_FILTER_PAGE_SIZE = 200
const CLIENT_FILTER_MAX_ITEMS = 1000

export const SourcesTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])

  // Store state
  const sources = useWatchlistsStore((s) => s.sources)
  const sourcesLoading = useWatchlistsStore((s) => s.sourcesLoading)
  const sourcesTotal = useWatchlistsStore((s) => s.sourcesTotal)
  const sourcesSearch = useWatchlistsStore((s) => s.sourcesSearch)
  const sourcesPage = useWatchlistsStore((s) => s.sourcesPage)
  const sourcesPageSize = useWatchlistsStore((s) => s.sourcesPageSize)
  const tags = useWatchlistsStore((s) => s.tags)
  const groups = useWatchlistsStore((s) => s.groups)
  const groupsLoading = useWatchlistsStore((s) => s.groupsLoading)
  const selectedGroupId = useWatchlistsStore((s) => s.selectedGroupId)
  const selectedTagName = useWatchlistsStore((s) => s.selectedTagName)
  const sourceFormOpen = useWatchlistsStore((s) => s.sourceFormOpen)
  const sourceFormEditId = useWatchlistsStore((s) => s.sourceFormEditId)

  // Store actions
  const setSources = useWatchlistsStore((s) => s.setSources)
  const setSourcesLoading = useWatchlistsStore((s) => s.setSourcesLoading)
  const setSourcesSearch = useWatchlistsStore((s) => s.setSourcesSearch)
  const setSourcesPage = useWatchlistsStore((s) => s.setSourcesPage)
  const setSourcesPageSize = useWatchlistsStore((s) => s.setSourcesPageSize)
  const setTags = useWatchlistsStore((s) => s.setTags)
  const setGroups = useWatchlistsStore((s) => s.setGroups)
  const setGroupsLoading = useWatchlistsStore((s) => s.setGroupsLoading)
  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const setSelectedGroupId = useWatchlistsStore((s) => s.setSelectedGroupId)
  const setSelectedTagName = useWatchlistsStore((s) => s.setSelectedTagName)
  const openSourceForm = useWatchlistsStore((s) => s.openSourceForm)
  const closeSourceForm = useWatchlistsStore((s) => s.closeSourceForm)
  const addSource = useWatchlistsStore((s) => s.addSource)
  const updateSourceInList = useWatchlistsStore((s) => s.updateSourceInList)
  const removeSource = useWatchlistsStore((s) => s.removeSource)

  // Local state
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(
    null
  )
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [bulkWorking, setBulkWorking] = useState(false)
  const [checkingSourceIds, setCheckingSourceIds] = useState<number[]>([])
  const [importOpen, setImportOpen] = useState(false)
  const [seenDrawerSourceId, setSeenDrawerSourceId] = useState<number | null>(null)
  const [sourceHealthById, setSourceHealthById] = useState<Record<number, SourceHealthSnapshot>>({})

  const selectedSources = useMemo(
    () => sources.filter((source) => selectedRowKeys.includes(source.id)),
    [sources, selectedRowKeys]
  )
  const selectedSourceIds = useMemo(
    () => selectedSources.map((source) => source.id),
    [selectedSources]
  )
  const hasActiveFilters = useMemo(
    () =>
      Boolean(
        selectedGroupId ||
          selectedTagName ||
          selectedTypeFilter ||
          sourcesSearch.trim().length > 0
      ),
    [selectedGroupId, selectedTagName, selectedTypeFilter, sourcesSearch]
  )
  const unifiedEmptyState = shouldShowUnifiedWatchlistsEmptyState({
    groupsCount: groups.length,
    sourcesCount: sources.length,
    hasActiveFilters,
    groupsLoading,
    sourcesLoading
  })
  const tableEmptyDescription = getSourcesTableEmptyDescription(hasActiveFilters)

  const loadSourceHealth = useCallback(async (items: WatchlistSource[]) => {
    if (!Array.isArray(items) || items.length === 0) {
      setSourceHealthById({})
      return
    }

    const results = await Promise.allSettled(
      items.map((source) => getSourceSeenStats(source.id, { keys_limit: 1 }))
    )

    const next: Record<number, SourceHealthSnapshot> = {}
    results.forEach((result, index) => {
      if (result.status !== "fulfilled") return
      next[items[index].id] = {
        defer_until: result.value.defer_until,
        consec_not_modified: result.value.consec_not_modified
      }
    })

    setSourceHealthById(next)
  }, [])

  // Fetch sources
  const loadSources = useCallback(async () => {
    setSourcesLoading(true)
    try {
      const useClientFilter = Boolean(selectedGroupId || selectedTypeFilter)
      const baseParams = {
        q: sourcesSearch || undefined,
        tags: selectedTagName ? [selectedTagName] : undefined
      }
      let items: WatchlistSource[] = []
      let total = 0

      if (useClientFilter) {
        let page = 1
        while (items.length < CLIENT_FILTER_MAX_ITEMS) {
          const result = await fetchWatchlistSources({
            ...baseParams,
            page,
            size: CLIENT_FILTER_PAGE_SIZE
          })
          const batch = Array.isArray(result.items) ? result.items : []
          if (page === 1) total = result.total || batch.length
          items = items.concat(batch)
          if (items.length >= total || batch.length < CLIENT_FILTER_PAGE_SIZE) {
            break
          }
          page += 1
        }
      } else {
        const result = await fetchWatchlistSources({
          ...baseParams,
          page: sourcesPage,
          size: sourcesPageSize
        })
        items = Array.isArray(result.items) ? result.items : []
        total = result.total || items.length
      }

      if (selectedGroupId) {
        try {
          const opml = await exportOpml({ group: [selectedGroupId] })
          const parser = new DOMParser()
          const doc = parser.parseFromString(opml, "text/xml")
          const urls = Array.from(doc.querySelectorAll("outline[xmlUrl]"))
            .map((node) => node.getAttribute("xmlUrl"))
            .filter((url): url is string => Boolean(url))
          const urlSet = new Set(urls)
          items = items.filter((source) => urlSet.has(source.url))
        } catch (err) {
          console.error("Failed to load group OPML:", err)
          message.error(t("watchlists:sources.groupFilterError", "Failed to load group filter"))
        }
      }

      if (selectedTypeFilter) {
        items = items.filter((source) => source.source_type === selectedTypeFilter)
      }

      total = useClientFilter ? items.length : total
      const pagedItems = useClientFilter
        ? items.slice((sourcesPage - 1) * sourcesPageSize, sourcesPage * sourcesPageSize)
        : items

      setSources(pagedItems, total)
      void loadSourceHealth(pagedItems)
    } catch (err) {
      console.error("Failed to fetch sources:", err)
      message.error(t("watchlists:sources.fetchError", "Failed to load sources"))
    } finally {
      setSourcesLoading(false)
    }
  }, [
    sourcesSearch,
    selectedTagName,
    selectedTypeFilter,
    selectedGroupId,
    sourcesPage,
    sourcesPageSize,
    setSources,
    setSourcesLoading,
    loadSourceHealth,
    t
  ])

  // Fetch tags
  const loadTags = useCallback(async () => {
    try {
      const result = await fetchWatchlistTags({ page: 1, size: 200 })
      setTags(Array.isArray(result.items) ? result.items : [])
    } catch (err) {
      console.error("Failed to fetch tags:", err)
      setTags([])
    }
  }, [setTags])

  const loadGroups = useCallback(async () => {
    setGroupsLoading(true)
    try {
      const result = await fetchWatchlistGroups({ page: 1, size: 200 })
      setGroups(Array.isArray(result.items) ? result.items : [])
    } catch (err) {
      console.error("Failed to fetch groups:", err)
      setGroups([])
    } finally {
      setGroupsLoading(false)
    }
  }, [setGroups, setGroupsLoading])

  // Initial load
  useEffect(() => {
    loadSources()
    loadTags()
    loadGroups()
  }, [loadSources, loadTags, loadGroups])

  // Handle toggle active
  const handleToggleActive = async (source: WatchlistSource) => {
    try {
      const updated = await updateWatchlistSource(source.id, {
        active: !source.active
      })
      updateSourceInList(source.id, updated)
      message.success(
        source.active
          ? t("watchlists:sources.disabled", "Source disabled")
          : t("watchlists:sources.enabled", "Source enabled")
      )
    } catch (err) {
      console.error("Failed to toggle source:", err)
      message.error(t("watchlists:sources.toggleError", "Failed to update source"))
    }
  }

  // Handle delete
  const handleDelete = async (sourceId: number) => {
    try {
      await deleteWatchlistSource(sourceId)
      removeSource(sourceId)
      message.success(t("watchlists:sources.deleted", "Source deleted"))
    } catch (err) {
      console.error("Failed to delete source:", err)
      message.error(t("watchlists:sources.deleteError", "Failed to delete source"))
    }
  }

  const handleBulkToggle = async (active: boolean) => {
    if (selectedSources.length === 0) return
    setBulkWorking(true)
    try {
      const results = await Promise.allSettled(
        selectedSources.map((source) =>
          updateWatchlistSource(source.id, { active })
        )
      )
      let successCount = 0
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          updateSourceInList(selectedSources[idx].id, result.value)
          successCount += 1
        }
      })
      message.success(
        t(
          "watchlists:sources.bulkUpdated",
          "{{count}} sources updated",
          { count: successCount }
        )
      )
    } catch (err) {
      console.error("Bulk update failed:", err)
      message.error(t("watchlists:sources.bulkError", "Bulk update failed"))
    } finally {
      setBulkWorking(false)
      setSelectedRowKeys([])
    }
  }

  const handleBulkDelete = async () => {
    if (selectedSources.length === 0) return
    setBulkWorking(true)
    try {
      const results = await Promise.allSettled(
        selectedSources.map((source) => deleteWatchlistSource(source.id))
      )
      let successCount = 0
      results.forEach((result, idx) => {
        if (result.status === "fulfilled") {
          removeSource(selectedSources[idx].id)
          successCount += 1
        }
      })
      message.success(
        t(
          "watchlists:sources.bulkDeleted",
          "{{count}} sources deleted",
          { count: successCount }
        )
      )
    } catch (err) {
      console.error("Bulk delete failed:", err)
      message.error(t("watchlists:sources.bulkDeleteError", "Bulk delete failed"))
    } finally {
      setBulkWorking(false)
      setSelectedRowKeys([])
    }
  }

  const executeCheckNow = useCallback(async (sourceIds: number[]) => {
    const normalizedIds = normalizeSourceIds(sourceIds)
    if (normalizedIds.length === 0) return

    setCheckingSourceIds((prev) => Array.from(new Set([...prev, ...normalizedIds])))
    try {
      const result = await checkWatchlistSourcesNow(normalizedIds)
      const successCount = typeof result.success === "number"
        ? result.success
        : (Array.isArray(result.items) ? result.items.filter((item) => item.status === "ok").length : 0)
      const failedCount = typeof result.failed === "number"
        ? result.failed
        : Math.max(normalizedIds.length - successCount, 0)
      const viewRunsAction = (
        <Button
          type="link"
          size="small"
          className="px-0"
          onClick={() => setActiveTab("runs")}
        >
          {t("watchlists:sources.viewRuns", "View Runs")}
        </Button>
      )

      if (failedCount === 0) {
        message.success({
          content: (
            <span>
              {t(
                "watchlists:sources.checkNowSuccess",
                "Checked {{count}} source{{plural}}",
                {
                  count: successCount,
                  plural: successCount === 1 ? "" : "s"
                }
              )}{" "}
              {viewRunsAction}
            </span>
          )
        })
      } else if (successCount > 0) {
        message.warning({
          content: (
            <span>
              {t(
                "watchlists:sources.checkNowPartial",
                "Checked {{success}} source{{successPlural}}, {{failed}} failed",
                {
                  success: successCount,
                  successPlural: successCount === 1 ? "" : "s",
                  failed: failedCount
                }
              )}{" "}
              {viewRunsAction}
            </span>
          )
        })
      } else {
        message.error(t("watchlists:sources.checkNowError", "Failed to check selected sources"))
      }

      await loadSources()
    } catch (err) {
      console.error("Failed to check sources now:", err)
      message.error(t("watchlists:sources.checkNowError", "Failed to check selected sources"))
    } finally {
      setCheckingSourceIds((prev) => prev.filter((id) => !normalizedIds.includes(id)))
    }
  }, [loadSources, setActiveTab, t])

  const requestCheckNow = useCallback((sourceIds: number[]) => {
    const normalizedIds = normalizeSourceIds(sourceIds)
    if (normalizedIds.length === 0) return

    if (shouldConfirmMultiSourceCheck(normalizedIds)) {
      Modal.confirm({
        title: t(
          "watchlists:sources.checkNowMultiConfirmTitle",
          "Check {{count}} sources now?",
          { count: normalizedIds.length }
        ),
        content: t(
          "watchlists:sources.checkNowMultiConfirmDescription",
          "This will manually force a refresh for all selected sources."
        ),
        okText: t("watchlists:sources.checkNow", "Check Now"),
        cancelText: t("common:cancel", "Cancel"),
        onOk: () => executeCheckNow(normalizedIds)
      })
      return
    }

    void executeCheckNow(normalizedIds)
  }, [executeCheckNow, t])

  const resolveCheckNowTargetIds = useCallback((sourceId: number): number[] => {
    return resolveCheckNowTargets(sourceId, selectedSourceIds)
  }, [selectedSourceIds])

  // Handle form submit
  const handleFormSubmit = async (
    values: { name: string; url: string; source_type: SourceType; tags: string[] }
  ) => {
    try {
      if (sourceFormEditId) {
        const updated = await updateWatchlistSource(sourceFormEditId, values)
        updateSourceInList(sourceFormEditId, updated)
        message.success(t("watchlists:sources.updated", "Source updated"))
      } else {
        const created = await createWatchlistSource(values)
        addSource(created)
        message.success(t("watchlists:sources.created", "Source created"))
      }
      closeSourceForm()
      loadTags() // Refresh tags in case new ones were added
    } catch (err) {
      console.error("Failed to save source:", err)
      message.error(t("watchlists:sources.saveError", "Failed to save source"))
    }
  }

  const handleExport = async () => {
    try {
      const opml = await exportOpml({
        tag: selectedTagName ? [selectedTagName] : undefined,
        group: selectedGroupId ? [selectedGroupId] : undefined,
        type: selectedTypeFilter || undefined
      })
      const blob = new Blob([opml], { type: "application/xml" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `watchlists_sources_${Date.now()}.opml`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      message.success(t("watchlists:sources.exported", "OPML exported"))
    } catch (err) {
      console.error("Failed to export OPML:", err)
      message.error(t("watchlists:sources.exportError", "Failed to export OPML"))
    }
  }

  // Get source for editing
  const editingSource = sourceFormEditId
    ? sources.find((s) => s.id === sourceFormEditId)
    : undefined

  // Table columns
  const columns: ColumnsType<WatchlistSource> = [
    {
      title: t("watchlists:sources.columns.name", "Name"),
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      render: (name: string, record) => (
        <div className="flex items-center gap-2">
          <span className="font-medium">{name}</span>
          {record.url && (
            <Tooltip title={record.url}>
              <a
                href={record.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-text-subtle hover:text-text-muted"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Tooltip>
          )}
        </div>
      )
    },
    {
      title: t("watchlists:sources.columns.type", "Type"),
      dataIndex: "source_type",
      key: "source_type",
      width: 100,
      render: (type: SourceType) => (
        <Tag color={SOURCE_TYPE_COLORS[type] || "default"}>
          {type.toUpperCase()}
        </Tag>
      )
    },
    {
      title: t("watchlists:sources.columns.status", "Status"),
      key: "status",
      width: 300,
      render: (_, record) => {
        const statusVisual = getSourceStatusVisual(record.status, record.active)
        const health = sourceHealthById[record.id]
        const deferUntil = health?.defer_until
        const consecutiveNotModified = health?.consec_not_modified ?? 0
        const hasBackoff = typeof deferUntil === "string" && deferUntil.length > 0

        return (
          <div className="flex flex-wrap items-center gap-1">
            <Tag color={statusVisual.color}>{statusVisual.label}</Tag>
            {consecutiveNotModified > 0 && (
              <Tag color={consecutiveNotModified >= 5 ? "red" : "gold"}>
                {t("watchlists:sources.staleCount", "Stale x{{count}}", {
                  count: consecutiveNotModified
                })}
              </Tag>
            )}
            {hasBackoff && (
              <Tooltip title={new Date(deferUntil).toLocaleString()}>
                <Tag color="gold">
                  {t("watchlists:sources.backoffUntil", "Backoff {{time}}", {
                    time: formatRelativeTime(deferUntil, t, { compact: true })
                  })}
                </Tag>
              </Tooltip>
            )}
          </div>
        )
      }
    },
    {
      title: t("watchlists:sources.columns.tags", "Tags"),
      dataIndex: "tags",
      key: "tags",
      width: 200,
      render: (tags: string[]) => (
        <div className="flex flex-wrap gap-1">
          {tags.slice(0, 3).map((tag) => (
            <Tag key={tag} className="text-xs">
              {tag}
            </Tag>
          ))}
          {tags.length > 3 && (
            <Tag className="text-xs">+{tags.length - 3}</Tag>
          )}
        </div>
      )
    },
    {
      title: t("watchlists:sources.columns.lastScraped", "Last Scraped"),
      dataIndex: "last_scraped_at",
      key: "last_scraped_at",
      width: 190,
      render: (date: string | null, record) => {
        const targetIds = resolveCheckNowTargetIds(record.id)
        const checkNowLoading = targetIds.some((id) => checkingSourceIds.includes(id))
        const checkNowTooltip = targetIds.length > 1
          ? t(
              "watchlists:sources.checkNowSelectedTooltip",
              "Check now for {{count}} selected sources",
              { count: targetIds.length }
            )
          : t("watchlists:sources.checkNowTooltip", "Check now")

        return (
          <div className="flex items-center gap-1.5">
            {date ? (
              <span className="text-sm text-text-muted">
                {formatRelativeTime(date, t)}
              </span>
            ) : (
              <span className="text-sm text-text-subtle">
                {t("watchlists:sources.never", "Never")}
              </span>
            )}
            <Tooltip title={checkNowTooltip}>
              <Button
                type="text"
                size="small"
                shape="circle"
                icon={<RefreshCw className="h-3.5 w-3.5" />}
                loading={checkNowLoading}
                aria-label={checkNowTooltip}
                onClick={(event) => {
                  event.stopPropagation()
                  requestCheckNow(targetIds)
                }}
              />
            </Tooltip>
          </div>
        )
      }
    },
    {
      title: t("watchlists:sources.columns.active", "Active"),
      dataIndex: "active",
      key: "active",
      width: 80,
      align: "center",
      render: (active: boolean, record) => (
        <Switch
          checked={active}
          size="small"
          onChange={() => handleToggleActive(record)}
        />
      )
    },
    {
      title: t("watchlists:sources.columns.actions", "Actions"),
      key: "actions",
      width: 140,
      align: "center",
      render: (_, record) => (
        <Space size="small">
          <Tooltip title={t("common:edit", "Edit")}>
            <Button
              type="text"
              size="small"
              icon={<Edit2 className="h-4 w-4" />}
              onClick={() => openSourceForm(record.id)}
            />
          </Tooltip>
          <Tooltip title={t("watchlists:sources.seenInfo", "Source Health & Dedup Stats")}>
            <Button
              type="text"
              size="small"
              icon={<Eye className="h-4 w-4" />}
              onClick={() => setSeenDrawerSourceId(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title={t("watchlists:sources.deleteConfirm", "Delete this source?")}
            onConfirm={() => handleDelete(record.id)}
            okText={t("common:yes", "Yes")}
            cancelText={t("common:no", "No")}
          >
            <Tooltip title={t("common:delete", "Delete")}>
              <Button
                type="text"
                size="small"
                danger
                icon={<Trash2 className="h-4 w-4" />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Search
            placeholder={t("watchlists:sources.searchPlaceholder", "Search sources...")}
            value={sourcesSearch}
            onChange={(e) => setSourcesSearch(e.target.value)}
            onSearch={loadSources}
            allowClear
            className="w-64"
          />
          <Select
            placeholder={t("watchlists:sources.filterByTag", "Filter by tag")}
            value={selectedTagName}
            onChange={setSelectedTagName}
            allowClear
            className="w-40"
            options={(Array.isArray(tags) ? tags : []).map((tag) => ({
              label: tag.name,
              value: tag.name
            }))}
          />
          <Select
            placeholder={t("watchlists:sources.filterByType", "Filter by type")}
            value={selectedTypeFilter}
            onChange={(value) => {
              setSelectedTypeFilter(value)
              setSourcesPage(1)
            }}
            allowClear
            className="w-32"
            options={[
              { label: "RSS", value: "rss" },
              { label: "Site", value: "site" },
              { label: "Forum", value: "forum" }
            ]}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={loadSources}
            loading={sourcesLoading}
          >
            {t("common:refresh", "Refresh")}
          </Button>
          <Button
            icon={<Download className="h-4 w-4" />}
            onClick={handleExport}
          >
            {t("watchlists:sources.export", "Export OPML")}
          </Button>
          <Button
            icon={<UploadCloud className="h-4 w-4" />}
            onClick={() => setImportOpen(true)}
          >
            {t("watchlists:sources.import", "Import OPML")}
          </Button>
          <Button
            type="primary"
            icon={<Plus className="h-4 w-4" />}
            onClick={() => openSourceForm()}
          >
            {t("watchlists:sources.addSource", "Add Source")}
          </Button>
        </div>
      </div>

      {selectedRowKeys.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border p-3 text-sm">
          <span className="text-text-muted">
            {t("watchlists:sources.selectedCount", "{{count}} selected", { count: selectedRowKeys.length })}
          </span>
          <Button
            size="small"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => requestCheckNow(selectedSourceIds)}
            loading={selectedSourceIds.some((id) => checkingSourceIds.includes(id))}
            disabled={bulkWorking}
          >
            {t("watchlists:sources.checkNow", "Check Now")}
          </Button>
          <Button size="small" onClick={() => handleBulkToggle(true)} loading={bulkWorking}>
            {t("watchlists:sources.bulkEnable", "Enable")}
          </Button>
          <Button size="small" onClick={() => handleBulkToggle(false)} loading={bulkWorking}>
            {t("watchlists:sources.bulkDisable", "Disable")}
          </Button>
          <Popconfirm
            title={t("watchlists:sources.bulkDeleteConfirm", "Delete selected sources?")}
            onConfirm={handleBulkDelete}
            okText={t("common:yes", "Yes")}
            cancelText={t("common:no", "No")}
          >
            <Button size="small" danger loading={bulkWorking}>
              {t("watchlists:sources.bulkDelete", "Delete")}
            </Button>
          </Popconfirm>
          <Button size="small" onClick={() => setSelectedRowKeys([])}>
            {t("common:clear", "Clear")}
          </Button>
        </div>
      )}

      {unifiedEmptyState ? (
        <div className="rounded-lg border border-dashed border-border bg-surface p-8">
          <Empty
            description={
              <div className="space-y-2">
                <p className="text-text-muted">
                  {t("watchlists:sources.emptyInitialTitle", "No watchlist sources yet")}
                </p>
                <p className="text-sm text-text-subtle">
                  {t(
                    "watchlists:sources.emptyInitialDescription",
                    "Add a source or import OPML to start monitoring updates."
                  )}
                </p>
              </div>
            }
          >
            <Space>
              <Button
                type="primary"
                icon={<Plus className="h-4 w-4" />}
                onClick={() => openSourceForm()}
              >
                {t("watchlists:sources.addSource", "Add Source")}
              </Button>
              <Button
                icon={<UploadCloud className="h-4 w-4" />}
                onClick={() => setImportOpen(true)}
              >
                {t("watchlists:sources.import", "Import OPML")}
              </Button>
            </Space>
          </Empty>
        </div>
      ) : (
        <div className="flex flex-col gap-4 lg:flex-row">
          <div className="w-full lg:w-72 shrink-0 space-y-4">
            <GroupsTree
              groups={groups}
              selectedGroupId={selectedGroupId}
              loading={groupsLoading}
              onSelect={setSelectedGroupId}
              onRefresh={loadGroups}
            />
          </div>

          <div className="flex-1">
            <Table
              dataSource={Array.isArray(sources) ? sources : []}
              columns={columns}
              rowKey="id"
              loading={sourcesLoading}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={t(
                      "watchlists:sources.emptyTableDescription",
                      tableEmptyDescription
                    )}
                  />
                )
              }}
              rowSelection={{
                selectedRowKeys,
                onChange: setSelectedRowKeys
              }}
              pagination={{
                current: sourcesPage,
                pageSize: sourcesPageSize,
                total: sourcesTotal,
                showSizeChanger: true,
                showTotal: (total) =>
                  t("watchlists:sources.totalItems", "{{total}} sources", { total }),
                onChange: (page, pageSize) => {
                  setSourcesPage(page)
                  if (pageSize !== sourcesPageSize) {
                    setSourcesPageSize(pageSize)
                  }
                }
              }}
              size="middle"
              scroll={{ x: 800 }}
            />
          </div>
        </div>
      )}

      <SourceFormModal
        open={sourceFormOpen}
        onClose={closeSourceForm}
        onSubmit={handleFormSubmit}
        initialValues={editingSource}
        existingTags={(Array.isArray(tags) ? tags : []).map((t) => t.name)}
      />

      <SourcesBulkImport
        open={importOpen}
        onClose={() => setImportOpen(false)}
        groups={groups}
        tags={tags}
        defaultGroupId={selectedGroupId}
        onImported={() => {
          loadSources()
          loadTags()
          loadGroups()
        }}
      />

      <SourceSeenDrawer
        open={seenDrawerSourceId !== null}
        onClose={() => setSeenDrawerSourceId(null)}
        sourceId={seenDrawerSourceId}
        sourceName={sources.find((s) => s.id === seenDrawerSourceId)?.name}
      />
    </div>
  )
}
