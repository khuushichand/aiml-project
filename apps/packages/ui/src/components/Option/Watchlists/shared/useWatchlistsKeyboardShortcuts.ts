import { useCallback, useEffect } from "react"

interface KeyboardShortcutActions {
  onOpenCommandPalette: () => void
  onSwitchTab: (index: number) => void
  onNewEntity: () => void
  onRefresh: () => void
  onFocusSearch: () => void
  onShowHelp: () => void
}

const isInputFocused = (): boolean => {
  const el = document.activeElement
  if (!el) return false
  const tag = el.tagName.toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true
  if ((el as HTMLElement).isContentEditable) return true
  return false
}

export const useWatchlistsKeyboardShortcuts = (
  actions: KeyboardShortcutActions,
  enabled: boolean = true
): void => {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return

      const metaOrCtrl = event.metaKey || event.ctrlKey

      // Cmd/Ctrl+K — command palette (always active)
      if (metaOrCtrl && event.key === "k") {
        event.preventDefault()
        actions.onOpenCommandPalette()
        return
      }

      // Skip remaining shortcuts when typing in inputs
      if (isInputFocused()) return

      // 1/2/3 — switch primary tabs
      if (event.key >= "1" && event.key <= "3" && !metaOrCtrl && !event.altKey) {
        event.preventDefault()
        actions.onSwitchTab(Number(event.key) - 1)
        return
      }

      // N — new entity
      if (event.key === "n" && !metaOrCtrl && !event.altKey && !event.shiftKey) {
        event.preventDefault()
        actions.onNewEntity()
        return
      }

      // R — refresh
      if (event.key === "r" && !metaOrCtrl && !event.altKey && !event.shiftKey) {
        event.preventDefault()
        actions.onRefresh()
        return
      }

      // / — focus search
      if (event.key === "/" && !metaOrCtrl && !event.altKey) {
        event.preventDefault()
        actions.onFocusSearch()
        return
      }

      // ? — show help
      if (event.key === "?" || (event.shiftKey && event.key === "/")) {
        event.preventDefault()
        actions.onShowHelp()
        return
      }
    },
    [actions, enabled]
  )

  useEffect(() => {
    if (!enabled) return
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [handleKeyDown, enabled])
}
