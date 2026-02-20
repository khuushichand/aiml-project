import React from "react"
import {
  resolveMobileComposerViewportState,
  type MobileComposerViewportState
} from "./mobile-composer-layout"

const DEFAULT_STATE: MobileComposerViewportState = {
  keyboardInsetPx: 0,
  keyboardOpen: false
}

export const useMobileComposerViewport = (
  enabled: boolean
): MobileComposerViewportState => {
  const [state, setState] =
    React.useState<MobileComposerViewportState>(DEFAULT_STATE)

  React.useEffect(() => {
    if (typeof window === "undefined") return
    if (!enabled) {
      setState((prev) =>
        prev.keyboardInsetPx === 0 && !prev.keyboardOpen
          ? prev
          : DEFAULT_STATE
      )
      return
    }

    const viewport = window.visualViewport
    if (!viewport) {
      setState((prev) =>
        prev.keyboardInsetPx === 0 && !prev.keyboardOpen
          ? prev
          : DEFAULT_STATE
      )
      return
    }

    let rafId = 0
    const measureViewport = () => {
      const next = resolveMobileComposerViewportState({
        layoutViewportHeight: window.innerHeight,
        visualViewportHeight: viewport.height,
        visualViewportOffsetTop: viewport.offsetTop
      })
      setState((prev) =>
        prev.keyboardInsetPx === next.keyboardInsetPx &&
        prev.keyboardOpen === next.keyboardOpen
          ? prev
          : next
      )
    }

    const scheduleMeasure = () => {
      if (rafId) {
        window.cancelAnimationFrame(rafId)
      }
      rafId = window.requestAnimationFrame(() => {
        rafId = 0
        measureViewport()
      })
    }

    scheduleMeasure()
    viewport.addEventListener("resize", scheduleMeasure)
    viewport.addEventListener("scroll", scheduleMeasure)
    window.addEventListener("orientationchange", scheduleMeasure)

    return () => {
      if (rafId) {
        window.cancelAnimationFrame(rafId)
      }
      viewport.removeEventListener("resize", scheduleMeasure)
      viewport.removeEventListener("scroll", scheduleMeasure)
      window.removeEventListener("orientationchange", scheduleMeasure)
    }
  }, [enabled])

  return state
}
