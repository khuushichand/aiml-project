import React from "react"

type UseDictionaryManagerShortcutsParams = {
  openCreate: boolean
  openEdit: boolean
  openCreateDictionaryModal: () => void
  createForm: { submit: () => void }
  editForm: { submit: () => void }
}

function shouldIgnoreGlobalShortcut(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  const element = target as HTMLElement
  if (element.isContentEditable) return true
  const tag = (element.tagName || "").toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true
  return Boolean(element.closest('input,textarea,select,[contenteditable="true"]'))
}

export function useDictionaryManagerShortcuts({
  openCreate,
  openEdit,
  openCreateDictionaryModal,
  createForm,
  editForm,
}: UseDictionaryManagerShortcutsParams): void {
  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return

      const hasModifier = event.ctrlKey || event.metaKey
      if (!hasModifier || event.altKey) return

      const lowered = event.key.toLowerCase()

      if (lowered === "n" && !event.shiftKey) {
        if (shouldIgnoreGlobalShortcut(event.target)) return
        if (openCreate || openEdit) return
        event.preventDefault()
        openCreateDictionaryModal()
        return
      }

      if (event.key !== "Enter" || event.shiftKey) return

      if (openEdit) {
        event.preventDefault()
        editForm.submit()
        return
      }

      if (openCreate) {
        event.preventDefault()
        createForm.submit()
      }
    }

    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [
    createForm,
    editForm,
    openCreate,
    openCreateDictionaryModal,
    openEdit,
  ])
}
