type Placeholder = "{predict}" | "{fill}"

const clampIndex = (value: number, length: number): number => {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(length, Math.floor(value)))
}

export const applyPlaceholderAtRange = (
  source: string,
  selectionStart: number,
  selectionEnd: number,
  placeholder: Placeholder
): { nextValue: string; cursor: number } => {
  return applyTextAtRange(source, selectionStart, selectionEnd, placeholder)
}

export const applyTextAtRange = (
  source: string,
  selectionStart: number,
  selectionEnd: number,
  textToInsert: string
): { nextValue: string; cursor: number } => {
  const text = typeof source === "string" ? source : ""
  const length = text.length
  const normalizedStart = clampIndex(selectionStart, length)
  const normalizedEnd = clampIndex(selectionEnd, length)
  const start = Math.min(normalizedStart, normalizedEnd)
  const end = Math.max(normalizedStart, normalizedEnd)
  const insertText = typeof textToInsert === "string" ? textToInsert : ""

  const nextValue = text.slice(0, start) + insertText + text.slice(end)
  const cursor = start + insertText.length

  return { nextValue, cursor }
}
