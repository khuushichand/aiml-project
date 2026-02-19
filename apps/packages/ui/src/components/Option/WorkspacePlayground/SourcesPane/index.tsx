import React from "react"
import { useTranslation } from "react-i18next"
import {
  Plus,
  Search,
  FileText,
  Video,
  Headphones,
  Globe,
  File,
  Type,
  PanelLeftClose,
  Loader2,
  AlertTriangle,
  Info,
  Eye,
  ChevronUp,
  ChevronDown
} from "lucide-react"
import {
  Input,
  Checkbox,
  Empty,
  Button,
  Tooltip,
  message,
  Popconfirm,
  Modal
} from "antd"
import { useWorkspaceStore } from "@/store/workspace"
import type { WorkspaceSourceType } from "@/types/workspace"
import {
  WORKSPACE_SOURCE_DRAG_TYPE,
  serializeWorkspaceSourceDragPayload
} from "../drag-source"
import {
  WORKSPACE_UNDO_WINDOW_MS,
  scheduleWorkspaceUndoAction,
  undoWorkspaceAction
} from "../undo-manager"
import { AddSourceModal } from "./AddSourceModal"

// Icon mapping for source types
const SOURCE_TYPE_ICONS: Record<WorkspaceSourceType, React.ElementType> = {
  pdf: FileText,
  video: Video,
  audio: Headphones,
  website: Globe,
  document: File,
  text: Type
}

const SOURCE_VIRTUALIZATION_THRESHOLD = 60
const SOURCE_VIRTUAL_ROW_HEIGHT = 80
const SOURCE_VIRTUAL_OVERSCAN = 5

