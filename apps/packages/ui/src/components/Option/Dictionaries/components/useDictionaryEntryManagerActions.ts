import { useDictionaryEntryCreate } from "./useDictionaryEntryCreate"
import { useDictionaryInlineEdit } from "./useDictionaryInlineEdit"
import { useDictionaryRegexSafetyValidation } from "./useDictionaryRegexSafetyValidation"
import { useDictionaryEntryEdit } from "./useDictionaryEntryEdit"
import { useDictionaryEntryManagerContext } from "./useDictionaryEntryManagerContext"
import { useDictionaryEntryManagerRowTableActions } from "./useDictionaryEntryManagerRowTableActions"

type UseDictionaryEntryManagerActionsParams = {
  dictionaryId: number
  form: any
  context: ReturnType<typeof useDictionaryEntryManagerContext>
}

export function useDictionaryEntryManagerActions({
  dictionaryId,
  form,
  context,
}: UseDictionaryEntryManagerActionsParams) {
  const { validateRegexWithServer } = useDictionaryRegexSafetyValidation({
    dictionaryName: context.dictionaryMeta?.name,
  })

  const {
    adding,
    advancedMode,
    toggleAdvancedMode,
    regexError,
    regexServerError,
    handleAddEntrySubmit,
    handleAddEntryPatternChange,
    handleAddEntryReplacementChange,
    handleAddEntryTypeChange,
  } = useDictionaryEntryCreate({
    dictionaryId,
    form,
    allEntriesQueryKey: context.allEntriesQueryKey,
    validateRegexWithServer,
  })

  const {
    inlineEdit,
    setInlineEdit,
    inlineEditError,
    setInlineEditError,
    inlineEditSaving,
    startInlineEdit,
    cancelInlineEdit,
    saveInlineEdit,
  } = useDictionaryInlineEdit({
    dictionaryId,
    allEntriesById: context.allEntriesById,
    allEntriesQueryKey: context.allEntriesQueryKey,
    notification: context.notification,
    queryClient: context.queryClient,
    validateRegexWithServer,
  })

  const {
    editingEntry,
    updatingEntry,
    openEditEntryPanel,
    closeEditEntryPanel,
    handleEditEntrySubmit,
  } = useDictionaryEntryEdit({
    dictionaryId,
    allEntriesQueryKey: context.allEntriesQueryKey,
    editEntryForm: context.editEntryForm,
    notification: context.notification,
    queryClient: context.queryClient,
    validateRegexWithServer,
  })

  const {
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
  } = useDictionaryEntryManagerRowTableActions({
    dictionaryId,
    context,
    inlineEdit,
    setInlineEdit,
    inlineEditError,
    setInlineEditError,
    inlineEditSaving,
    cancelInlineEdit,
    saveInlineEdit,
    startInlineEdit,
    onOpenEditEntry: openEditEntryPanel,
  })

  return {
    editingEntry,
    updatingEntry,
    closeEditEntryPanel,
    handleEditEntrySubmit,
    entryTableColumns,
    selectedEntryRowKeys,
    setSelectedEntryRowKeys,
    selectedEntryIds,
    canEscalateSelectAllFilteredEntries,
    bulkGroupName,
    setBulkGroupName,
    bulkEntryAction,
    handleSelectAllFilteredEntries,
    handleBulkEntryAction,
    adding,
    advancedMode,
    toggleAdvancedMode,
    handleAddEntrySubmit,
    handleAddEntryPatternChange,
    handleAddEntryReplacementChange,
    handleAddEntryTypeChange,
    regexError,
    regexServerError,
  }
}
