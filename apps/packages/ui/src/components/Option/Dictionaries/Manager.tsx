import React from "react"
import { DictionaryListSection } from "./components/DictionaryListSection"
import { DictionaryManagerOverlays } from "./components/DictionaryManagerOverlays"
import { useDictionariesManagerState } from "./components/useDictionariesManagerState"

export const DictionariesManager: React.FC = () => {
  const { listSectionProps, overlayProps } = useDictionariesManagerState()

  return (
    <div className="space-y-4">
      <DictionaryListSection {...listSectionProps} />
      <DictionaryManagerOverlays {...overlayProps} />
    </div>
  )
}
