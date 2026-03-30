import { normalizeKeywordList } from "./worldBookEntryUtils"

export const normalizeKeywords = (value: any): string[] => {
  return normalizeKeywordList(value)
}

export const normalizeEntryGroup = (value: unknown): string | null => {
  const normalized = String(value ?? "").trim()
  return normalized.length > 0 ? normalized : null
}

export const buildMatchPreview = (keywordsValue: any, opts: { caseSensitive?: boolean; regexMatch?: boolean; wholeWord?: boolean }) => {
  const keyword = normalizeKeywords(keywordsValue)[0]
  if (!keyword) return "Add a keyword to see a preview."
  if (opts.regexMatch) {
    return `Regex enabled. Example pattern: /${keyword}/`
  }
  const lower = keyword.toLowerCase()
  const upper = keyword.toUpperCase()
  const caseExample = opts.caseSensitive ? `'${keyword}' only` : `'${lower}', '${upper}'`
  const wordExample = opts.wholeWord ? "whole-word matches" : "partial matches"
  return `Preview: ${caseExample}; ${wordExample}.`
}

export const BULK_ENTRY_FORMAT_EXAMPLES = [
  { separator: "=>", example: "keyword1, keyword2 => content" },
  { separator: "->", example: "keyword1, keyword2 -> content" },
  { separator: "|", example: "keyword1, keyword2 | content" },
  { separator: "\t", example: "keyword1, keyword2<TAB>content" }
] as const

export const ATTACHMENT_MATRIX_CHARACTER_THRESHOLD = 10
export const ATTACHMENT_LIST_PAGE_SIZE = 8
export const ATTACHMENT_FEEDBACK_DURATION_MS = 2400
export const ATTACHMENT_PULSE_DURATION_MS = 1200
export const MODAL_BODY_SCROLL_STYLE: React.CSSProperties = {
  maxHeight: "80vh",
  overflowY: "auto"
}
export const LOREBOOK_DEBUG_ENTRYPOINT_HREF = "/chat?from=world-books&focus=lorebook-debug"
export const LOREBOOK_METRIC_LABELS = {
  entriesMatched: "Entries matched",
  booksUsed: "Books used",
  tokensUsed: "Tokens used",
  tokenBudget: "Token budget"
} as const
export const TEST_MATCHING_SAMPLE_STORAGE_KEY = "tldw:world-books:test-match:sample:v1"
export const FALLBACK_AI_GENERATION_MODEL = "gpt-4o-mini"
export const DEFAULT_AI_GENERATION_COUNT = 3
export const MIN_AI_GENERATION_COUNT = 1
export const MAX_AI_GENERATION_COUNT = 8
export const ACCESSIBLE_SWITCH_TEXT_PROPS = {
  checkedChildren: "On",
  unCheckedChildren: "Off"
} as const

export type WorldBookGeneratedEntryDraft = {
  id: string
  keywordsText: string
  content: string
  priority: number
  group: string
}

export const loadSavedTestMatchingSample = (): string => {
  if (typeof window === "undefined") return ""
  try {
    const raw = window.sessionStorage.getItem(TEST_MATCHING_SAMPLE_STORAGE_KEY)
    return typeof raw === "string" ? raw : ""
  } catch {
    return ""
  }
}

export const persistTestMatchingSample = (value: string) => {
  if (typeof window === "undefined") return
  try {
    if (!value) {
      window.sessionStorage.removeItem(TEST_MATCHING_SAMPLE_STORAGE_KEY)
      return
    }
    window.sessionStorage.setItem(TEST_MATCHING_SAMPLE_STORAGE_KEY, value)
  } catch {
    // ignore storage failures
  }
}

export const toWorldBookGenerationString = (value: unknown): string | null => {
  if (typeof value === "string") {
    const normalized = value.trim()
    return normalized.length > 0 ? normalized : null
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return null
}

export const toWorldBookGenerationModel = (value: unknown): string | null => {
  const direct = toWorldBookGenerationString(value)
  if (direct) return direct
  if (!value || typeof value !== "object") return null
  const modelRecord = value as Record<string, unknown>
  return (
    toWorldBookGenerationString(modelRecord.name) ||
    toWorldBookGenerationString(modelRecord.id) ||
    toWorldBookGenerationString(modelRecord.model_id) ||
    toWorldBookGenerationString(modelRecord.display_name)
  )
}

export const pickWorldBookGenerationModel = (provider: unknown): string | null => {
  if (!provider || typeof provider !== "object") return null
  const providerRecord = provider as Record<string, unknown>
  const modelsRaw = Array.isArray(providerRecord.models)
    ? providerRecord.models
    : Array.isArray(providerRecord.models_info)
      ? providerRecord.models_info
      : []
  for (const modelEntry of modelsRaw) {
    const model = toWorldBookGenerationModel(modelEntry)
    if (model) return model
  }
  return null
}

export const resolveWorldBookGenerationProviderConfig = (
  payload: unknown
): { provider?: string; model: string } => {
  const result: { provider?: string; model: string } = {
    model: FALLBACK_AI_GENERATION_MODEL
  }
  if (!payload || typeof payload !== "object") return result

  const root = payload as Record<string, unknown>
  const providersRaw = Array.isArray(root.providers) ? root.providers : []
  const defaultProviderName = toWorldBookGenerationString(root.default_provider)

  const providers = providersRaw
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null
      const providerRecord = entry as Record<string, unknown>
      const name =
        toWorldBookGenerationString(providerRecord.name) ||
        toWorldBookGenerationString(providerRecord.provider)
      if (!name) return null
      return {
        name,
        model: pickWorldBookGenerationModel(providerRecord)
      }
    })
    .filter((entry): entry is { name: string; model: string | null } => entry !== null)

  const selected =
    providers.find((provider) => provider.name === defaultProviderName) || providers[0] || null
  if (!selected) return result

  result.provider = selected.name
  result.model = selected.model || result.model
  return result
}

export const normalizeWorldBookCompletionText = (candidate: unknown): string => {
  if (typeof candidate === "string") return candidate.trim()
  if (Array.isArray(candidate)) {
    return candidate
      .map((part) => {
        if (typeof part === "string") return part
        if (!part || typeof part !== "object") return ""
        const partRecord = part as Record<string, unknown>
        return toWorldBookGenerationString(partRecord.text) || ""
      })
      .join("\n")
      .trim()
  }
  return ""
}

export type WorldBookFormMode = "create" | "edit"
export type EditWorldBookConflictState = {
  attemptedValues: Record<string, any>
  message: string
}
export type EntryFilterPreset = {
  enabledFilter: "all" | "enabled" | "disabled"
  matchFilter: "all" | "regex" | "plain"
  searchText: string
}

export const DEFAULT_ENTRY_FILTER_PRESET: EntryFilterPreset = {
  enabledFilter: "all",
  matchFilter: "all",
  searchText: ""
}

export const getReasonLabel = (reason: string) => {
  if (reason === "regex_match") return "Regex match"
  if (reason === "depth") return "Depth rule"
  return "Keyword match"
}

export const normalizeWorldBookSetting = (
  value: unknown,
  fallback: number,
  min: number,
  max: number
) => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(min, Math.min(max, parsed))
}
