import React from "react"
import { useRestoreFocusOnClose } from "./useRestoreFocusOnClose"

type UseDictionaryManagerFocusRestorationParams = {
  openEntries: number | null
  statsFor: any | null
  versionHistoryFor: any | null
  assignFor: any | null
  openImport: boolean
  openCreate: boolean
  openEdit: boolean
  createDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  editDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  entriesDrawerFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  statsDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  versionHistoryDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

export function useDictionaryManagerFocusRestoration({
  openEntries,
  statsFor,
  versionHistoryFor,
  assignFor,
  openImport,
  openCreate,
  openEdit,
  createDialogFocusReturnRef,
  editDialogFocusReturnRef,
  entriesDrawerFocusReturnRef,
  importDialogFocusReturnRef,
  quickAssignFocusReturnRef,
  statsDialogFocusReturnRef,
  versionHistoryDialogFocusReturnRef,
}: UseDictionaryManagerFocusRestorationParams): void {
  useRestoreFocusOnClose(openEntries != null, entriesDrawerFocusReturnRef)
  useRestoreFocusOnClose(Boolean(statsFor), statsDialogFocusReturnRef)
  useRestoreFocusOnClose(Boolean(versionHistoryFor), versionHistoryDialogFocusReturnRef)
  useRestoreFocusOnClose(Boolean(assignFor), quickAssignFocusReturnRef)
  useRestoreFocusOnClose(openImport, importDialogFocusReturnRef)
  useRestoreFocusOnClose(openCreate, createDialogFocusReturnRef)
  useRestoreFocusOnClose(openEdit, editDialogFocusReturnRef)
}
