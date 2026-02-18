import React from "react"
import {
  FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING,
  type FlashcardsShortcutHintDensity
} from "@/services/settings/ui-settings"
import { getSetting, setSetting } from "@/services/settings/registry"

type HintDensityUpdater =
  | FlashcardsShortcutHintDensity
  | ((prev: FlashcardsShortcutHintDensity) => FlashcardsShortcutHintDensity)

/**
 * Flashcards-specific shortcut hint preference that avoids hydration races.
 * We hydrate once from settings storage and do not overwrite explicit user changes.
 */
export const useFlashcardsShortcutHintDensity = () => {
  const [hintDensity, setHintDensityState] =
    React.useState<FlashcardsShortcutHintDensity>("expanded")
  const userChangedRef = React.useRef(false)

  React.useEffect(() => {
    let active = true
    void getSetting(FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING).then((stored) => {
      if (!active || userChangedRef.current) return
      setHintDensityState(stored)
    })
    return () => {
      active = false
    }
  }, [])

  const setHintDensity = React.useCallback((next: HintDensityUpdater) => {
    setHintDensityState((prev) => {
      userChangedRef.current = true
      const resolved = typeof next === "function" ? next(prev) : next
      void setSetting(FLASHCARDS_SHORTCUT_HINT_DENSITY_SETTING, resolved)
      return resolved
    })
  }, [])

  return [hintDensity, setHintDensity] as const
}

export default useFlashcardsShortcutHintDensity
