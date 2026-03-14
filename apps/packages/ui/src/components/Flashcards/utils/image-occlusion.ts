export interface NormalizedOcclusionRect {
  x: number
  y: number
  width: number
  height: number
}

export interface FinalizeNormalizedOcclusionRectInput {
  startClientX: number
  startClientY: number
  endClientX: number
  endClientY: number
  bounds: {
    left: number
    top: number
    width: number
    height: number
  }
  minSizePx: number
}

const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max)

const normalizePoint = (
  clientX: number,
  clientY: number,
  bounds: FinalizeNormalizedOcclusionRectInput["bounds"]
) => ({
  x: clamp(clientX - bounds.left, 0, bounds.width),
  y: clamp(clientY - bounds.top, 0, bounds.height)
})

export const finalizeNormalizedOcclusionRect = (
  input: FinalizeNormalizedOcclusionRectInput
): NormalizedOcclusionRect | null => {
  const start = normalizePoint(input.startClientX, input.startClientY, input.bounds)
  const end = normalizePoint(input.endClientX, input.endClientY, input.bounds)

  const widthPx = Math.abs(end.x - start.x)
  const heightPx = Math.abs(end.y - start.y)
  if (widthPx < input.minSizePx || heightPx < input.minSizePx) {
    return null
  }

  const leftPx = Math.min(start.x, end.x)
  const topPx = Math.min(start.y, end.y)

  return {
    x: leftPx / input.bounds.width,
    y: topPx / input.bounds.height,
    width: widthPx / input.bounds.width,
    height: heightPx / input.bounds.height
  }
}

export const resolveNextSelectedOcclusionId = (
  regionIds: string[],
  removedId: string
): string | null => {
  const removedIndex = regionIds.indexOf(removedId)
  if (removedIndex === -1) {
    return regionIds.at(-1) ?? null
  }
  if (regionIds.length <= 1) {
    return null
  }
  return regionIds[removedIndex + 1] ?? regionIds[removedIndex - 1] ?? null
}

export const formatNormalizedOcclusionRect = (rect: NormalizedOcclusionRect): string =>
  `x: ${(rect.x * 100).toFixed(1)}%, y: ${(rect.y * 100).toFixed(1)}%, w: ${(rect.width * 100).toFixed(1)}%, h: ${(rect.height * 100).toFixed(1)}%`
