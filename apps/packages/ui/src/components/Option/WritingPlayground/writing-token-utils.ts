export type WritingTokenPreviewRow = {
  index: number
  id: number
  text: string
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
    index,
    id,
    text: normalizeTokenPreviewText(strings?.[index])
  }))
}
