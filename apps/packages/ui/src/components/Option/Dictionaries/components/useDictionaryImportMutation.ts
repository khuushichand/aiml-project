import { useMutation } from "@tanstack/react-query"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildDictionaryImportErrorDescription,
  isDictionaryImportConflictError,
} from "../importValidationUtils"
import {
  DictionaryImportFormat,
  DictionaryImportPreview,
} from "./dictionaryImportPreviewUtils"

type UseDictionaryImportMutationParams = {
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
  notification: {
    error: (config: { message: string; description?: string }) => void
  }
  activateOnImport: boolean
  onImportSuccess: () => void
}

type UseDictionaryImportMutationResult = {
  importing: boolean
  runImportWithPreview: (preview: DictionaryImportPreview) => Promise<unknown>
}

export function useDictionaryImportMutation({
  queryClient,
  notification,
  activateOnImport,
  onImportSuccess,
}: UseDictionaryImportMutationParams): UseDictionaryImportMutationResult {
  const { mutateAsync: importDict, isPending: importing } = useMutation({
    mutationFn: async (payload: {
      format: DictionaryImportFormat
      activate: boolean
      data?: any
      name?: string
      content?: string
    }) => {
      if (payload.format === "json") {
        return await tldwClient.importDictionaryJSON(payload.data, payload.activate)
      }
      return await tldwClient.importDictionaryMarkdown(
        payload.name || "Imported Dictionary",
        payload.content || "",
        payload.activate
      )
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
      onImportSuccess()
    },
    onError: (error: any) => {
      if (isDictionaryImportConflictError(error)) return
      notification.error({
        message: "Import failed",
        description: buildDictionaryImportErrorDescription(error),
      })
    },
  })

  const runImportWithPreview = React.useCallback(
    async (preview: DictionaryImportPreview) => {
      if (preview.payload.kind === "json") {
        return await importDict({
          format: "json",
          data: preview.payload.data,
          activate: activateOnImport,
        })
      }
      return await importDict({
        format: "markdown",
        name: preview.payload.name,
        content: preview.payload.content,
        activate: activateOnImport,
      })
    },
    [activateOnImport, importDict]
  )

  return {
    importing,
    runImportWithPreview,
  }
}
