import React from "react"
import { useTranslation } from "react-i18next"
import { Plus, Search, FileText, Video, Headphones, Globe, File, Type } from "lucide-react"
import { Input, Checkbox, Empty, Button } from "antd"
import { useWorkspaceStore } from "@/store/workspace"
import type { WorkspaceSourceType } from "@/types/workspace"
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

/**
 * SourcesPane - Left pane for managing research sources
 */
export const SourcesPane: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])

  // Store state
  const sources = useWorkspaceStore((s) => s.sources)
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const sourceSearchQuery = useWorkspaceStore((s) => s.sourceSearchQuery)

  // Store actions
  const toggleSourceSelection = useWorkspaceStore((s) => s.toggleSourceSelection)
  const selectAllSources = useWorkspaceStore((s) => s.selectAllSources)
  const deselectAllSources = useWorkspaceStore((s) => s.deselectAllSources)
  const setSourceSearchQuery = useWorkspaceStore((s) => s.setSourceSearchQuery)
  const openAddSourceModal = useWorkspaceStore((s) => s.openAddSourceModal)
  const removeSource = useWorkspaceStore((s) => s.removeSource)

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

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text">
          {t("playground:sources.title", "Sources")}
        </h2>
        <Button
          type="primary"
          size="small"
          icon={<Plus className="h-3.5 w-3.5" />}
          onClick={() => openAddSourceModal()}
        >
          {t("playground:sources.add", "Add")}
        </Button>
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

              return (
                <div
                  key={source.id}
                  className={`group flex items-start gap-2 rounded-lg p-2 transition-colors ${
                    isSelected
                      ? "bg-primary/10 border border-primary/30"
                      : "hover:bg-surface2 border border-transparent"
                  }`}
                >
                  <Checkbox
                    checked={isSelected}
                    onChange={() => toggleSourceSelection(source.id)}
                    className="mt-0.5"
                  />
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
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeSource(source.id)}
                    className="shrink-0 rounded p-1 text-text-muted opacity-0 transition hover:bg-error/10 hover:text-error group-hover:opacity-100"
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
