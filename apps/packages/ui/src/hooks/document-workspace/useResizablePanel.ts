import { useState, useCallback, useEffect, useRef } from "react"

interface UseResizablePanelOptions {
  key: string
  defaultWidth: number
  min: number
  max: number
}

interface UseResizablePanelReturn {
  width: number
  handleMouseDown: (e: React.MouseEvent) => void
}

export function useResizablePanel({
  key,
  defaultWidth,
  min,
  max
}: UseResizablePanelOptions): UseResizablePanelReturn {
  const storageKey = `document-workspace-panel-${key}`

  const [width, setWidth] = useState(() => {
    if (typeof window === "undefined") return defaultWidth
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const parsed = parseInt(saved, 10)
        if (!isNaN(parsed)) return Math.max(min, Math.min(max, parsed))
      }
    } catch { /* ignore */ }
    return defaultWidth
  })

  const draggingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = true
    startXRef.current = e.clientX
    startWidthRef.current = width
  }, [width])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current) return
      const delta = e.clientX - startXRef.current
      const newWidth = Math.max(min, Math.min(max, startWidthRef.current + delta))
      setWidth(newWidth)
    }
    const handleMouseUp = () => {
      draggingRef.current = false
    }
    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", handleMouseUp)
    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [min, max])

  // Persist to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, String(width))
    } catch { /* ignore */ }
  }, [storageKey, width])

  return { width, handleMouseDown }
}
