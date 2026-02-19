import React from "react"
import { getActiveFocusableElement } from "./focusUtils"

type UseDictionaryEntriesPanelParams = {
  entriesDrawerFocusReturnRef: React.MutableRefObject<HTMLElement | null>
}

type UseDictionaryEntriesPanelResult = {
  openEntries: number | null
  openDictionaryEntriesPanel: (dictionaryId: number) => void
  closeDictionaryEntriesPanel: () => void
}

export function useDictionaryEntriesPanel({
  entriesDrawerFocusReturnRef,
}: UseDictionaryEntriesPanelParams): UseDictionaryEntriesPanelResult {
  const [openEntries, setOpenEntries] = React.useState<number | null>(null)

  const openDictionaryEntriesPanel = React.useCallback(
    (dictionaryId: number) => {
      entriesDrawerFocusReturnRef.current = getActiveFocusableElement()
      setOpenEntries(dictionaryId)
    },
    [entriesDrawerFocusReturnRef]
  )

  const closeDictionaryEntriesPanel = React.useCallback(() => {
    setOpenEntries(null)
  }, [])

  return {
    openEntries,
    openDictionaryEntriesPanel,
    closeDictionaryEntriesPanel,
  }
}
