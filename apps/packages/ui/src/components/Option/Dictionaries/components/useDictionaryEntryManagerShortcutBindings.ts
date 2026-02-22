import React from "react"
import { useDictionaryEntryManagerShortcuts } from "./useDictionaryEntryManagerShortcuts"
import { useDictionaryEntryManagerActions } from "./useDictionaryEntryManagerActions"
import { useDictionaryEntryManagerContext } from "./useDictionaryEntryManagerContext"

type UseDictionaryEntryManagerShortcutBindingsParams = {
  form: any
  runValidation: () => void
  context: ReturnType<typeof useDictionaryEntryManagerContext>
  actions: ReturnType<typeof useDictionaryEntryManagerActions>
}

export function useDictionaryEntryManagerShortcutBindings({
  form,
  runValidation,
  context,
  actions,
}: UseDictionaryEntryManagerShortcutBindingsParams) {
  const openValidationPanel = React.useCallback(() => {
    context.setToolsPanelKeys((previous) =>
      previous.includes("validate") ? previous : [...previous, "validate"]
    )
  }, [context.setToolsPanelKeys])

  useDictionaryEntryManagerShortcuts({
    editingEntry: actions.editingEntry,
    form,
    editEntryForm: context.editEntryForm,
    runValidation,
    openValidationPanel,
  })
}
