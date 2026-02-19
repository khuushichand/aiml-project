import React from "react"
import { useDictionaryFormManagement } from "./useDictionaryFormManagement"
import { useDictionaryDeactivationConfirmation } from "./useDictionaryDeactivationConfirmation"
import { useDictionaryManagerDialogs } from "./useDictionaryManagerDialogs"

type UseDictionaryManagerFormDialogsParams = {
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
  dictionariesById: Record<number, any>
  createDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  editDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  openQuickAssignModalInternal: (record: any) => void
  closeQuickAssignModalInternal: () => void
  openImportModal: () => void
}

export function useDictionaryManagerFormDialogs({
  queryClient,
  notification,
  confirmDanger,
  t,
  dictionariesById,
  createDialogFocusReturnRef,
  editDialogFocusReturnRef,
  importDialogFocusReturnRef,
  quickAssignFocusReturnRef,
  openQuickAssignModalInternal,
  closeQuickAssignModalInternal,
  openImportModal,
}: UseDictionaryManagerFormDialogsParams) {
  const { confirmDeactivationIfNeeded } = useDictionaryDeactivationConfirmation({
    confirmDanger,
    t,
  })

  const {
    openCreate,
    openEdit,
    createForm,
    editForm,
    creating,
    updating,
    openCreateModal,
    closeCreateModal,
    openEditModal,
    closeEditModal,
    handleCreateSubmit,
    handleEditSubmit,
  } = useDictionaryFormManagement({
    queryClient,
    notification,
    confirmDanger,
    t,
    dictionariesById,
    confirmDeactivationIfNeeded,
  })

  const {
    openQuickAssignModal,
    closeQuickAssignModal,
    openCreateDictionaryModal,
    openImportDictionaryModal,
    openDictionaryEditModal,
    closeDictionaryEditModal,
  } = useDictionaryManagerDialogs({
    createDialogFocusReturnRef,
    editDialogFocusReturnRef,
    importDialogFocusReturnRef,
    quickAssignFocusReturnRef,
    openQuickAssignModalInternal,
    closeQuickAssignModalInternal,
    openCreateModal,
    openImportModal,
    openEditModal,
    closeEditModal,
  })

  return {
    confirmDeactivationIfNeeded,
    openCreate,
    openEdit,
    createForm,
    editForm,
    creating,
    updating,
    closeCreateModal,
    handleCreateSubmit,
    handleEditSubmit,
    openQuickAssignModal,
    closeQuickAssignModal,
    openCreateDictionaryModal,
    openImportDictionaryModal,
    openDictionaryEditModal,
    closeDictionaryEditModal,
  }
}
