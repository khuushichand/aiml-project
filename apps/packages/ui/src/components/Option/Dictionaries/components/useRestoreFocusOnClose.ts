import React from "react"
import { restoreFocusToElement } from "./focusUtils"

export function useRestoreFocusOnClose(
  isOpen: boolean,
  focusReturnRef: React.MutableRefObject<HTMLElement | null>
): void {
  React.useEffect(() => {
    if (isOpen) return
    const focusTarget = focusReturnRef.current
    focusReturnRef.current = null
    restoreFocusToElement(focusTarget)
  }, [focusReturnRef, isOpen])
}
