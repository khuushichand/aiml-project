export const getFocusableActiveElement = (): HTMLElement | null => {
  if (typeof document === "undefined") return null
  const active = document.activeElement
  return active instanceof HTMLElement ? active : null
}

export const restoreFocusToElement = (target: HTMLElement | null): void => {
  if (!target || typeof target.focus !== "function") return

  const applyFocus = () => {
    if (!target.isConnected) return
    target.focus()
  }

  if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(applyFocus)
  }

  setTimeout(applyFocus, 0)
}
