import { normalizeDictionaryTags } from "../listUtils"

type NormalizeDictionaryFormPayloadOptions = {
  allowNullDefaultTokenBudget?: boolean
  allowNullCategory?: boolean
  includeEmptyTags?: boolean
}

export function toOptionalPositiveInteger(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.floor(value)
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.floor(parsed)
    }
  }
  return undefined
}

export function normalizeDictionaryFormPayload(
  values: Record<string, any>,
  options: NormalizeDictionaryFormPayloadOptions = {}
): Record<string, any> {
  const nextPayload = { ...values }
  if (Object.prototype.hasOwnProperty.call(nextPayload, "category")) {
    const rawCategory = nextPayload.category
    if (rawCategory === null) {
      if (!options.allowNullCategory) {
        delete nextPayload.category
      }
    } else if (typeof rawCategory === "string") {
      const normalizedCategory = rawCategory.trim()
      if (!normalizedCategory) {
        if (options.allowNullCategory) {
          nextPayload.category = null
        } else {
          delete nextPayload.category
        }
      } else {
        nextPayload.category = normalizedCategory
      }
    } else if (rawCategory == null) {
      delete nextPayload.category
    } else {
      nextPayload.category = String(rawCategory).trim()
    }
  }

  if (Object.prototype.hasOwnProperty.call(nextPayload, "tags")) {
    const normalizedTags = normalizeDictionaryTags(nextPayload.tags)
    if (normalizedTags.length > 0 || options.includeEmptyTags) {
      nextPayload.tags = normalizedTags
    } else {
      delete nextPayload.tags
    }
  }

  if (!Object.prototype.hasOwnProperty.call(nextPayload, "default_token_budget")) {
    return nextPayload
  }

  const rawBudget = nextPayload.default_token_budget
  if (rawBudget === null) {
    if (!options.allowNullDefaultTokenBudget) {
      delete nextPayload.default_token_budget
    }
    return nextPayload
  }

  const normalizedBudget = toOptionalPositiveInteger(rawBudget)
  if (normalizedBudget === undefined) {
    delete nextPayload.default_token_budget
  } else {
    nextPayload.default_token_budget = normalizedBudget
  }
  return nextPayload
}

export function normalizeCreateDictionaryPayload(
  values: Record<string, any>
): Record<string, any> {
  const payload = normalizeDictionaryFormPayload(values, {
    allowNullCategory: false,
    includeEmptyTags: false,
  })
  delete payload.starter_template
  return payload
}
