import React from "react"
import { Tag, Tooltip } from "antd"
import type { ColumnsType } from "antd/es/table"
import { Star } from "lucide-react"
import { SyncStatusBadge } from "./SyncStatusBadge"
import type { PromptListSortKey, PromptListSortOrder, PromptRowVM } from "./prompt-workspace-types"

export type PromptTableColumnLabels = {
  title: string
  preview: string
  tags: string
  updated: string
  status: string
  actions: string
  author: string
  system: string
  user: string
  unknown: string
  offlineStatus: string
  edit: string
}

export type PromptTableColumnOptions = {
  isOnline: boolean
  isCompactViewport: boolean
  sortKey: PromptListSortKey
  sortOrder: PromptListSortOrder
  onToggleFavorite?: (row: PromptRowVM, nextFavorite: boolean) => void
  onEdit?: (row: PromptRowVM) => void
  onOpenConflictResolution?: (row: PromptRowVM) => void
  renderActions?: (row: PromptRowVM) => React.ReactNode
  renderTitleMeta?: (row: PromptRowVM) => React.ReactNode
  favoriteButtonTestId?: (row: PromptRowVM) => string
  labels?: Partial<PromptTableColumnLabels>
  formatRelativeTime?: (timestamp?: number) => string
}

const defaultFormatRelativeTime = (timestamp?: number) => {
  if (!timestamp) return "Unknown"
  const now = Date.now()
  const diffMs = Math.max(0, now - timestamp)
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffMinutes < 1) return "Just now"
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  return new Date(timestamp).toLocaleDateString()
}

const renderPreview = (
  record: PromptRowVM,
  isCompactViewport: boolean,
  labels: Pick<PromptTableColumnLabels, "system" | "user">
) => {
  const clampClass = isCompactViewport ? "line-clamp-1" : "line-clamp-2"
  return (
    <div className={`flex flex-col gap-1 ${isCompactViewport ? "max-w-[14rem]" : "max-w-[24rem]"}`}>
      {record.previewSystem ? (
        <div className="flex items-start gap-2">
          <Tag color="volcano">{labels.system}</Tag>
          <span className={clampClass}>{record.previewSystem}</span>
        </div>
      ) : null}
      {record.previewUser ? (
        <div className="flex items-start gap-2">
          <Tag color="blue">{labels.user}</Tag>
          <span className={clampClass}>{record.previewUser}</span>
        </div>
      ) : null}
    </div>
  )
}

export const buildPromptTableColumns = (
  options: PromptTableColumnOptions
): ColumnsType<PromptRowVM> => {
  const {
    isOnline,
    isCompactViewport,
    sortKey,
    sortOrder,
    onToggleFavorite,
    onEdit,
    onOpenConflictResolution,
    renderActions,
    renderTitleMeta,
    favoriteButtonTestId,
    labels,
    formatRelativeTime = defaultFormatRelativeTime
  } = options

  const resolvedLabels: PromptTableColumnLabels = {
    title: labels?.title || "Title",
    preview: labels?.preview || "Preview",
    tags: labels?.tags || "Tags",
    updated: labels?.updated || "Updated",
    status: labels?.status || "Status",
    actions: labels?.actions || "Actions",
    author: labels?.author || "Author",
    system: labels?.system || "System",
    user: labels?.user || "User",
    unknown: labels?.unknown || "Unknown",
    offlineStatus:
      labels?.offlineStatus ||
      "Sync unavailable while offline. Showing last known state.",
    edit: labels?.edit || "Edit"
  }

  const columns: ColumnsType<PromptRowVM> = [
    {
      title: "",
      key: "favorite",
      dataIndex: "favorite",
      width: 52,
      render: (_value, record) => (
        <button
          type="button"
          aria-label={record.favorite ? "Unfavorite prompt" : "Favorite prompt"}
          aria-pressed={record.favorite}
          data-testid={favoriteButtonTestId?.(record)}
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onToggleFavorite?.(record, !record.favorite)
          }}
          className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded transition-colors ${
            record.favorite
              ? "text-warn"
              : "text-text-muted hover:text-warn hover:bg-surface2"
          }`}
        >
          <Star className={`size-4 ${record.favorite ? "fill-current" : ""}`} />
        </button>
      )
    },
    {
      title: resolvedLabels.title,
      dataIndex: "title",
      key: "title",
      sorter: true,
      sortOrder: sortKey === "title" ? sortOrder || undefined : undefined,
      render: (_value, record) => (
        <div className="flex max-w-64 flex-col">
          <span className="line-clamp-1 font-medium text-text">
            {record.title}
          </span>
          {record.author ? (
            <span className="text-xs text-text-muted">
              {resolvedLabels.author}: {record.author}
            </span>
          ) : null}
          {record.details ? (
            <span className="line-clamp-2 text-xs text-text-muted">{record.details}</span>
          ) : null}
          {renderTitleMeta?.(record)}
        </div>
      )
    },
    {
      title: resolvedLabels.preview,
      key: "preview",
      render: (_value, record) => renderPreview(record, isCompactViewport, resolvedLabels)
    },
    ...(!isCompactViewport
      ? [
          {
            title: resolvedLabels.tags,
            key: "keywords",
            render: (_value: unknown, record: PromptRowVM) => (
              <div className="flex max-w-64 flex-wrap gap-1">
                {(record.keywords || []).map((keyword) => (
                  <Tag key={`${record.id}-${keyword}`}>{keyword}</Tag>
                ))}
              </div>
            )
          },
          {
            title: resolvedLabels.updated,
            key: "modifiedAt",
            width: 132,
            sorter: true,
            sortOrder: sortKey === "modifiedAt" ? sortOrder || undefined : undefined,
            render: (_value: unknown, record: PromptRowVM) => (
              <Tooltip
                title={
                  record.updatedAt
                    ? new Date(record.updatedAt).toLocaleString()
                    : resolvedLabels.unknown
                }
              >
                <span className="text-xs text-text-muted">
                  {formatRelativeTime(record.updatedAt)}
                </span>
              </Tooltip>
            )
          },
          {
            title: resolvedLabels.status,
            key: "syncStatus",
            width: 124,
            render: (_value: unknown, record: PromptRowVM) => (
              <Tooltip
                title={
                  !isOnline
                    ? resolvedLabels.offlineStatus
                    : undefined
                }
              >
                <div className={!isOnline ? "opacity-60" : undefined}>
                  <SyncStatusBadge
                    syncStatus={record.syncStatus}
                    sourceSystem={record.sourceSystem}
                    serverId={record.serverId}
                    compact={false}
                    onClick={
                      record.syncStatus === "conflict"
                        ? () => onOpenConflictResolution?.(record)
                        : undefined
                    }
                  />
                </div>
              </Tooltip>
            )
          }
        ]
      : []),
    {
      title: resolvedLabels.actions,
      key: "actions",
      width: isCompactViewport ? 112 : 156,
      render: (_value, record) =>
        renderActions ? (
          renderActions(record)
        ) : (
          <button
            type="button"
            className="rounded border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              onEdit?.(record)
            }}
          >
            {resolvedLabels.edit}
          </button>
        )
    }
  ]

  return columns
}
