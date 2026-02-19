import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  type InlineEditableEntryField,
  validateRegexPattern,
} from "./dictionaryEntryUtils"

type InlineEditState = {
  entryId: number
  field: InlineEditableEntryField
  value: string
  initialValue: string
}

type UseDictionaryInlineEditParams = {
  dictionaryId: number
  allEntriesById: Map<number, any>
  allEntriesQueryKey: readonly [string, number]
  notification: {
    success: (config: { message: string; description?: string }) => void
  }
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  validateRegexWithServer: (entryDraft: any) => Promise<string | null>
}

type UseDictionaryInlineEditResult = {
  inlineEdit: InlineEditState | null
  setInlineEdit: React.Dispatch<React.SetStateAction<InlineEditState | null>>
  inlineEditError: string | null
  setInlineEditError: React.Dispatch<React.SetStateAction<string | null>>
  inlineEditSaving: boolean
  startInlineEdit: (entry: any, field: InlineEditableEntryField) => void
  cancelInlineEdit: () => void
  saveInlineEdit: () => Promise<void>
}

export function useDictionaryInlineEdit({
  dictionaryId,
  allEntriesById,
  allEntriesQueryKey,
  notification,
  queryClient,
  validateRegexWithServer,
}: UseDictionaryInlineEditParams): UseDictionaryInlineEditResult {
  const [inlineEdit, setInlineEdit] = React.useState<InlineEditState | null>(null)
  const [inlineEditError, setInlineEditError] = React.useState<string | null>(null)
  const [inlineEditSaving, setInlineEditSaving] = React.useState(false)

  const startInlineEdit = React.useCallback(
    (entry: any, field: InlineEditableEntryField) => {
      if (inlineEditSaving) return
      const entryId = Number(entry?.id)
      if (!Number.isFinite(entryId) || entryId <= 0) return
      const rawValue = entry?.[field]
      const currentValue = typeof rawValue === "string" ? rawValue : ""
      setInlineEdit({
        entryId,
        field,
        value: currentValue,
        initialValue: currentValue,
      })
      setInlineEditError(null)
    },
    [inlineEditSaving]
  )

  const cancelInlineEdit = React.useCallback(() => {
    if (inlineEditSaving) return
    setInlineEdit(null)
    setInlineEditError(null)
  }, [inlineEditSaving])

  const saveInlineEdit = React.useCallback(async () => {
    if (!inlineEdit || inlineEditSaving) return

    const nextValue = inlineEdit.value
    const trimmedValue = nextValue.trim()
    const fieldLabel = inlineEdit.field === "pattern" ? "Pattern" : "Replacement"

    if (!trimmedValue) {
      setInlineEditError(`${fieldLabel} is required.`)
      return
    }

    if (nextValue === inlineEdit.initialValue) {
      setInlineEdit(null)
      setInlineEditError(null)
      return
    }

    const currentEntry = allEntriesById.get(inlineEdit.entryId)
    if (!currentEntry) {
      setInlineEditError("Entry no longer exists. Refresh and retry.")
      return
    }

    if (inlineEdit.field === "pattern" && currentEntry?.type === "regex") {
      const clientRegexError = validateRegexPattern(nextValue)
      if (clientRegexError) {
        setInlineEditError(clientRegexError)
        return
      }
      const serverRegexError = await validateRegexWithServer({
        ...currentEntry,
        pattern: nextValue,
      })
      if (serverRegexError) {
        setInlineEditError(serverRegexError)
        return
      }
    }

    setInlineEditSaving(true)
    try {
      await tldwClient.updateDictionaryEntry(inlineEdit.entryId, {
        [inlineEdit.field]: nextValue,
      })
      await queryClient.invalidateQueries({
        queryKey: ["tldw:listDictionaryEntries", dictionaryId],
      })
      await queryClient.invalidateQueries({ queryKey: allEntriesQueryKey })
      setInlineEdit(null)
      setInlineEditError(null)
      notification.success({ message: `${fieldLabel} updated` })
    } catch (error: any) {
      setInlineEditError(error?.message || "Unable to save inline edit.")
    } finally {
      setInlineEditSaving(false)
    }
  }, [
    allEntriesById,
    allEntriesQueryKey,
    dictionaryId,
    inlineEdit,
    inlineEditSaving,
    notification,
    queryClient,
    validateRegexWithServer,
  ])

  return {
    inlineEdit,
    setInlineEdit,
    inlineEditError,
    setInlineEditError,
    inlineEditSaving,
    startInlineEdit,
    cancelInlineEdit,
    saveInlineEdit,
  }
}
