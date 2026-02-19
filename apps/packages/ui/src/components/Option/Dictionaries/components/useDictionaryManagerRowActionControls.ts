import React from "react"
import { useDictionaryRowActions } from "./useDictionaryRowActions"

type UseDictionaryManagerRowActionControlsParams = {
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  notification: {
    error: (config: { message: string; description?: string }) => void
    warning: (config: { message: string; description?: string }) => void
    success: (config: { message: string; description?: string }) => void
    info: (config: { message: string; description?: string }) => void
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
  setStatsFor: React.Dispatch<React.SetStateAction<any | null>>
  setVersionHistoryFor: React.Dispatch<React.SetStateAction<any | null>>
  statsDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  versionHistoryDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

export function useDictionaryManagerRowActionControls({
  queryClient,
  notification,
  confirmDanger,
  t,
  setStatsFor,
  setVersionHistoryFor,
  statsDialogFocusReturnRef,
  versionHistoryDialogFocusReturnRef,
}: UseDictionaryManagerRowActionControlsParams) {
  const {
    exportDictionaryAsJson,
    exportDictionaryAsMarkdown,
    openDictionaryStatsModal,
    openDictionaryVersionHistoryModal,
    confirmAndDeleteDictionary,
  } = useDictionaryRowActions({
    notification,
    confirmDanger,
    t,
    queryClient,
    setStatsFor,
    statsDialogFocusReturnRef,
    setVersionHistoryFor,
    versionHistoryDialogFocusReturnRef,
  })

  const handleDictionaryVersionHistoryReverted = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
  }, [queryClient])

  return {
    exportDictionaryAsJson,
    exportDictionaryAsMarkdown,
    openDictionaryStatsModal,
    openDictionaryVersionHistoryModal,
    confirmAndDeleteDictionary,
    handleDictionaryVersionHistoryReverted,
  }
}
