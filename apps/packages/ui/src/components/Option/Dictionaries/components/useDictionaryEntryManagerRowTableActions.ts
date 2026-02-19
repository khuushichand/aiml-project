import { useDictionaryEntryRowOperations } from "./useDictionaryEntryRowOperations"
import { useDictionaryEntryListTable } from "./useDictionaryEntryListTable"
import { useDictionaryEntryManagerContext } from "./useDictionaryEntryManagerContext"

type UseDictionaryEntryManagerRowTableActionsParams = {
  dictionaryId: number
  context: ReturnType<typeof useDictionaryEntryManagerContext>
  inlineEdit: any
  setInlineEdit: (value: any) => void
  inlineEditError: string | null
  setInlineEditError: (value: string | null) => void
  inlineEditSaving: boolean
  startInlineEdit: (entry: any, field: "pattern" | "replacement") => void
  cancelInlineEdit: () => void
  saveInlineEdit: () => Promise<void>
  onOpenEditEntry: (entry: any) => void
}

export function useDictionaryEntryManagerRowTableActions({
  dictionaryId,
  context,
  inlineEdit,
  setInlineEdit,
  inlineEditError,
  setInlineEditError,
  inlineEditSaving,
  startInlineEdit,
  cancelInlineEdit,
  saveInlineEdit,
  onOpenEditEntry,
}: UseDictionaryEntryManagerRowTableActionsParams) {
  const {
    selectedEntryRowKeys,
    setSelectedEntryRowKeys,
    selectedEntryIds,
    canEscalateSelectAllFilteredEntries,
    bulkGroupName,
    setBulkGroupName,
    bulkEntryAction,
    reorderBusyEntryId,
    handleSelectAllFilteredEntries,
    handleBulkEntryAction,
    handleMoveEntry,
    handleDeleteEntryWithUndo,
  } = useDictionaryEntryRowOperations({
    dictionaryId,
    entries: context.entries,
    allEntries: context.allEntries,
    allEntriesById: context.allEntriesById,
    filteredEntryIds: context.filteredEntryIds,
    orderedEntryIds: context.orderedEntryIds,
    canReorderEntries: context.canReorderEntries,
    entriesQueryKey: context.entriesQueryKey,
    allEntriesQueryKey: context.allEntriesQueryKey,
    confirmDanger: context.confirmDanger,
    notification: context.notification,
    queryClient: context.queryClient,
    showUndoNotification: context.showUndoNotification,
    t: context.t,
  })

  const { entryTableColumns } = useDictionaryEntryListTable({
    inlineEdit,
    setInlineEdit,
    inlineEditError,
    setInlineEditError,
    inlineEditSaving,
    cancelInlineEdit,
    saveInlineEdit,
    startInlineEdit,
    entryPriorityById: context.entryPriorityById,
    reorderBusyEntryId,
    canReorderEntries: context.canReorderEntries,
    orderedEntryCount: context.orderedEntryIds.length,
    onMoveEntry: handleMoveEntry,
    onOpenEditEntry,
    onDeleteEntry: handleDeleteEntryWithUndo,
  })

  return {
    selectedEntryRowKeys,
    setSelectedEntryRowKeys,
    selectedEntryIds,
    canEscalateSelectAllFilteredEntries,
    bulkGroupName,
    setBulkGroupName,
    bulkEntryAction,
    handleSelectAllFilteredEntries,
    handleBulkEntryAction,
    entryTableColumns,
  }
}
