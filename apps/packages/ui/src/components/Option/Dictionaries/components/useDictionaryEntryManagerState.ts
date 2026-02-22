import { useDictionaryEntryTools } from "./useDictionaryEntryTools"
import { useDictionaryEntryManagerContext } from "./useDictionaryEntryManagerContext"
import { useDictionaryEntryManagerActions } from "./useDictionaryEntryManagerActions"
import { useDictionaryEntryManagerShortcutBindings } from "./useDictionaryEntryManagerShortcutBindings"
import { useDictionaryEntryManagerPublicState } from "./useDictionaryEntryManagerPublicState"

type UseDictionaryEntryManagerStateParams = {
  dictionaryId: number
  form: any
}

export function useDictionaryEntryManagerState({
  dictionaryId,
  form,
}: UseDictionaryEntryManagerStateParams) {
  const context = useDictionaryEntryManagerContext({ dictionaryId })

  const {
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
  } = useDictionaryEntryTools({
    dictionaryId,
    dictionaryMeta: context.dictionaryMeta,
    entries: context.entries,
    previewText: context.previewText,
    t: context.t,
  })

  const actions = useDictionaryEntryManagerActions({
    dictionaryId,
    form,
    context,
  })

  useDictionaryEntryManagerShortcutBindings({
    form,
    runValidation,
    context,
    actions,
  })

  return useDictionaryEntryManagerPublicState({
    context,
    tools: {
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
    },
    actions,
  })
}
