import { useState, useCallback, useEffect } from "react"

export type LayoutMode = "simple" | "research" | "expert"

const STORAGE_KEY = "knowledge_qa_layout_mode"

function readPersistedMode(): LayoutMode | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === "simple" || stored === "research" || stored === "expert") {
      return stored
    }
  } catch {
    // localStorage unavailable (private mode, extension sandbox, etc.)
  }
  return null
}

function persistMode(mode: LayoutMode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // ignore
  }
}

type UseLayoutModeOptions = {
  messageCount: number
}

export function useLayoutMode({ messageCount }: UseLayoutModeOptions) {
  const [mode, setModeRaw] = useState<LayoutMode>(
    () => readPersistedMode() ?? "simple"
  )
  const [showPromotionToast, setShowPromotionToast] = useState(false)
  const [promotionDismissed, setPromotionDismissed] = useState(false)

  const setLayoutMode = useCallback((next: LayoutMode) => {
    setModeRaw(next)
    persistMode(next)
    setShowPromotionToast(false)
  }, [])

  // Auto-suggest promotion to research mode after 3+ Q+A pairs (6 messages)
  useEffect(() => {
    if (
      mode === "simple" &&
      !promotionDismissed &&
      messageCount >= 6
    ) {
      setShowPromotionToast(true)
    }
  }, [mode, messageCount, promotionDismissed])

  const dismissPromotion = useCallback(() => {
    setShowPromotionToast(false)
    setPromotionDismissed(true)
  }, [])

  const acceptPromotion = useCallback(() => {
    setLayoutMode("research")
    setPromotionDismissed(true)
  }, [setLayoutMode])

  const isSimple = mode === "simple"
  const isResearch = mode === "research" || mode === "expert"

  return {
    mode,
    setLayoutMode,
    isSimple,
    isResearch,
    showPromotionToast,
    dismissPromotion,
    acceptPromotion,
  }
}
