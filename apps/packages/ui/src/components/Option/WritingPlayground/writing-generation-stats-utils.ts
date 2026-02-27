export const computeTokensPerSecond = (
  tokenCount: number,
  elapsedMs: number
): number => {
  if (!Number.isFinite(tokenCount) || !Number.isFinite(elapsedMs)) return 0
  if (tokenCount <= 0 || elapsedMs <= 0) return 0
  return tokenCount / (elapsedMs / 1000)
}

export const estimateTokenCountFromText = (value: string): number => {
  const trimmed = String(value || "").trim()
  if (!trimmed) return 0
  return trimmed.split(/\s+/).filter(Boolean).length
}