const formatFileSize = (bytes?: number): string | null => {
  if (!Number.isFinite(bytes) || (bytes as number) <= 0) return null
  const value = bytes as number
  if (value >= 1024 * 1024 * 1024) return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`
  if (value >= 1024 * 1024) return `${Math.round(value / (1024 * 1024))} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${Math.round(value)} B`
}

const formatDuration = (seconds?: number): string | null => {
  if (!Number.isFinite(seconds) || (seconds as number) <= 0) return null
  const totalSeconds = Math.round(seconds as number)
  const hrs = Math.floor(totalSeconds / 3600)
  const mins = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  if (hrs > 0) {
    return `${hrs}h ${mins}m`
  }
  if (mins > 0) {
    return `${mins}m ${secs}s`
  }
  return `${secs}s`
}

type SourceAnnotation = {
  id: string
  quote: string
  note: string
  createdAt: number
  updatedAt: number
}

interface SourcesPaneProps {
  /** Callback to hide/collapse the pane */
  onHide?: () => void
}

/**
 * SourcesPane - Left pane for managing research sources
 */
export const SourcesPane: React.FC<SourcesPaneProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "common"])
  const [messageApi, messageContextHolder] = message.useMessage()

  // Store state
  const sources = useWorkspaceStore((s) => s.sources)
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const sourceSearchQuery = useWorkspaceStore((s) => s.sourceSearchQuery)
  const sourceFocusTarget = useWorkspaceStore((s) => s.sourceFocusTarget)

  // Store actions
  const toggleSourceSelection = useWorkspaceStore((s) => s.toggleSourceSelection)
  const selectAllSources = useWorkspaceStore((s) => s.selectAllSources)
  const deselectAllSources = useWorkspaceStore((s) => s.deselectAllSources)
  const setSourceSearchQuery = useWorkspaceStore((s) => s.setSourceSearchQuery)
  const clearSourceFocusTarget = useWorkspaceStore(
    (s) => s.clearSourceFocusTarget
  )
  const openAddSourceModal = useWorkspaceStore((s) => s.openAddSourceModal)
  const removeSource = useWorkspaceStore((s) => s.removeSource)
  const restoreSource = useWorkspaceStore((s) => s.restoreSource)
  const reorderSource = useWorkspaceStore((s) => s.reorderSource)
  const sourceItemRefs = React.useRef<Record<string, HTMLDivElement | null>>({})
  const sourceListContainerRef = React.useRef<HTMLDivElement | null>(null)
  const [highlightedSourceId, setHighlightedSourceId] = React.useState<
    string | null
  >(null)
  const [sourceListScrollTop, setSourceListScrollTop] = React.useState(0)
  const [sourceListViewportHeight, setSourceListViewportHeight] =
    React.useState(420)
  const [confirmingRemovalSourceId, setConfirmingRemovalSourceId] =
    React.useState<string | null>(null)
  const [draggedSourceId, setDraggedSourceId] = React.useState<string | null>(null)
  const [previewSourceId, setPreviewSourceId] = React.useState<string | null>(null)
  const [sourceAnnotations, setSourceAnnotations] = React.useState<
    Record<string, SourceAnnotation[]>
  >({})
  const [annotationQuoteDraft, setAnnotationQuoteDraft] = React.useState("")
  const [annotationNoteDraft, setAnnotationNoteDraft] = React.useState("")
  const [editingAnnotationId, setEditingAnnotationId] = React.useState<
    string | null
  >(null)

  // Filter sources based on search query
  const filteredSources = React.useMemo(() => {
    if (!sourceSearchQuery.trim()) return sources
    const query = sourceSearchQuery.toLowerCase()
    return sources.filter((source) =>
      source.title.toLowerCase().includes(query)
    )
  }, [sources, sourceSearchQuery])

  const useVirtualizedSources =
    filteredSources.length > SOURCE_VIRTUALIZATION_THRESHOLD
  const virtualStartIndex = useVirtualizedSources
    ? Math.max(
        0,
        Math.floor(sourceListScrollTop / SOURCE_VIRTUAL_ROW_HEIGHT) -
          SOURCE_VIRTUAL_OVERSCAN
      )
    : 0
  const virtualEndIndex = useVirtualizedSources
    ? Math.min(
        filteredSources.length,
        Math.ceil(
          (sourceListScrollTop + sourceListViewportHeight) /
            SOURCE_VIRTUAL_ROW_HEIGHT
        ) + SOURCE_VIRTUAL_OVERSCAN
      )
    : filteredSources.length
  const visibleSources = useVirtualizedSources
    ? filteredSources.slice(virtualStartIndex, virtualEndIndex)
    : filteredSources

  const allSelected =
    sources.length > 0 && selectedSourceIds.length === sources.length
  const someSelected = selectedSourceIds.length > 0 && !allSelected
  const previewSource = previewSourceId
    ? sources.find((source) => source.id === previewSourceId) || null
    : null
  const previewAnnotations = previewSourceId
    ? sourceAnnotations[previewSourceId] || []
    : []

  const handleSelectAllToggle = () => {
    if (allSelected || someSelected) {
      deselectAllSources()
    } else {
      selectAllSources()
    }
  }

  const resetAnnotationEditor = React.useCallback(() => {
    setAnnotationQuoteDraft("")
    setAnnotationNoteDraft("")
    setEditingAnnotationId(null)
  }, [])

  const handleOpenPreview = React.useCallback(
    (sourceId: string) => {
      setPreviewSourceId(sourceId)
      resetAnnotationEditor()
    },
    [resetAnnotationEditor]
  )

  const handleClosePreview = React.useCallback(() => {
    setPreviewSourceId(null)
    resetAnnotationEditor()
  }, [resetAnnotationEditor])

  const handleSaveAnnotation = React.useCallback(() => {
    if (!previewSourceId) return
    const quote = annotationQuoteDraft.trim()
    const note = annotationNoteDraft.trim()
    if (!quote && !note) {
      messageApi.warning(
        t(
          "playground:sources.annotationEmpty",
          "Add a highlight excerpt or an annotation note."
        )
      )
      return
    }

    setSourceAnnotations((previous) => {
      const existing = previous[previewSourceId] || []
      const now = Date.now()
      if (editingAnnotationId) {
        return {
          ...previous,
          [previewSourceId]: existing.map((annotation) =>
            annotation.id === editingAnnotationId
              ? {
                  ...annotation,
                  quote,
                  note,
                  updatedAt: now
                }
              : annotation
          )
        }
      }

      const nextAnnotation: SourceAnnotation = {
        id: `${previewSourceId}-${now}-${Math.random().toString(36).slice(2, 7)}`,
        quote,
        note,
        createdAt: now,
        updatedAt: now
      }
      return {
        ...previous,
        [previewSourceId]: [nextAnnotation, ...existing]
      }
    })
    resetAnnotationEditor()
  }, [
    annotationNoteDraft,
    annotationQuoteDraft,
    editingAnnotationId,
    messageApi,
    previewSourceId,
    resetAnnotationEditor,
    t
  ])

  const handleEditAnnotation = React.useCallback((annotation: SourceAnnotation) => {
    setAnnotationQuoteDraft(annotation.quote)
    setAnnotationNoteDraft(annotation.note)
    setEditingAnnotationId(annotation.id)
  }, [])

  const handleDeleteAnnotation = React.useCallback(
    (annotationId: string) => {
      if (!previewSourceId) return
      setSourceAnnotations((previous) => {
        const existing = previous[previewSourceId] || []
        return {
          ...previous,
          [previewSourceId]: existing.filter(
            (annotation) => annotation.id !== annotationId
          )
        }
      })
      if (editingAnnotationId === annotationId) {
        resetAnnotationEditor()
      }
    },
    [editingAnnotationId, previewSourceId, resetAnnotationEditor]
  )

  const removeSourceWithUndo = React.useCallback(
    (source: (typeof sources)[number]) => {
      const sourceIndex = sources.findIndex((entry) => entry.id === source.id)
      const wasSelected = selectedSourceIds.includes(source.id)
      const undoHandle = scheduleWorkspaceUndoAction({
        apply: () => {
          removeSource(source.id)
        },
        undo: () => {
          restoreSource(source, {
            index: sourceIndex,
            select: wasSelected
          })
        }
      })

      const undoMessageKey = `workspace-source-undo-${undoHandle.id}`
      const maybeOpen = (
        messageApi as { open?: (config: unknown) => void }
      ).open
      const messageConfig = {
        key: undoMessageKey,
        type: "warning",
        duration: WORKSPACE_UNDO_WINDOW_MS / 1000,
        content: t(
          "playground:sources.undoRemove",
          "Source removed."
        ),
        btn: (
          <Button
            size="small"
            type="link"
            onClick={() => {
              if (undoWorkspaceAction(undoHandle.id)) {
                messageApi.success(
                  t("playground:sources.restoreSuccess", "Source restored")
                )
              }
              messageApi.destroy(undoMessageKey)
            }}
          >
            {t("common:undo", "Undo")}
          </Button>
        )
      }
      if (typeof maybeOpen === "function") {
        maybeOpen(messageConfig)
      } else {
        const maybeWarning = (
          messageApi as { warning?: (content: string) => void }
        ).warning
        if (typeof maybeWarning === "function") {
          maybeWarning(t("playground:sources.undoRemove", "Source removed."))
        }
      }
    },
    [messageApi, removeSource, restoreSource, selectedSourceIds, sources, t]
  )

  React.useEffect(() => {
    const container = sourceListContainerRef.current
    if (!container) return

    const syncViewportHeight = () => {
      setSourceListViewportHeight(container.clientHeight || 420)
    }

    syncViewportHeight()

    if (typeof ResizeObserver === "undefined") {
      return
    }

    const observer = new ResizeObserver(() => {
      syncViewportHeight()
    })
    observer.observe(container)
    return () => {
      observer.disconnect()
    }
  }, [filteredSources.length])

  React.useEffect(() => {
    const targetSourceId = sourceFocusTarget?.sourceId
    if (!targetSourceId) return

    const sourceExists = sources.some((source) => source.id === targetSourceId)
    if (!sourceExists) {
      clearSourceFocusTarget()
      return
    }

    const isTargetVisible = filteredSources.some(
      (source) => source.id === targetSourceId
    )
    if (!isTargetVisible && sourceSearchQuery.trim()) {
      setSourceSearchQuery("")
    }

    if (useVirtualizedSources && sourceListContainerRef.current) {
      const targetIndex = filteredSources.findIndex(
        (source) => source.id === targetSourceId
      )
      if (targetIndex >= 0) {
        const targetScrollTop = targetIndex * SOURCE_VIRTUAL_ROW_HEIGHT
        sourceListContainerRef.current.scrollTop = targetScrollTop
        setSourceListScrollTop(targetScrollTop)
      }
    }

    const revealTimer = window.setTimeout(() => {
      const element = sourceItemRefs.current[targetSourceId]
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "nearest" })
      }
      setHighlightedSourceId(targetSourceId)
    }, 0)

    const highlightTimer = window.setTimeout(() => {
      setHighlightedSourceId((current) =>
        current === targetSourceId ? null : current
      )
    }, 1800)

    clearSourceFocusTarget()

    return () => {
      window.clearTimeout(revealTimer)
      window.clearTimeout(highlightTimer)
    }
  }, [
    clearSourceFocusTarget,
    filteredSources,
    sourceFocusTarget,
    sourceSearchQuery,
    sources,
    setSourceSearchQuery,
    useVirtualizedSources
  ])

  const renderSourceRow = (source: (typeof filteredSources)[number]) => {
    const Icon = SOURCE_TYPE_ICONS[source.type] || File
    const isSelected = selectedSourceIds.includes(source.id)
    const isHighlighted = highlightedSourceId === source.id
    const sourceStatus = source.status || "ready"
    const isReady = sourceStatus === "ready"
    const isProcessing = sourceStatus === "processing"
    const isError = sourceStatus === "error"
    const metadataParts: string[] = []
    const fileSizeLabel = formatFileSize(source.fileSize)
    const durationLabel = formatDuration(source.duration)
    const pageCountLabel =
      Number.isFinite(source.pageCount) && (source.pageCount as number) > 0
        ? `${source.pageCount} pages`
        : null
    if (fileSizeLabel) metadataParts.push(fileSizeLabel)
    if (durationLabel) metadataParts.push(durationLabel)
    if (pageCountLabel) metadataParts.push(pageCountLabel)
    const sourceDate = source.sourceCreatedAt || source.addedAt
    metadataParts.push(
      source.sourceCreatedAt
        ? t("playground:sources.createdAt", "Created {{date}}", {
            date: sourceDate.toLocaleDateString()
          })
        : t("playground:sources.addedAt", "Added {{date}}", {
            date: sourceDate.toLocaleDateString()
          })
    )
    const metadataPreview = metadataParts.slice(0, 2).join(" • ")
    const metadataTooltip = metadataParts.join(" • ")
    const sourceOrderIndex = sources.findIndex((entry) => entry.id === source.id)
    const canMoveUp = sourceOrderIndex > 0
    const canMoveDown = sourceOrderIndex >= 0 && sourceOrderIndex < sources.length - 1
    const isDropTarget = draggedSourceId != null && draggedSourceId !== source.id

    return (
      <div
        key={source.id}
        data-source-id={source.id}
        data-source-draggable="true"
        data-highlighted={isHighlighted ? "true" : "false"}
        ref={(element) => {
          sourceItemRefs.current[source.id] = element
        }}
        draggable={isReady}
        onDragStart={(event) => {
          if (!isReady) {
            event.preventDefault()
            return
          }
          setDraggedSourceId(source.id)
          event.dataTransfer.effectAllowed = "copyMove"
          event.dataTransfer.setData(
            WORKSPACE_SOURCE_DRAG_TYPE,
            serializeWorkspaceSourceDragPayload({
              sourceId: source.id,
              mediaId: source.mediaId,
              title: source.title,
              type: source.type
            })
          )
          event.dataTransfer.setData("text/plain", source.title)
        }}
        onDragOver={(event) => {
          if (!isReady || !draggedSourceId || draggedSourceId === source.id) return
          event.preventDefault()
          event.dataTransfer.dropEffect = "move"
        }}
        onDrop={(event) => {
          if (!isReady || !draggedSourceId || draggedSourceId === source.id) return
          event.preventDefault()
          const targetIndex = sources.findIndex((entry) => entry.id === source.id)
          if (targetIndex >= 0) {
            reorderSource(draggedSourceId, targetIndex)
          }
          setDraggedSourceId(null)
        }}
        onDragEnd={() => setDraggedSourceId(null)}
        className={`group flex items-start gap-2 rounded-lg p-2 transition-colors ${
          isSelected
            ? "bg-primary/10 border border-primary/30"
            : "hover:bg-surface2 border border-transparent"
        } ${
          isHighlighted
            ? "ring-2 ring-primary/40 border-primary/40 bg-primary/15"
            : ""
        } ${
          isDropTarget ? "border-primary/50 bg-primary/5" : ""
        } ${isReady ? "cursor-grab active:cursor-grabbing" : "cursor-default"}`}
      >
        <div
          data-testid={`source-checkbox-hitarea-${source.id}`}
          className="mt-0.5 flex items-center justify-center [@media(hover:none)]:min-h-11 [@media(hover:none)]:min-w-11"
        >
          <Checkbox
            checked={isSelected}
            disabled={!isReady}
            onChange={() => toggleSourceSelection(source.id)}
          />
        </div>
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded ${
              isSelected ? "bg-primary/20 text-primary" : "bg-surface2 text-text-muted"
            }`}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">
              {source.title}
            </p>
            <p className="truncate text-xs text-text-muted capitalize">
              {source.type}
            </p>
            <Tooltip title={metadataTooltip}>
              <p className="mt-0.5 inline-flex max-w-full items-center gap-1 truncate text-[11px] text-text-subtle">
                <Info className="h-3 w-3 shrink-0" />
                <span className="truncate">{metadataPreview}</span>
              </p>
            </Tooltip>
            {isProcessing && (
              <p className="mt-0.5 flex items-center gap-1 text-[11px] text-primary">
                <Loader2 className="h-3 w-3 animate-spin" />
                {t("playground:sources.statusProcessing", "Processing")}
              </p>
            )}
            {isError && (
              <p
                className="mt-0.5 flex items-center gap-1 text-[11px] text-error"
                title={source.statusMessage || undefined}
              >
                <AlertTriangle className="h-3 w-3" />
                {source.statusMessage ||
                  t(
                    "playground:sources.statusError",
                    "Source processing failed"
                  )}
              </p>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-start gap-1">
          <Tooltip title={t("playground:sources.previewAnnotate", "Preview & annotate")}>
            <button
              type="button"
              onClick={() => handleOpenPreview(source.id)}
              data-testid={`preview-source-${source.id}`}
              className="rounded p-1 text-text-muted transition hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label={t(
                "playground:sources.previewAnnotate",
                "Preview & annotate"
              )}
            >
              <Eye className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
          <div className="flex flex-col">
            <button
              type="button"
              className="rounded p-0.5 text-text-muted transition hover:bg-surface focus-visible:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={t("playground:sources.moveUp", "Move source up")}
              data-testid={`move-source-up-${source.id}`}
              disabled={!canMoveUp}
              onClick={() => {
                if (!canMoveUp) return
                reorderSource(source.id, sourceOrderIndex - 1)
              }}
            >
              <ChevronUp className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              className="rounded p-0.5 text-text-muted transition hover:bg-surface focus-visible:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={t("playground:sources.moveDown", "Move source down")}
              data-testid={`move-source-down-${source.id}`}
              disabled={!canMoveDown}
              onClick={() => {
                if (!canMoveDown) return
                reorderSource(source.id, sourceOrderIndex + 1)
              }}
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          </div>
          <Popconfirm
            open={confirmingRemovalSourceId === source.id}
            title={t("playground:sources.confirmRemoveTitle", "Remove source?")}
            description={t(
              "playground:sources.confirmRemoveDescription",
              "Press Remove to confirm. You can still undo for a few seconds."
            )}
            okText={t("common:remove", "Remove")}
            cancelText={t("common:cancel", "Cancel")}
            onConfirm={() => {
              setConfirmingRemovalSourceId(null)
              removeSourceWithUndo(source)
            }}
            onCancel={() => setConfirmingRemovalSourceId(null)}
          >
            <button
              type="button"
              onClick={() => {
                if (confirmingRemovalSourceId === source.id) return
                removeSourceWithUndo(source)
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault()
                  setConfirmingRemovalSourceId(source.id)
                }
              }}
              data-testid={`remove-source-${source.id}`}
              className="rounded p-1 text-text-muted opacity-0 transition hover:bg-error/10 hover:text-error group-hover:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:min-h-11 [@media(hover:none)]:min-w-11 [@media(hover:none)]:opacity-100"
              aria-label={t("common:remove", "Remove")}
            >
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </Popconfirm>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {messageContextHolder}
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text">
          {t("playground:sources.title", "Sources")}
        </h2>
        <div className="flex items-center gap-2">
          <Button
            type="primary"
            size="small"
            icon={<Plus className="h-3.5 w-3.5" />}
            onClick={() => openAddSourceModal()}
          >
            {t("playground:sources.add", "Add")}
          </Button>
          {onHide && (
            <Tooltip title={t("playground:workspace.hideSources", "Hide sources")}>
              <button
                type="button"
                onClick={onHide}
                className="hidden rounded p-1.5 text-text-muted transition hover:bg-surface2 hover:text-text lg:block"
                aria-label={t("playground:workspace.hideSources", "Hide sources")}
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Search and select controls */}
      {sources.length > 0 && (
        <div className="border-b border-border px-4 py-2">
          <Input
            prefix={<Search className="h-4 w-4 text-text-muted" />}
            placeholder={t("playground:sources.searchPlaceholder", "Search sources...")}
            value={sourceSearchQuery}
            onChange={(e) => setSourceSearchQuery(e.target.value)}
            size="small"
            allowClear
          />
          <div className="mt-2 flex items-center justify-between text-xs">
            <Checkbox
              checked={allSelected}
              indeterminate={someSelected}
              onChange={handleSelectAllToggle}
              className="[@media(hover:none)]:min-h-11 [@media(hover:none)]:min-w-11"
            >
              <span className="text-text-muted">
                {selectedSourceIds.length > 0
                  ? t("playground:sources.selectedCount", "{{count}} selected", {
                      count: selectedSourceIds.length
                    })
                  : t("playground:sources.selectAll", "Select all")}
              </span>
            </Checkbox>
            {selectedSourceIds.length > 0 && (
              <button
                type="button"
                onClick={deselectAllSources}
                className="text-primary hover:underline"
              >
                {t("common:clear", "Clear")}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Source list */}
      <div
        ref={sourceListContainerRef}
        onScroll={(event) =>
          setSourceListScrollTop(event.currentTarget.scrollTop)
        }
        className="custom-scrollbar flex-1 overflow-y-auto"
      >
        {filteredSources.length === 0 ? (
          <div className="flex h-full items-center justify-center p-4">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                sources.length === 0 ? (
                  <div className="text-center">
                    <p className="text-text-muted">
                      {t("playground:sources.empty", "No sources yet")}
                    </p>
                    <p className="mt-1 text-xs text-text-subtle">
                      {t(
                        "playground:sources.emptyHint",
                        "Add PDFs, videos, or websites to start researching"
                      )}
                    </p>
                  </div>
                ) : (
                  <span className="text-text-muted">
                    {t("playground:sources.noResults", "No matching sources")}
                  </span>
                )
              }
            >
              {sources.length === 0 && (
                <Button
                  type="primary"
                  size="small"
                  icon={<Plus className="h-3.5 w-3.5" />}
                  onClick={() => openAddSourceModal()}
                >
                  {t("playground:sources.addFirst", "Add your first source")}
                </Button>
              )}
            </Empty>
          </div>
        ) : useVirtualizedSources ? (
          <div
            data-testid="sources-virtualized-list"
            style={{
              height: filteredSources.length * SOURCE_VIRTUAL_ROW_HEIGHT,
              position: "relative"
            }}
          >
            <div
              className="space-y-1 p-2"
              style={{
                transform: `translateY(${virtualStartIndex * SOURCE_VIRTUAL_ROW_HEIGHT}px)`
              }}
            >
              {visibleSources.map((source) => renderSourceRow(source))}
            </div>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {visibleSources.map((source) => renderSourceRow(source))}
          </div>
        )}
      </div>

      {/* Footer with source count */}
      {sources.length > 0 && (
        <div className="border-t border-border px-4 py-2 text-xs text-text-muted">
          {t("playground:sources.totalCount", "{{count}} source(s)", {
            count: sources.length
          })}
        </div>
      )}

      {/* Add Source Modal */}
      <Modal
        open={Boolean(previewSource)}
        title={t(
          "playground:sources.previewModalTitle",
          "Source preview and annotations"
        )}
        onCancel={handleClosePreview}
        footer={null}
        width={680}
      >
        {previewSource && (
          <div className="space-y-4">
            <div className="rounded border border-border bg-surface2/40 p-3">
              <p className="text-sm font-semibold text-text">{previewSource.title}</p>
              <p className="text-xs capitalize text-text-muted">
                {previewSource.type} • {previewSource.status || "ready"}
              </p>
              {previewSource.url && (
                <a
                  href={previewSource.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs text-primary hover:underline"
                >
                  {previewSource.url}
                </a>
              )}
            </div>

            <div className="rounded border border-border bg-surface/50 p-3">
              <p className="mb-2 text-xs font-semibold uppercase text-text-muted">
                {t("playground:sources.highlights", "Highlights & annotations")}
              </p>
              <Input
                placeholder={t(
                  "playground:sources.annotationQuotePlaceholder",
                  "Highlighted excerpt (optional)"
                )}
                value={annotationQuoteDraft}
                onChange={(event) => setAnnotationQuoteDraft(event.target.value)}
                className="mb-2"
              />
              <Input.TextArea
                placeholder={t(
                  "playground:sources.annotationNotePlaceholder",
                  "Annotation note"
                )}
                value={annotationNoteDraft}
                onChange={(event) => setAnnotationNoteDraft(event.target.value)}
                rows={3}
              />
              <div className="mt-2 flex items-center justify-end gap-2">
                {editingAnnotationId && (
                  <Button size="small" onClick={resetAnnotationEditor}>
                    {t("common:cancel", "Cancel")}
                  </Button>
                )}
                <Button
                  type="primary"
                  size="small"
                  onClick={handleSaveAnnotation}
                >
                  {editingAnnotationId
                    ? t("playground:sources.saveAnnotation", "Save annotation")
                    : t("playground:sources.addAnnotation", "Add annotation")}
                </Button>
              </div>
            </div>

            <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
              {previewAnnotations.length === 0 ? (
                <p className="text-xs text-text-muted">
                  {t("playground:sources.noAnnotations", "No annotations yet.")}
                </p>
              ) : (
                previewAnnotations.map((annotation) => (
                  <div
                    key={annotation.id}
                    data-testid={`source-annotation-${annotation.id}`}
                    className="rounded border border-border bg-surface2/40 p-2"
                  >
                    {annotation.quote && (
                      <p className="text-xs text-text-muted">
                        "{annotation.quote}"
                      </p>
                    )}
                    {annotation.note && (
                      <p className="mt-1 text-sm text-text">{annotation.note}</p>
                    )}
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-[11px] text-text-muted">
                        {new Date(annotation.updatedAt).toLocaleString()}
                      </span>
                      <div className="flex items-center gap-1">
                        <Button
                          type="text"
                          size="small"
                          onClick={() => handleEditAnnotation(annotation)}
                        >
                          {t("common:edit", "Edit")}
                        </Button>
                        <Button
                          type="text"
                          danger
                          size="small"
                          onClick={() => handleDeleteAnnotation(annotation.id)}
                        >
                          {t("common:delete", "Delete")}
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </Modal>

      <AddSourceModal />
    </div>
  )
}

export default SourcesPane
