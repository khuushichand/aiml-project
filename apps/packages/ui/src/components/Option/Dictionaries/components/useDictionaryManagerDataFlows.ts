import React from "react"
import { useDictionaryEntriesPanel } from "./useDictionaryEntriesPanel"
import { useDictionaryListData } from "./useDictionaryListData"
import { useDictionaryManagerWorkflows } from "./useDictionaryManagerWorkflows"

type UseDictionaryManagerDataFlowsParams = {
  isOnline: boolean
  dictionarySearch: string
  dictionaryCategoryFilter: string
  dictionaryTagFilters: string[]
  notification: {
    error: (config: { message: string; description?: string }) => void
    warning: (config: { message: string; description?: string }) => void
    success: (config: { message: string; description?: string }) => void
    info: (config: { message: string; description?: string }) => void
  }
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
  entriesDrawerFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

export function useDictionaryManagerDataFlows({
  isOnline,
  dictionarySearch,
  dictionaryCategoryFilter,
  dictionaryTagFilters,
  notification,
  queryClient,
  confirmDanger,
  t,
  entriesDrawerFocusReturnRef,
  quickAssignFocusReturnRef,
  importDialogFocusReturnRef,
}: UseDictionaryManagerDataFlowsParams) {
  const { openEntries, openDictionaryEntriesPanel, closeDictionaryEntriesPanel } =
    useDictionaryEntriesPanel({
      entriesDrawerFocusReturnRef,
    })

  const {
    data,
    status,
    error,
    refetch,
    filteredDictionaries,
    categoryFilterOptions,
    tagFilterOptions,
    activeEntriesDictionary,
    dictionariesById,
    duplicateDictionary,
  } = useDictionaryListData({
    isOnline,
    dictionarySearch,
    dictionaryCategoryFilter,
    dictionaryTagFilters,
    openEntries,
    notification,
    queryClient,
  })

  const dictionaries = Array.isArray(data) ? data : []
  const workflows = useDictionaryManagerWorkflows({
    isOnline,
    dictionaries,
    queryClient,
    notification,
    confirmDanger,
    t,
    quickAssignFocusReturnRef,
    importDialogFocusReturnRef,
  })

  return {
    openEntries,
    openDictionaryEntriesPanel,
    closeDictionaryEntriesPanel,
    data,
    status,
    error,
    refetch,
    filteredDictionaries,
    categoryFilterOptions,
    tagFilterOptions,
    activeEntriesDictionary,
    dictionariesById,
    duplicateDictionary,
    ...workflows,
  }
}
