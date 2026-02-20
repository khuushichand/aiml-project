const DEFAULT_KEYBOARD_INSET_THRESHOLD = 90

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null
  }
  return value
}

export type MobileComposerViewportState = {
  keyboardInsetPx: number
  keyboardOpen: boolean
}

export const computeKeyboardInsetPx = (params: {
  layoutViewportHeight: number
  visualViewportHeight: number
  visualViewportOffsetTop?: number
}): number => {
  const layoutHeight = toFiniteNumber(params.layoutViewportHeight)
  const visualHeight = toFiniteNumber(params.visualViewportHeight)
  const viewportOffsetTop =
    toFiniteNumber(params.visualViewportOffsetTop) ?? 0

  if (
    layoutHeight == null ||
    visualHeight == null ||
    layoutHeight <= 0 ||
    visualHeight <= 0
  ) {
    return 0
  }

  const inset = layoutHeight - (visualHeight + viewportOffsetTop)
  if (!Number.isFinite(inset) || inset <= 0) {
    return 0
  }
  return Math.max(0, Math.round(inset))
}

export const isKeyboardLikelyOpen = (params: {
  keyboardInsetPx: number
  thresholdPx?: number
}): boolean => {
  const inset = toFiniteNumber(params.keyboardInsetPx)
  const threshold =
    toFiniteNumber(params.thresholdPx) ?? DEFAULT_KEYBOARD_INSET_THRESHOLD
  if (inset == null) return false
  return inset >= Math.max(32, Math.round(threshold))
}

export const resolveMobileComposerViewportState = (params: {
  layoutViewportHeight: number
  visualViewportHeight: number
  visualViewportOffsetTop?: number
  thresholdPx?: number
}): MobileComposerViewportState => {
  const keyboardInsetPx = computeKeyboardInsetPx(params)
  return {
    keyboardInsetPx,
    keyboardOpen: isKeyboardLikelyOpen({
      keyboardInsetPx,
      thresholdPx: params.thresholdPx
    })
  }
}
