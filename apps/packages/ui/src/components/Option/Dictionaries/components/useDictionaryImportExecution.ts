import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildImportConflictRenameSuggestion,
  isDictionaryImportConflictError,
} from "../importValidationUtils"
import {
  buildRenamedImportPreview,
  DictionaryImportConflictResolution,
  DictionaryImportPreview,
} from "./dictionaryImportPreviewUtils"
import { useDictionaryImportMutation } from "./useDictionaryImportMutation"

type UseDictionaryImportExecutionParams = {
  dictionaries: any[] | undefined
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  notification: {
    error: (config: { message: string; description?: string }) => void
  }
  confirmDanger: (config: {
    title: string
    content: string
    okText: string
    cancelText: string
  }) => Promise<boolean>
  t: (key: string, fallbackOrOptions?: any) => string
  activateOnImport: boolean
  importPreview: DictionaryImportPreview | null
  onImportSuccess: () => void
}

type UseDictionaryImportExecutionResult = {
  importing: boolean
  importConflictResolution: DictionaryImportConflictResolution
  clearImportConflictResolution: () => void
  handleConfirmImport: () => Promise<void>
  resolveImportConflictRename: () => Promise<void>
  resolveImportConflictReplace: () => Promise<void>
}

export function useDictionaryImportExecution({
  dictionaries,
  queryClient,
  notification,
  confirmDanger,
  t,
  activateOnImport,
  importPreview,
  onImportSuccess,
}: UseDictionaryImportExecutionParams): UseDictionaryImportExecutionResult {
  const [importConflictResolution, setImportConflictResolution] =
    React.useState<DictionaryImportConflictResolution>(null)

  const handleImportMutationSuccess = React.useCallback(() => {
    setImportConflictResolution(null)
    onImportSuccess()
  }, [onImportSuccess])

  const { importing, runImportWithPreview } = useDictionaryImportMutation({
    queryClient,
    notification,
    activateOnImport,
    onImportSuccess: handleImportMutationSuccess,
  })

  const handleConfirmImport = React.useCallback(async () => {
    if (!importPreview) return
    try {
      await runImportWithPreview(importPreview)
    } catch (error: any) {
      if (!isDictionaryImportConflictError(error)) {
        return
      }
      const existingNames = (Array.isArray(dictionaries) ? dictionaries : []).map(
        (dictionary: any) => dictionary?.name
      )
      const suggestedName = buildImportConflictRenameSuggestion(
        importPreview.summary.name,
        existingNames
      )
      setImportConflictResolution({
        preview: importPreview,
        suggestedName,
      })
    }
  }, [dictionaries, importPreview, runImportWithPreview])

  const clearImportConflictResolution = React.useCallback(() => {
    setImportConflictResolution(null)
  }, [])

  const resolveImportConflictRename = React.useCallback(async () => {
    if (!importConflictResolution) return
    const renamedPreview = buildRenamedImportPreview(
      importConflictResolution.preview,
      importConflictResolution.suggestedName
    )

    try {
      await runImportWithPreview(renamedPreview)
    } catch {
      // handled by mutation onError
      return
    }
    setImportConflictResolution(null)
  }, [importConflictResolution, runImportWithPreview])

  const resolveImportConflictReplace = React.useCallback(async () => {
    if (!importConflictResolution) return
    const targetName = importConflictResolution.preview.summary.name
    const targetDictionary = (Array.isArray(dictionaries) ? dictionaries : []).find(
      (dictionary: any) =>
        String(dictionary?.name || "").trim().toLowerCase() ===
        targetName.trim().toLowerCase()
    )

    if (!targetDictionary?.id) {
      notification.error({
        message: "Replace unavailable",
        description: "Could not find the conflicting dictionary to replace.",
      })
      return
    }

    const confirmed = await confirmDanger({
      title: "Replace existing dictionary?",
      content: `Delete "${targetName}" and import the new version?`,
      okText: "Replace existing",
      cancelText: t("common:cancel", { defaultValue: "Cancel" }),
    })
    if (!confirmed) return

    try {
      await tldwClient.deleteDictionary(Number(targetDictionary.id))
      await runImportWithPreview(importConflictResolution.preview)
      setImportConflictResolution(null)
      await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
    } catch (error: any) {
      notification.error({
        message: "Replace failed",
        description: error?.message || "Unable to replace existing dictionary.",
      })
    }
  }, [
    confirmDanger,
    dictionaries,
    importConflictResolution,
    notification,
    queryClient,
    runImportWithPreview,
    t,
  ])

  return {
    importing,
    importConflictResolution,
    clearImportConflictResolution,
    handleConfirmImport,
    resolveImportConflictRename,
    resolveImportConflictReplace,
  }
}
