import React from "react"
import { PromptBulkActionBar } from "./PromptBulkActionBar"
import { PromptInspectorPanel } from "./PromptInspectorPanel"
import { PromptListTable } from "./PromptListTable"
import { PromptListToolbar } from "./PromptListToolbar"
import { usePromptWorkspaceState } from "./usePromptWorkspaceState"
import type { PromptRowVM } from "./prompt-workspace-types"

type PromptBodyContainerProps = {
  rows: PromptRowVM[]
  total: number
  loading?: boolean
  isOnline: boolean
  allTags: string[]
  onCreatePrompt?: () => void
  onImportPrompts?: () => void
  onExportPrompts?: () => void
  onEditPrompt?: (id: string) => void
  onUsePromptInChat?: (id: string) => void
  onDuplicatePrompt?: (id: string) => void
  onDeletePrompt?: (id: string) => void
  onToggleFavorite?: (id: string, nextFavorite: boolean) => void
}

export const PromptBodyContainer: React.FC<PromptBodyContainerProps> = ({
  rows,
  total,
  loading = false,
  isOnline,
  allTags,
  onCreatePrompt,
  onImportPrompts,
  onExportPrompts,
  onEditPrompt,
  onUsePromptInChat,
  onDuplicatePrompt,
  onDeletePrompt,
  onToggleFavorite
}) => {
  const { state, setQuery, setSelection, clearSelection, openPanel, closePanel } =
    usePromptWorkspaceState()

  const activePrompt = React.useMemo(
    () => rows.find((row) => row.id === state.panel.promptId) || null,
    [rows, state.panel.promptId]
  )

  return (
    <div data-testid="prompts-body-container-scaffold" className="space-y-3">
      <PromptListToolbar
        query={state.query}
        allTags={allTags}
        onQueryChange={setQuery}
        onCreatePrompt={onCreatePrompt}
        onImportPrompts={onImportPrompts}
        onExportPrompts={onExportPrompts}
      />

      <PromptBulkActionBar
        selectedCount={state.selection.selectedIds.length}
        onClearSelection={clearSelection}
      />

      <PromptListTable
        rows={rows}
        total={total}
        loading={loading}
        isOnline={isOnline}
        isCompactViewport={state.isCompactViewport}
        query={state.query}
        selectedIds={state.selection.selectedIds}
        onQueryChange={setQuery}
        onSelectionChange={setSelection}
        onRowOpen={openPanel}
        onEdit={onEditPrompt}
        onToggleFavorite={onToggleFavorite}
      />

      <PromptInspectorPanel
        open={state.panel.open}
        prompt={activePrompt}
        onClose={closePanel}
        onEdit={onEditPrompt}
        onUseInChat={onUsePromptInChat}
        onDuplicate={onDuplicatePrompt}
        onDelete={onDeletePrompt}
      />
    </div>
  )
}
