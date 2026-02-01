import { useState, useEffect, useCallback, useRef } from "react"

export interface TextSelection {
  text: string
  rect: DOMRect
}

/**
 * Hook for detecting text selection within a container element.
 *
 * @param containerRef - Ref to the container element to monitor for selections
 * @returns Selection state and clear function
 */
export function useTextSelection(containerRef: React.RefObject<HTMLElement | null>) {
  const [selection, setSelection] = useState<TextSelection | null>(null)
  const selectionTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const clearSelection = useCallback(() => {
    setSelection(null)
  }, [])

  useEffect(() => {
    const handleMouseUp = () => {
      // Clear any pending timeout
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current)
      }

      // Small delay to ensure selection is complete
      selectionTimeoutRef.current = setTimeout(() => {
        const sel = window.getSelection()

        if (!sel || sel.isCollapsed) {
          setSelection(null)
          return
        }

        // Only handle selection within the PDF container
        const container = containerRef.current
        if (!container) {
          setSelection(null)
          return
        }

        // Check if selection anchor is within container
        const anchorNode = sel.anchorNode
        if (!anchorNode || !container.contains(anchorNode)) {
          setSelection(null)
          return
        }

        const text = sel.toString().trim()
        if (text.length === 0) {
          setSelection(null)
          return
        }

        // Get bounding rect of selection
        const range = sel.getRangeAt(0)
        const rect = range.getBoundingClientRect()

        setSelection({ text, rect })
      }, 10)
    }

    const handleMouseDown = (e: MouseEvent) => {
      // Clear selection when clicking elsewhere
      const target = e.target as HTMLElement
      const popover = document.querySelector("[data-selection-popover]")

      if (popover && popover.contains(target)) {
        // Clicking inside popover - don't clear
        return
      }

      setSelection(null)
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      // Clear selection on Escape
      if (e.key === "Escape") {
        setSelection(null)
        window.getSelection()?.removeAllRanges()
      }
    }

    document.addEventListener("mouseup", handleMouseUp)
    document.addEventListener("mousedown", handleMouseDown)
    document.addEventListener("keydown", handleKeyDown)

    return () => {
      if (selectionTimeoutRef.current) {
        clearTimeout(selectionTimeoutRef.current)
      }
      document.removeEventListener("mouseup", handleMouseUp)
      document.removeEventListener("mousedown", handleMouseDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [containerRef])

  return { selection, clearSelection }
}
