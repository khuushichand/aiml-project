export type PlaygroundShortcutAction =
  | "toggle_artifacts"
  | "toggle_compare"
  | "toggle_modes"

type ShortcutEvent = {
  altKey?: boolean
  shiftKey?: boolean
  ctrlKey?: boolean
  metaKey?: boolean
  repeat?: boolean
  key?: string
  target?: EventTarget | null
}

const isEditableTarget = (target: EventTarget | null | undefined): boolean => {
  if (!target || !(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tagName = target.tagName.toLowerCase()
  return tagName === "input" || tagName === "textarea" || tagName === "select"
}

export const resolvePlaygroundShortcutAction = (
  event: ShortcutEvent
): PlaygroundShortcutAction | null => {
  if (event.repeat) return null
  if (!event.altKey || !event.shiftKey) return null
  if (event.ctrlKey || event.metaKey) return null
  if (isEditableTarget(event.target)) return null

  const key = String(event.key || "").toLowerCase()
  if (key === "a") return "toggle_artifacts"
  if (key === "c") return "toggle_compare"
  if (key === "m") return "toggle_modes"
  return null
}
