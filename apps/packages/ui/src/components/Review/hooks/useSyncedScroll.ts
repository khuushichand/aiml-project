import React from "react"

/**
 * Synchronize scroll positions across 2-4 panels.
 * When one panel scrolls, all others are updated to the same scroll percentage.
 */
export function useSyncedScroll(enabled: boolean, bindingKey?: string) {
  const refsRef = React.useRef<(HTMLElement | null)[]>([])
  const scrollingRef = React.useRef(false)

  const setRef = React.useCallback(
    (index: number) => (el: HTMLElement | null) => {
      refsRef.current[index] = el
    },
    []
  )

  React.useEffect(() => {
    if (!enabled) return

    const els = refsRef.current.filter(Boolean) as HTMLElement[]
    if (els.length < 2) return

    const handler = (source: HTMLElement) => {
      if (scrollingRef.current) return
      scrollingRef.current = true

      const maxScroll = source.scrollHeight - source.clientHeight
      const ratio = maxScroll > 0 ? source.scrollTop / maxScroll : 0

      for (const el of els) {
        if (el === source) continue
        const elMax = el.scrollHeight - el.clientHeight
        el.scrollTop = ratio * elMax
      }

      requestAnimationFrame(() => {
        scrollingRef.current = false
      })
    }

    const listeners = els.map((el) => {
      const fn = () => handler(el)
      el.addEventListener("scroll", fn, { passive: true })
      return { el, fn }
    })

    return () => {
      for (const { el, fn } of listeners) {
        el.removeEventListener("scroll", fn)
      }
    }
  }, [enabled, bindingKey])

  return { setRef }
}
