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
  AlertTriangle
} from "lucide-react"
import { Input, Checkbox, Empty, Button, Tooltip } from "antd"
import { useWorkspaceStore } from "@/store/workspace"
import type { WorkspaceSourceType } from "@/types/workspace"
import {
  WORKSPACE_SOURCE_DRAG_TYPE,
  serializeWorkspaceSourceDragPayload
} from "../drag-source"
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

interface SourcesPaneProps {
  /** Callback to hide/collapse the pane */
  onHide?: () => void
}

/**
 * SourcesPane - Left pane for managing research sources
 */
export const SourcesPane: React.FC<SourcesPaneProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "common"])

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
  const sourceItemRefs = React.useRef<Record<string, HTMLDivElement | null>>({})
  const [highlightedSourceId, setHighlightedSourceId] = React.useState<
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

  const allSelected =
    sources.length > 0 && selectedSourceIds.length === sources.length
  const someSelected = selectedSourceIds.length > 0 && !allSelected

  const handleSelectAllToggle = () => {
    if (allSelected || someSelected) {
      deselectAllSources()
    } else {
      selectAllSources()
    }
  }

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
    setSourceSearchQuery
  ])

  return (
    <div className="flex h-full flex-col">
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
      <div className="custom-scrollbar flex-1 overflow-y-auto">
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
        ) : (
          <div className="space-y-1 p-2">
            {filteredSources.map((source) => {
              const Icon = SOURCE_TYPE_ICONS[source.type] || File
              const isSelected = selectedSourceIds.includes(source.id)
              const isHighlighted = highlightedSourceId === source.id
              const sourceStatus = source.status || "ready"
              const isReady = sourceStatus === "ready"
              const isProcessing = sourceStatus === "processing"
              const isError = sourceStatus === "error"

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
                  className={`group flex items-start gap-2 rounded-lg p-2 transition-colors ${
                    isSelected
                      ? "bg-primary/10 border border-primary/30"
                      : "hover:bg-surface2 border border-transparent"
                  } ${
                    isHighlighted
                      ? "ring-2 ring-primary/40 border-primary/40 bg-primary/15"
                      : ""
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
                  <button
                    type="button"
                    onClick={() => removeSource(source.id)}
                    data-testid={`remove-source-${source.id}`}
                    className="shrink-0 rounded p-1 text-text-muted opacity-0 transition hover:bg-error/10 hover:text-error group-hover:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:min-h-11 [@media(hover:none)]:min-w-11 [@media(hover:none)]:opacity-100"
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
                </div>
              )
            })}
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
      <AddSourceModal />
    </div>
  )
}

export default SourcesPane
