import React from "react"

type DictionaryManagerFocusRefs = {
  createDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  editDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  entriesDrawerFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  importDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  quickAssignFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  statsDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
  versionHistoryDialogFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

export function useDictionaryManagerFocusRefs(): DictionaryManagerFocusRefs {
  const createDialogFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const editDialogFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const entriesDrawerFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const importDialogFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const quickAssignFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const statsDialogFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const versionHistoryDialogFocusReturnRef = React.useRef<HTMLElement | null>(null)

  return {
    createDialogFocusReturnRef,
    editDialogFocusReturnRef,
    entriesDrawerFocusReturnRef,
    importDialogFocusReturnRef,
    quickAssignFocusReturnRef,
    statsDialogFocusReturnRef,
    versionHistoryDialogFocusReturnRef,
  }
}
