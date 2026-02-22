import React from "react"

type UseDictionaryEntryManagerShortcutsParams = {
  editingEntry: any | null
  form: { submit: () => void }
  editEntryForm: { submit: () => void }
  runValidation: () => Promise<unknown> | unknown
  openValidationPanel: () => void
}

function shouldIgnoreGlobalShortcut(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  const element = target as HTMLElement
  if (element.isContentEditable) return true
  const tag = (element.tagName || "").toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true
  return Boolean(element.closest('input,textarea,select,[contenteditable="true"]'))
}

export function useDictionaryEntryManagerShortcuts({
  editingEntry,
  form,
  editEntryForm,
  runValidation,
  openValidationPanel,
}: UseDictionaryEntryManagerShortcutsParams): void {
  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return

      const hasModifier = event.ctrlKey || event.metaKey
      if (!hasModifier || event.altKey) return

      const lowered = event.key.toLowerCase()

      if (lowered === "v" && event.shiftKey) {
        if (shouldIgnoreGlobalShortcut(event.target)) return
        event.preventDefault()
        openValidationPanel()
        void runValidation()
        return
      }

      if (event.key !== "Enter" || event.shiftKey) return

      event.preventDefault()
      if (editingEntry) {
        editEntryForm.submit()
        return
      }
      form.submit()
    }

    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [editEntryForm, editingEntry, form, openValidationPanel, runValidation])
}
