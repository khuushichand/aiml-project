import React from "react"
import { useDictionaryEntryTableColumns } from "./useDictionaryEntryTableColumns"

type InlineEditableEntryField = "pattern" | "replacement"

type InlineEditState = {
  entryId: number
  field: InlineEditableEntryField
  value: string
  initialValue: string
}

type UseDictionaryEntryListTableParams = {
  inlineEdit: InlineEditState | null
  setInlineEdit: React.Dispatch<React.SetStateAction<InlineEditState | null>>
  inlineEditError: string | null
  setInlineEditError: (value: string | null) => void
  inlineEditSaving: boolean
  cancelInlineEdit: () => void
  saveInlineEdit: () => Promise<void> | void
  startInlineEdit: (entry: any, field: InlineEditableEntryField) => void
  entryPriorityById: Map<number, number>
  reorderBusyEntryId: number | null
  canReorderEntries: boolean
  orderedEntryCount: number
  onMoveEntry: (entryId: number, direction: -1 | 1) => Promise<void> | void
  onOpenEditEntry: (entry: any) => void
  onDeleteEntry: (entry: any) => Promise<void> | void
}

type UseDictionaryEntryListTableResult = {
  entryTableColumns: any[]
}

export function useDictionaryEntryListTable({
  inlineEdit,
  setInlineEdit,
  inlineEditError,
  setInlineEditError,
  inlineEditSaving,
  cancelInlineEdit,
  saveInlineEdit,
  startInlineEdit,
  entryPriorityById,
  reorderBusyEntryId,
  canReorderEntries,
  orderedEntryCount,
  onMoveEntry,
  onOpenEditEntry,
  onDeleteEntry,
}: UseDictionaryEntryListTableParams): UseDictionaryEntryListTableResult {
  const [testingEntryId, setTestingEntryId] = React.useState<number | null>(null)
  const [inlineTestInput, setInlineTestInput] = React.useState("")
  const [inlineTestResult, setInlineTestResult] = React.useState<string | null>(null)

  const entryTableColumns = useDictionaryEntryTableColumns({
    inlineEdit,
    setInlineEdit,
    inlineEditError,
    setInlineEditError,
    inlineEditSaving,
    cancelInlineEdit,
    saveInlineEdit,
    startInlineEdit,
    entryPriorityById,
    reorderBusyEntryId,
    canReorderEntries,
    orderedEntryCount,
    onMoveEntry,
    testingEntryId,
    setTestingEntryId,
    inlineTestInput,
    setInlineTestInput,
    inlineTestResult,
    setInlineTestResult,
    onOpenEditEntry,
    onDeleteEntry,
  })

  return { entryTableColumns }
}
