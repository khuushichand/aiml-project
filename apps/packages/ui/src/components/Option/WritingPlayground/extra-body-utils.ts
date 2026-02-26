type Primitive = string | number | boolean | null | undefined

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const sanitizeValue = (value: unknown): unknown => {
  if (value == null) return undefined
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : undefined
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined
  }
  if (typeof value === "boolean") return value
  if (Array.isArray(value)) {
    const items = value
      .map((item) => sanitizeValue(item))
      .filter((item) => item !== undefined) as Array<Primitive | Record<string, unknown>>
    return items.length > 0 ? items : undefined
  }
  if (isRecord(value)) {
    const out: Record<string, unknown> = {}
    for (const [key, entry] of Object.entries(value)) {
      const sanitized = sanitizeValue(entry)
      if (sanitized !== undefined) {
        out[key] = sanitized
      }
    }
    return Object.keys(out).length > 0 ? out : undefined
  }
  return undefined
}

export const parseStringListInput = (value: string): string[] => {
  if (!value.trim()) return []
  return value
    .split(/[\n,]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
}

export const sanitizeExtraBodyPayload = (
  payload: Record<string, unknown> | null | undefined
): Record<string, unknown> => {
  if (!isRecord(payload)) return {}
  const sanitized = sanitizeValue(payload)
  if (!isRecord(sanitized)) return {}
  return sanitized
}

export const parseExtraBodyJsonObject = (
  value: string
): { value: Record<string, unknown>; error: string | null } => {
  const trimmed = String(value || "").trim()
  if (!trimmed) {
    return { value: {}, error: null }
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (!isRecord(parsed)) {
      return {
        value: {},
        error: "extra_body payload must be a JSON object."
      }
    }
    return {
      value: sanitizeExtraBodyPayload(parsed),
      error: null
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown parse error"
    return {
      value: {},
      error: `Invalid JSON: ${detail}`
    }
  }
}

type BuildExtraBodyInput = {
  top_k: number
  seed: number | null
  stop: string[]
  advanced_extra_body?: Record<string, unknown> | null
}

export const buildExtraBodyPayload = (
  input: BuildExtraBodyInput
): Record<string, unknown> | undefined => {
  const payload = sanitizeExtraBodyPayload(input.advanced_extra_body)

  if (input.top_k > 0) {
    payload.top_k = input.top_k
  }
  if (input.seed != null && Number.isFinite(input.seed)) {
    payload.seed = input.seed
  }

  const stop = input.stop
    .map((entry) => String(entry || "").trim())
    .filter(Boolean)
  if (stop.length > 0) {
    payload.stop = stop
  }

  return Object.keys(payload).length > 0 ? payload : undefined
}
