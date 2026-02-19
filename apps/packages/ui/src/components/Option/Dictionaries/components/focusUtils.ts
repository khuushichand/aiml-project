export function getActiveFocusableElement(): HTMLElement | null {
  if (typeof document === "undefined") return null
  const activeElement = document.activeElement
  return activeElement instanceof HTMLElement ? activeElement : null
}

export function restoreFocusToElement(target: HTMLElement | null): void {
  if (!target) return
  window.setTimeout(() => {
    if (!target.isConnected) return
    if (target instanceof HTMLButtonElement && target.disabled) return
    if (target instanceof HTMLInputElement && target.disabled) return
    target.focus()
  }, 0)
}
