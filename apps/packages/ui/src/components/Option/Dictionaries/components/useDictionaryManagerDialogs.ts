import React from "react"
import { getActiveFocusableElement } from "./focusUtils"

type UseDictionaryManagerDialogsParams = {
  createDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  editDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  openQuickAssignModalInternal: (dictionary: any) => void
  closeQuickAssignModalInternal: () => void
  openCreateModal: () => void
  openImportModal: () => void
  openEditModal: (record: any) => void
  closeEditModal: () => void
}

type UseDictionaryManagerDialogsResult = {
  openQuickAssignModal: (dictionary: any) => void
  closeQuickAssignModal: () => void
  openCreateDictionaryModal: () => void
  openImportDictionaryModal: () => void
  openDictionaryEditModal: (record: any) => void
  closeDictionaryEditModal: () => void
}

export function useDictionaryManagerDialogs({
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
}: UseDictionaryManagerDialogsParams): UseDictionaryManagerDialogsResult {
  const openQuickAssignModal = React.useCallback(
    (dictionary: any) => {
      quickAssignFocusReturnRef.current = getActiveFocusableElement()
      openQuickAssignModalInternal(dictionary)
    },
    [openQuickAssignModalInternal, quickAssignFocusReturnRef]
  )

  const closeQuickAssignModal = React.useCallback(() => {
    closeQuickAssignModalInternal()
  }, [closeQuickAssignModalInternal])

  const openCreateDictionaryModal = React.useCallback(() => {
    createDialogFocusReturnRef.current = getActiveFocusableElement()
    openCreateModal()
  }, [createDialogFocusReturnRef, openCreateModal])

  const openImportDictionaryModal = React.useCallback(() => {
    importDialogFocusReturnRef.current = getActiveFocusableElement()
    openImportModal()
  }, [importDialogFocusReturnRef, openImportModal])

  const openDictionaryEditModal = React.useCallback(
    (record: any) => {
      editDialogFocusReturnRef.current = getActiveFocusableElement()
      openEditModal(record)
    },
    [editDialogFocusReturnRef, openEditModal]
  )

  const closeDictionaryEditModal = React.useCallback(() => {
    closeEditModal()
  }, [closeEditModal])

  return {
    openQuickAssignModal,
    closeQuickAssignModal,
    openCreateDictionaryModal,
    openImportDictionaryModal,
    openDictionaryEditModal,
    closeDictionaryEditModal,
  }
}
