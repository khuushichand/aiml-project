const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const sortLogitBias = (value: Record<string, number>): Record<string, number> => {
  const sorted: Record<string, number> = {}
  for (const key of Object.keys(value).sort()) {
    sorted[key] = value[key]
  }
  return sorted
}

const normalizeLogitBiasObject = (
  raw: Record<string, unknown>
): { value: Record<string, number> | null; error: string | null } => {
  const out: Record<string, number> = {}
  for (const [rawKey, rawValue] of Object.entries(raw)) {
    const key = String(rawKey || "").trim()
    if (!key) continue
    const parsed = toFiniteNumber(rawValue)
    if (parsed == null) {
      return {
        value: null,
        error: `logit_bias value for key "${key}" must be a finite number.`
      }
    }
    out[key] = parsed
  }

  if (Object.keys(out).length === 0) {
    return { value: null, error: null }
  }

  return { value: sortLogitBias(out), error: null }
}

export const normalizeLogitBiasValue = (
  value: unknown
): Record<string, number> => {
  if (!isRecord(value)) return {}
  const normalized = normalizeLogitBiasObject(value)
  return normalized.value ?? {}
}

export const parseLogitBiasInput = (
  value: string
): { value: Record<string, number> | null; error: string | null } => {
  const trimmed = String(value || "").trim()
  if (!trimmed) {
    return { value: null, error: null }
  }

  try {
    const parsed = JSON.parse(trimmed)
    if (!isRecord(parsed)) {
      return {
        value: null,
        error: "logit_bias payload must be a JSON object."
      }
    }
    return normalizeLogitBiasObject(parsed)
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown parse error"
    return {
      value: null,
      error: `Invalid JSON: ${detail}`
    }
  }
}

export const formatLogitBiasValue = (value: unknown): string => {
  const normalized = normalizeLogitBiasValue(value)
  if (Object.keys(normalized).length === 0) return ""
  return JSON.stringify(normalized, null, 2)
}

export const withLogitBiasEntry = (
  value: unknown,
  token: string,
  bias: number
): Record<string, number> => {
  const normalized = normalizeLogitBiasValue(value)
  const key = String(token || "").trim()
  if (!key || !Number.isFinite(bias)) return normalized
  return {
    ...normalized,
    [key]: bias
  }
}

export type LogitBiasTokenPreset = "ban" | "favor"

const LOGIT_BIAS_TOKEN_PRESET_VALUE: Record<LogitBiasTokenPreset, number> = {
  ban: -100,
  favor: 5
}

const normalizeTokenId = (tokenId: number | string): string => {
  if (typeof tokenId === "number") {
    return Number.isFinite(tokenId) ? String(Math.trunc(tokenId)) : ""
  }
  return String(tokenId || "").trim()
}

export const withTokenIdPresetLogitBias = (
  value: unknown,
  tokenId: number | string,
  preset: LogitBiasTokenPreset
): Record<string, number> => {
  const token = normalizeTokenId(tokenId)
  if (!token) {
    return normalizeLogitBiasValue(value)
  }
  return withLogitBiasEntry(value, token, LOGIT_BIAS_TOKEN_PRESET_VALUE[preset])
}

export const withTokenIdsPresetLogitBias = (
  value: unknown,
  tokenIds: Array<number | string>,
  preset: LogitBiasTokenPreset
): Record<string, number> => {
  let next = normalizeLogitBiasValue(value)
  const seen = new Set<string>()
  for (const tokenId of tokenIds) {
    const token = normalizeTokenId(tokenId)
    if (!token || seen.has(token)) continue
    seen.add(token)
    next = withLogitBiasEntry(
      next,
      token,
      LOGIT_BIAS_TOKEN_PRESET_VALUE[preset]
    )
  }
  return next
}

export const withoutLogitBiasEntry = (
  value: unknown,
  token: string
): Record<string, number> => {
  const normalized = normalizeLogitBiasValue(value)
  const key = String(token || "").trim()
  if (!key || !Object.prototype.hasOwnProperty.call(normalized, key)) {
    return normalized
  }
  const next = { ...normalized }
  delete next[key]
  return next
}
