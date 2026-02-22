import { useCallback, useState } from "react"
import {
  useKeyboardShortcuts,
  type KeyboardShortcutConfig
} from "@/hooks/keyboard/useKeyboardShortcuts"

interface KanbanShortcutActions {
  onNewCard?: () => void
  onNewBoard?: () => void
  onNewList?: () => void
  onClosePanel?: () => void
}

function isInputFocused(): boolean {
  const active = document.activeElement
  if (!active) return false
  const tag = active.tagName.toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true
  if ((active as HTMLElement).isContentEditable) return true
  return false
}

export const useKanbanShortcuts = (actions: KanbanShortcutActions) => {
  const [helpOpen, setHelpOpen] = useState(false)

  const guard = useCallback(
    (fn?: () => void) => () => {
      if (isInputFocused()) return
      fn?.()
    },
    []
  )

  const shortcuts: KeyboardShortcutConfig[] = [
    {
      shortcut: { key: "n", preventDefault: false, stopPropagation: false },
      action: guard(actions.onNewCard),
      description: "New card in active list"
    },
    {
      shortcut: { key: "b", preventDefault: false, stopPropagation: false },
      action: guard(actions.onNewBoard),
      description: "New board"
    },
    {
      shortcut: { key: "l", preventDefault: false, stopPropagation: false },
      action: guard(actions.onNewList),
      description: "New list"
    },
    {
      shortcut: { key: "Escape", preventDefault: false, stopPropagation: false },
      action: guard(actions.onClosePanel),
      description: "Close panel"
    },
    {
      shortcut: { key: "?", shiftKey: true, preventDefault: false, stopPropagation: false },
      action: guard(() => setHelpOpen(true)),
      description: "Show keyboard shortcuts"
    }
  ]

  useKeyboardShortcuts(shortcuts)

  return { helpOpen, setHelpOpen, shortcuts }
}
