import React from "react"
import { useDictionaryImportFlow } from "./useDictionaryImportFlow"
import { useDictionaryQuickAssign } from "./useDictionaryQuickAssign"
import { useRestoreFocusOnClose } from "./useRestoreFocusOnClose"

type UseDictionaryManagerWorkflowsParams = {
  isOnline: boolean
  dictionaries: any[]
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
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

export function useDictionaryManagerWorkflows({
  isOnline,
  dictionaries,
  queryClient,
  notification,
  confirmDanger,
  t,
  quickAssignFocusReturnRef,
  importDialogFocusReturnRef,
}: UseDictionaryManagerWorkflowsParams) {
  const quickAssignFlow = useDictionaryQuickAssign({
    isOnline,
    notification,
    queryClient,
  })
  const importFlow = useDictionaryImportFlow({
    dictionaries,
    queryClient,
    notification,
    confirmDanger,
    t,
  })

  useRestoreFocusOnClose(Boolean(quickAssignFlow.assignFor), quickAssignFocusReturnRef)
  useRestoreFocusOnClose(importFlow.openImport, importDialogFocusReturnRef)

  return {
    ...quickAssignFlow,
    ...importFlow,
  }
}
