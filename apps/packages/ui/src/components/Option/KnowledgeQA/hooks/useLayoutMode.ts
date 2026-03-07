import { useState, useCallback, useEffect } from "react"

export type LayoutMode = "simple" | "research" | "expert"

const STORAGE_KEY = "knowledge_qa_layout_mode"
const DISMISSED_KEY = "knowledge_qa_promotion_dismissed"

/** Suggest workspace view after this many messages (3 Q+A pairs) */
export const PROMOTION_MESSAGE_THRESHOLD = 6

function safeGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    // localStorage unavailable in private mode, extension sandbox, etc.
    return null
  }
}

function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // localStorage unavailable — preference won't persist this session
  }
}

function readPersistedMode(): LayoutMode | null {
  const stored = safeGetItem(STORAGE_KEY)
  if (stored === "simple" || stored === "research" || stored === "expert") {
    return stored
  }
  return null
}

type UseLayoutModeOptions = {
  messageCount: number
}

export function useLayoutMode({ messageCount }: UseLayoutModeOptions) {
  const [mode, setModeRaw] = useState<LayoutMode>(
    () => readPersistedMode() ?? "simple"
  )
  const [showPromotionToast, setShowPromotionToast] = useState(false)
  const [promotionDismissed, setPromotionDismissed] = useState(
    () => safeGetItem(DISMISSED_KEY) === "true"
  )

  const setLayoutMode = useCallback((next: LayoutMode) => {
    setModeRaw(next)
    safeSetItem(STORAGE_KEY, next)
    setShowPromotionToast(false)
  }, [])

  // Auto-suggest promotion to research mode after 3+ Q+A pairs
  useEffect(() => {
    if (
      mode === "simple" &&
      !promotionDismissed &&
      messageCount >= PROMOTION_MESSAGE_THRESHOLD
    ) {
      setShowPromotionToast(true)
    }
  }, [mode, messageCount, promotionDismissed])

  const dismissPromotion = useCallback(() => {
    setShowPromotionToast(false)
    setPromotionDismissed(true)
    safeSetItem(DISMISSED_KEY, "true")
  }, [])

  const acceptPromotion = useCallback(() => {
    setLayoutMode("research")
    setPromotionDismissed(true)
    safeSetItem(DISMISSED_KEY, "true")
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
