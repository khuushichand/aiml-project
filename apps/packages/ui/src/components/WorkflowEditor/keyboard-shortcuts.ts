const EDITABLE_TARGET_SELECTOR =
  "input, textarea, select, [contenteditable='true'], [role='textbox'], [role='combobox']"

export const isEditableEventTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true

  const tag = target.tagName.toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true

  return Boolean(target.closest(EDITABLE_TARGET_SELECTOR))
}

