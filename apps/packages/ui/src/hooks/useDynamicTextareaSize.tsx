import { useEffect, useRef } from "react"

type TextareaStyleLike = {
  height: string
  maxHeight: string
  overflowY: string
}

export type DynamicTextareaLike = {
  scrollHeight: number
  style: TextareaStyleLike
}

export type DynamicTextareaApplyResult = {
  heightPx: number
  changed: boolean
}

/**
 * Applies textarea height/max-height styles while avoiding redundant writes.
 */
export const applyDynamicTextareaSize = (
  textarea: DynamicTextareaLike,
  maxHeight?: number,
  lastAppliedHeightPx?: number | null
): DynamicTextareaApplyResult => {
  const contentHeight = Math.max(0, Math.ceil(textarea.scrollHeight || 0))
  const hasMax = typeof maxHeight === "number" && Number.isFinite(maxHeight)
  const clampedMax = hasMax ? Math.max(0, Math.ceil(maxHeight as number)) : null
  const nextHeight = clampedMax != null ? Math.min(contentHeight, clampedMax) : contentHeight
  const nextOverflowY =
    clampedMax != null && contentHeight > clampedMax ? "scroll" : "hidden"

  if (clampedMax != null) {
    const nextMaxHeight = `${clampedMax}px`
    if (textarea.style.maxHeight !== nextMaxHeight) {
      textarea.style.maxHeight = nextMaxHeight
    }
  } else if (textarea.style.maxHeight !== "") {
    textarea.style.maxHeight = ""
  }

  if (textarea.style.overflowY !== nextOverflowY) {
    textarea.style.overflowY = nextOverflowY
  }

  const changed = lastAppliedHeightPx == null || lastAppliedHeightPx !== nextHeight
  if (changed) {
    textarea.style.height = `${nextHeight}px`
  }

  return { heightPx: nextHeight, changed }
}

/**
 * Custom hook for dynamically resizing a textarea to fit content.
 * Batches style writes in rAF and skips redundant height updates.
 */
const useDynamicTextareaSize = (
  textareaRef: React.RefObject<HTMLTextAreaElement>,
  textContent: string,
  maxHeight?: number
): void => {
  const rafRef = useRef<number | null>(null)
  const lastAppliedHeightRef = useRef<number | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return
    const textarea = textareaRef.current
    if (!textarea) return

    if (rafRef.current != null) {
      window.cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }

    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      const result = applyDynamicTextareaSize(
        textarea,
        maxHeight,
        lastAppliedHeightRef.current
      )
      lastAppliedHeightRef.current = result.heightPx
    })

    return () => {
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [textareaRef, textContent, maxHeight])
}

export default useDynamicTextareaSize

