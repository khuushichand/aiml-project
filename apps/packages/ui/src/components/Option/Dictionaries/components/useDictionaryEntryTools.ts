import { useMutation } from "@tanstack/react-query"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { buildTextDiffSegments } from "./dictionaryEntryUtils"

type UseDictionaryEntryToolsParams = {
  dictionaryId: number
  dictionaryMeta: any
  entries: any[]
  previewText: string
  t: (key: string, fallbackOrOptions?: any) => string
}

type DictionaryEntryToolsState = {
  validationStrict: boolean
  setValidationStrict: React.Dispatch<React.SetStateAction<boolean>>
  validationReport: any | null
  validationError: string | null
  runValidation: () => void
  validating: boolean
  previewTokenBudget: number | null
  setPreviewTokenBudget: React.Dispatch<React.SetStateAction<number | null>>
  previewMaxIterations: number | null
  setPreviewMaxIterations: React.Dispatch<React.SetStateAction<number | null>>
  previewResult: any | null
  previewError: string | null
  handlePreview: () => void
  previewing: boolean
  previewEntriesUsed: Array<string | number>
  previewProcessedText: string
  previewDiffSegments: ReturnType<typeof buildTextDiffSegments>
  previewHasDiffChanges: boolean
}

export function useDictionaryEntryTools({
  dictionaryId,
  dictionaryMeta,
  entries,
  previewText,
  t,
}: UseDictionaryEntryToolsParams): DictionaryEntryToolsState {
  const [validationStrict, setValidationStrict] = React.useState(false)
  const [validationReport, setValidationReport] = React.useState<any | null>(null)
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [previewTokenBudget, setPreviewTokenBudget] = React.useState<number | null>(1000)
  const [previewMaxIterations, setPreviewMaxIterations] = React.useState<number | null>(5)
  const [previewResult, setPreviewResult] = React.useState<any | null>(null)
  const [previewError, setPreviewError] = React.useState<string | null>(null)

  const { mutate: runValidation, isPending: validating } = useMutation({
    mutationFn: async () => {
      await tldwClient.initialize()
      const payload = {
        data: {
          name: dictionaryMeta?.name || undefined,
          description: dictionaryMeta?.description || undefined,
          entries: entries.map((entry: any) => ({
            pattern: entry.pattern,
            replacement: entry.replacement,
            type: entry.type,
            probability: entry.probability,
            enabled: entry.enabled,
            case_sensitive: entry.case_sensitive,
            group: entry.group,
            timed_effects: entry.timed_effects,
            max_replacements: entry.max_replacements,
          })),
        },
        schema_version: 1,
        strict: validationStrict,
      }
      return await tldwClient.validateDictionary(payload)
    },
    onSuccess: (response) => {
      setValidationReport(response)
      setValidationError(null)
    },
    onError: (error: any) => {
      setValidationReport(null)
      setValidationError(
        error?.message ||
          t("option:dictionariesTools.validateError", "Validation failed.")
      )
    },
  })

  const { mutate: runPreview, isPending: previewing } = useMutation({
    mutationFn: async () => {
      await tldwClient.initialize()
      const trimmed = previewText.trim()
      if (!trimmed) {
        throw new Error(
          t(
            "option:dictionariesTools.previewEmpty",
            "Enter sample text to preview."
          )
        )
      }
      const payload: {
        text: string
        token_budget?: number
        dictionary_id?: number | string
        max_iterations?: number
      } = {
        text: trimmed,
        dictionary_id: dictionaryId,
      }
      if (typeof previewTokenBudget === "number" && previewTokenBudget > 0) {
        payload.token_budget = previewTokenBudget
      }
      if (
        typeof previewMaxIterations === "number" &&
        previewMaxIterations > 0
      ) {
        payload.max_iterations = previewMaxIterations
      }
      return await tldwClient.processDictionary(payload)
    },
    onSuccess: (response) => {
      setPreviewResult(response)
      setPreviewError(null)
    },
    onError: (error: any) => {
      setPreviewResult(null)
      setPreviewError(
        error?.message ||
          t("option:dictionariesTools.previewError", "Preview failed.")
      )
    },
  })

  const handlePreview = React.useCallback(() => {
    if (!previewText.trim()) {
      setPreviewError(
        t(
          "option:dictionariesTools.previewEmpty",
          "Enter sample text to preview."
        )
      )
      return
    }
    runPreview()
  }, [previewText, runPreview, t])

  const previewEntriesUsed = Array.isArray(previewResult?.entries_used)
    ? previewResult.entries_used
    : []
  const previewOriginalText =
    typeof previewResult?.original_text === "string"
      ? previewResult.original_text
      : previewText
  const previewProcessedText =
    typeof previewResult?.processed_text === "string"
      ? previewResult.processed_text
      : ""
  const previewDiffSegments = React.useMemo(
    () => buildTextDiffSegments(previewOriginalText || "", previewProcessedText || ""),
    [previewOriginalText, previewProcessedText]
  )
  const previewHasDiffChanges = previewDiffSegments.some(
    (segment) => segment.type !== "unchanged"
  )

  return {
    validationStrict,
    setValidationStrict,
    validationReport,
    validationError,
    runValidation,
    validating,
    previewTokenBudget,
    setPreviewTokenBudget,
    previewMaxIterations,
    setPreviewMaxIterations,
    previewResult,
    previewError,
    handlePreview,
    previewing,
    previewEntriesUsed,
    previewProcessedText,
    previewDiffSegments,
    previewHasDiffChanges,
  }
}
