export type WritingTokenPreviewRow = {
  index: number
  id: number
  text: string
  rawText: string
}

export const normalizeTokenPreviewText = (value: string | undefined): string => {
  if (!value) return ""
  return value
    .replace(/\r/g, "\\r")
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t")
}

export const buildTokenPreviewRows = (
  ids: number[],
  strings?: string[],
  maxRows = 200
): WritingTokenPreviewRow[] => {
  if (!Array.isArray(ids) || ids.length === 0) return []
  const limit = Number.isFinite(maxRows) ? Math.max(0, Math.floor(maxRows)) : 200
  return ids.slice(0, limit).map((id, index) => ({
    rawText: typeof strings?.[index] === "string" ? strings[index] : "",
    index,
    id,
    text: normalizeTokenPreviewText(strings?.[index])
  }))
}

export const joinTokenStrings = (strings?: string[]): string => {
  if (!Array.isArray(strings) || strings.length === 0) return ""
  return strings.map((value) => (typeof value === "string" ? value : "")).join("")
}
