import { parseWorldInfoImportPayload } from "./writing-world-info-transfer-utils"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const IMPORT_METADATA_KEYS = new Set([
  "id",
  "name",
  "title",
  "schema_version",
  "schemaVersion",
  "version",
  "created_at",
  "updated_at",
  "payload",
  "payload_json",
  "session",
  "sessions"
])

const parseMaybeJsonValue = (value: unknown): unknown => {
  if (typeof value !== "string") return value
  const trimmed = value.trim()
  if (!trimmed) return ""
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return undefined
}

const toBoolean = (value: unknown): boolean | undefined => {
  if (typeof value === "boolean") return value
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (normalized === "true") return true
    if (normalized === "false") return false
  }
  return undefined
}

const toString = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? value : undefined
}

const firstDefined = <T>(...values: Array<T | undefined>): T | undefined => {
  for (const value of values) {
    if (value !== undefined) return value
  }
  return undefined
}

const readNumber = (
  source: Record<string, unknown>,
  keys: string[]
): number | undefined => {
  for (const key of keys) {
    const value = toNumber(source[key])
    if (value !== undefined) return value
  }
  return undefined
}

const readBoolean = (
  source: Record<string, unknown>,
  keys: string[]
): boolean | undefined => {
  for (const key of keys) {
    const value = toBoolean(source[key])
    if (value !== undefined) return value
  }
  return undefined
}

const readString = (
  source: Record<string, unknown>,
  keys: string[]
): string | undefined => {
  for (const key of keys) {
    const value = toString(source[key])
    if (value !== undefined) return value
  }
  return undefined
}

const normalizeModelHint = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const normalizeProviderHint = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim().toLowerCase()
  const compact = trimmed.replace(/\s+/g, "")
  const providerAliases: Record<string, string> = {
    custom_openai_api: "custom-openai-api",
    custom_openai_api_2: "custom-openai-api-2",
    custom_openai_api2: "custom-openai-api-2",
    "custom-openai-api2": "custom-openai-api-2",
    llamacpp: "llama.cpp",
    llama_cpp: "llama.cpp",
    koboldcpp: "kobold",
    tabbyapi: "tabby",
    oobabooga: "ooba",
    local_llm: "local-llm",
    localllm: "local-llm"
  }
  const aliased = providerAliases[compact] ?? providerAliases[trimmed]
  if (aliased) return aliased
  const normalized = compact.replace(/_/g, "-")
  if (normalized.length > 0) return normalized
  return trimmed.length > 0 ? trimmed : undefined
}

const normalizeEndpointApiProviderHint = (value: unknown): string | undefined => {
  const parsed = toNumber(value)
  if (parsed === undefined) return undefined
  const endpointApiProviderMap: Record<string, string> = {
    "0": "llama.cpp",
    "2": "kobold",
    "3": "openai"
  }
  const normalizedKey = String(Math.trunc(parsed))
  const mapped = endpointApiProviderMap[normalizedKey]
  if (!mapped) return undefined
  return normalizeProviderHint(mapped)
}

const readModelHint = (
  source: Record<string, unknown>
): string | undefined => {
  return (
    normalizeModelHint(source.model) ??
    normalizeModelHint(source.model_id) ??
    normalizeModelHint(source.modelId) ??
    normalizeModelHint(source.endpointModel)
  )
}

const readProviderHint = (
  source: Record<string, unknown>
): string | undefined => {
  return (
    normalizeProviderHint(source.provider) ??
    normalizeProviderHint(source.api_provider) ??
    normalizeProviderHint(source.apiProvider) ??
    normalizeProviderHint(source.endpointProvider) ??
    normalizeEndpointApiProviderHint(source.endpointAPI) ??
    normalizeEndpointApiProviderHint(source.endpointApi) ??
    normalizeEndpointApiProviderHint(source.endpoint_api)
  )
}

const normalizeStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry || "").trim()).filter(Boolean)
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return []
    return trimmed
      .split(/[\n,]+/)
      .map((entry) => entry.trim())
      .filter(Boolean)
  }
  return []
}

const normalizePrompt = (value: unknown): string | undefined => {
  if (typeof value === "string") {
    return value
  }
  if (Array.isArray(value)) {
    const parts = value
      .map((entry) => {
        if (typeof entry === "string") return entry
        if (isRecord(entry)) {
          if (typeof entry.content === "string") return entry.content
          if (typeof entry.text === "string") return entry.text
        }
        return ""
      })
      .map((entry) => entry.trim())
      .filter(Boolean)
    if (parts.length > 0) {
      return parts.join("\n\n")
    }
    return undefined
  }
  if (isRecord(value)) {
    if (typeof value.content === "string") return value.content
    if (typeof value.text === "string") return value.text
  }
  return undefined
}

type AdvancedParamMap = {
  target: string
  keys: string[]
  kind: "number" | "boolean" | "string-list" | "string" | "record"
  sampler?: string
  non_openai_presets_only?: boolean
}

const ADVANCED_PARAM_MAP: AdvancedParamMap[] = [
  {
    target: "dynatemp_range",
    keys: ["dynatemp_range", "dynatempRange", "dynaTempRange"],
    kind: "number",
    sampler: "dynatemp",
    non_openai_presets_only: true
  },
  {
    target: "dynatemp_exponent",
    keys: ["dynatemp_exponent", "dynatempExponent", "dynaTempExp"],
    kind: "number",
    sampler: "dynatemp",
    non_openai_presets_only: true
  },
  {
    target: "repeat_penalty",
    keys: ["repeat_penalty", "repeatPenalty"],
    kind: "number",
    sampler: "rep_pen",
    non_openai_presets_only: true
  },
  {
    target: "repeat_last_n",
    keys: ["repeat_last_n", "repeatLastN"],
    kind: "number",
    sampler: "rep_pen",
    non_openai_presets_only: true
  },
  {
    target: "penalize_nl",
    keys: ["penalize_nl", "penalizeNl"],
    kind: "boolean",
    non_openai_presets_only: true
  },
  {
    target: "ignore_eos",
    keys: ["ignore_eos", "ignoreEos"],
    kind: "boolean",
    non_openai_presets_only: true
  },
  {
    target: "mirostat",
    keys: ["mirostat"],
    kind: "number",
    sampler: "mirostat",
    non_openai_presets_only: true
  },
  {
    target: "mirostat_tau",
    keys: ["mirostat_tau", "mirostatTau"],
    kind: "number",
    sampler: "mirostat",
    non_openai_presets_only: true
  },
  {
    target: "mirostat_eta",
    keys: ["mirostat_eta", "mirostatEta"],
    kind: "number",
    sampler: "mirostat",
    non_openai_presets_only: true
  },
  {
    target: "typical_p",
    keys: ["typical_p", "typicalP"],
    kind: "number",
    sampler: "typical_p",
    non_openai_presets_only: true
  },
  {
    target: "min_p",
    keys: ["min_p", "minP"],
    kind: "number",
    sampler: "min_p",
    non_openai_presets_only: true
  },
  {
    target: "tfs_z",
    keys: ["tfs_z", "tfsZ"],
    kind: "number",
    sampler: "tfs_z",
    non_openai_presets_only: true
  },
  {
    target: "xtc_threshold",
    keys: ["xtc_threshold", "xtcThreshold"],
    kind: "number",
    sampler: "xtc",
    non_openai_presets_only: true
  },
  {
    target: "xtc_probability",
    keys: ["xtc_probability", "xtcProbability"],
    kind: "number",
    sampler: "xtc",
    non_openai_presets_only: true
  },
  {
    target: "dry_multiplier",
    keys: ["dry_multiplier", "dryMultiplier"],
    kind: "number",
    sampler: "dry",
    non_openai_presets_only: true
  },
  {
    target: "dry_base",
    keys: ["dry_base", "dryBase"],
    kind: "number",
    sampler: "dry",
    non_openai_presets_only: true
  },
  {
    target: "dry_allowed_length",
    keys: ["dry_allowed_length", "dryAllowedLength"],
    kind: "number",
    sampler: "dry",
    non_openai_presets_only: true
  },
  {
    target: "dry_penalty_last_n",
    keys: ["dry_penalty_last_n", "dryPenaltyLastN", "dryPenaltyRange"],
    kind: "number",
    sampler: "dry",
    non_openai_presets_only: true
  },
  {
    target: "dry_sequence_breakers",
    keys: ["dry_sequence_breakers", "drySequenceBreakers"],
    kind: "string-list",
    sampler: "dry",
    non_openai_presets_only: true
  },
  {
    target: "banned_tokens",
    keys: ["banned_tokens", "bannedTokens"],
    kind: "string-list",
    sampler: "ban_tokens",
    non_openai_presets_only: true
  },
  {
    target: "grammar",
    keys: ["grammar"],
    kind: "string",
    non_openai_presets_only: true
  },
  {
    target: "logit_bias",
    keys: ["logit_bias", "logitBias"],
    kind: "record"
  },
  {
    target: "post_sampling_probs",
    keys: ["post_sampling_probs", "postSamplingProbs"],
    kind: "boolean"
  }
]

const normalizeLogitBias = (value: unknown): Record<string, number> | undefined => {
  if (!isRecord(value)) return undefined

  const direct: Record<string, number> = {}
  for (const [key, rawValue] of Object.entries(value)) {
    const token = String(key || "").trim()
    if (!token) continue
    const bias = toNumber(rawValue)
    if (bias === undefined) continue
    direct[token] = bias
  }
  if (Object.keys(direct).length > 0) {
    return direct
  }

  const nested = value.bias
  if (!isRecord(nested)) return undefined
  const out: Record<string, number> = {}
  for (const rawEntry of Object.values(nested)) {
    if (!isRecord(rawEntry)) continue
    const ids = Array.isArray(rawEntry.ids) ? rawEntry.ids : []
    const firstTokenId = ids
      .map((entry) => toNumber(entry))
      .find((entry): entry is number => entry !== undefined)
    const bias = toNumber(rawEntry.power ?? rawEntry.bias ?? rawEntry.value)
    if (firstTokenId === undefined || bias === undefined) continue
    out[String(Math.trunc(firstTokenId))] = bias
  }
  if (Object.keys(out).length === 0) return undefined
  return out
}

const normalizeContextBlock = (value: unknown): Record<string, unknown> | undefined => {
  if (!isRecord(value)) return undefined
  const prefix = typeof value.prefix === "string" ? value.prefix : ""
  const text = typeof value.text === "string" ? value.text : ""
  const suffix = typeof value.suffix === "string" ? value.suffix : ""
  const explicitEnabled = toBoolean(value.enabled)
  const enabled = explicitEnabled ?? Boolean(text.trim())
  if (!enabled && !prefix && !text && !suffix) {
    return undefined
  }
  return {
    enabled,
    prefix,
    text,
    suffix
  }
}

const normalizeAuthorNote = (
  value: unknown,
  depth: number | undefined
): Record<string, unknown> | undefined => {
  const block = normalizeContextBlock(value)
  if (!block && depth === undefined) return undefined
  const insertionDepth =
    depth === undefined ? 1 : Math.max(1, Math.floor(depth))
  return {
    enabled: block?.enabled ?? false,
    prefix: block?.prefix ?? "",
    text: block?.text ?? "",
    suffix: block?.suffix ?? "",
    insertion_depth: insertionDepth
  }
}

const normalizeWorldInfo = (value: unknown): Record<string, unknown> | undefined => {
  const parsed = parseWorldInfoImportPayload(value)
  if (parsed.error || !parsed.value) return undefined
  const entries = Array.isArray(parsed.value.entries) ? parsed.value.entries : []
  if (entries.length === 0) return undefined
  const searchRange =
    typeof parsed.value.search_range === "number"
      ? Math.max(0, Math.floor(parsed.value.search_range))
      : 2000
  return {
    enabled: true,
    prefix: typeof parsed.value.prefix === "string" ? parsed.value.prefix : "",
    suffix: typeof parsed.value.suffix === "string" ? parsed.value.suffix : "",
    search_range: searchRange,
    entries
  }
}

const readEnabledSamplers = (
  source: Record<string, unknown>
): Set<string> | null => {
  const raw = firstDefined(source.enabledSamplers, source.enabled_samplers)
  const enabled = (
    Array.isArray(raw)
      ? raw
      : typeof raw === "string"
        ? raw.split(/[\n,]+/)
        : []
  )
    .map((entry) => String(entry || "").trim().toLowerCase())
    .filter(Boolean)
  return enabled.length > 0 ? new Set(enabled) : null
}

const isOpenAiPresetsCompatMode = (
  source: Record<string, unknown>
): boolean => {
  const openaiPresets = readBoolean(source, [
    "openaiPresets",
    "openai_presets"
  ])
  if (openaiPresets !== true) return false
  const endpointApi = readNumber(source, [
    "endpointAPI",
    "endpointApi",
    "endpoint_api"
  ])
  if (endpointApi !== undefined) {
    return Math.trunc(endpointApi) === 3
  }
  const provider = readProviderHint(source)
  return provider === "openai"
}

const buildSettings = (
  source: Record<string, unknown>
): Record<string, unknown> | undefined => {
  const settings: Record<string, unknown> = {}
  const enabledSamplers = readEnabledSamplers(source)
  const openaiCompatPresetsMode = isOpenAiPresetsCompatMode(source)

  const samplerEnabled = (sampler?: string): boolean => {
    if (!sampler) return true
    if (!enabledSamplers) return true
    return enabledSamplers.has(String(sampler).trim().toLowerCase())
  }

  const numericMap: Array<{
    target: string
    keys: string[]
    sampler?: string
    non_openai_presets_only?: boolean
  }> = [
    { target: "temperature", keys: ["temperature"], sampler: "temperature" },
    { target: "top_p", keys: ["top_p", "topP"], sampler: "top_p" },
    {
      target: "top_k",
      keys: ["top_k", "topK"],
      sampler: "top_k",
      non_openai_presets_only: true
    },
    { target: "max_tokens", keys: ["max_tokens", "maxTokens", "maxPredictTokens"] },
    {
      target: "presence_penalty",
      keys: ["presence_penalty", "presencePenalty"],
      sampler: "pres_pen"
    },
    {
      target: "frequency_penalty",
      keys: ["frequency_penalty", "frequencyPenalty"],
      sampler: "freq_pen"
    },
    { target: "seed", keys: ["seed"] },
    { target: "top_logprobs", keys: ["top_logprobs", "topLogprobs"] }
  ]

  for (const entry of numericMap) {
    if (
      entry.non_openai_presets_only &&
      openaiCompatPresetsMode
    ) {
      continue
    }
    if (!samplerEnabled(entry.sampler)) {
      continue
    }
    const value = readNumber(source, entry.keys)
    if (value !== undefined && entry.target === "max_tokens" && value <= 0) {
      continue
    }
    if (value !== undefined && entry.target === "seed" && value < 0) {
      continue
    }
    if (value !== undefined && entry.target === "top_logprobs" && value <= 0) {
      continue
    }
    if (value !== undefined) {
      settings[entry.target] = value
    }
  }

  const tokenStreaming = readBoolean(source, ["token_streaming", "tokenStreaming"])
  if (tokenStreaming !== undefined) {
    settings.token_streaming = tokenStreaming
  }

  const logprobs = readBoolean(source, ["logprobs"])
  if (logprobs !== undefined) {
    settings.logprobs = logprobs
  }

  const useBasicStoppingMode = readBoolean(source, [
    "use_basic_stopping_mode",
    "useBasicStoppingMode"
  ])
  if (useBasicStoppingMode !== undefined) {
    settings.use_basic_stopping_mode = useBasicStoppingMode
  }

  const basicStoppingModeType = readString(source, [
    "basic_stopping_mode_type",
    "basicStoppingModeType"
  ])
  if (basicStoppingModeType !== undefined) {
    const normalized = basicStoppingModeType
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_")
    if (
      normalized === "max_tokens" ||
      normalized === "new_line" ||
      normalized === "fill_suffix"
    ) {
      settings.basic_stopping_mode_type = normalized
    }
  }

  const stop = firstDefined(
    source.stop,
    source.stoppingStrings
  )
  const stopList = normalizeStringList(stop)
  if (stopList.length > 0) {
    settings.stop = stopList
  }

  const advancedExtraBody: Record<string, unknown> = {}
  for (const mapping of ADVANCED_PARAM_MAP) {
    if (
      mapping.non_openai_presets_only &&
      openaiCompatPresetsMode
    ) {
      continue
    }
    if (!samplerEnabled(mapping.sampler)) {
      continue
    }
    if (mapping.kind === "number") {
      const value = readNumber(source, mapping.keys)
      if (value !== undefined) advancedExtraBody[mapping.target] = value
      continue
    }
    if (mapping.kind === "boolean") {
      const value = readBoolean(source, mapping.keys)
      if (value !== undefined) advancedExtraBody[mapping.target] = value
      continue
    }
    if (mapping.kind === "string") {
      const value = readString(source, mapping.keys)
      if (value !== undefined) advancedExtraBody[mapping.target] = value
      continue
    }
    if (mapping.kind === "string-list") {
      const value = normalizeStringList(
        firstDefined(...mapping.keys.map((key) => source[key]))
      )
      if (value.length > 0) advancedExtraBody[mapping.target] = value
      continue
    }
    if (mapping.kind === "record") {
      const value = normalizeLogitBias(
        firstDefined(...mapping.keys.map((key) => source[key]))
      )
      if (value !== undefined) advancedExtraBody[mapping.target] = value
    }
  }
  if (Object.keys(advancedExtraBody).length > 0) {
    settings.advanced_extra_body = advancedExtraBody
  }

  const memoryBlock = normalizeContextBlock(
    firstDefined(source.memory_block, source.memoryBlock, source.memoryTokens)
  )
  if (memoryBlock) {
    settings.memory_block = memoryBlock
  }

  const authorDepth = readNumber(source, ["author_note_depth", "authorNoteDepth"])
  const authorNote = normalizeAuthorNote(
    firstDefined(source.author_note, source.authorNote, source.authorNoteTokens),
    authorDepth
  )
  if (authorNote) {
    settings.author_note = authorNote
  }

  const worldInfo = normalizeWorldInfo(
    firstDefined(source.world_info, source.worldInfo)
  )
  if (worldInfo) {
    settings.world_info = worldInfo
  }

  return Object.keys(settings).length > 0 ? settings : undefined
}

const RECOGNIZED_INPUT_KEYS = new Set([
  "prompt",
  "text",
  "template",
  "selectedTemplate",
  "template_name",
  "templateName",
  "theme",
  "theme_name",
  "themeName",
  "chat_mode",
  "chatMode",
  "chatAPI",
  "useChatAPI",
  "enabledSamplers",
  "enabled_samplers",
  "openaiPresets",
  "openai_presets",
  "stop",
  "stoppingStrings",
  "memory_block",
  "memoryBlock",
  "memoryTokens",
  "author_note",
  "authorNote",
  "authorNoteTokens",
  "author_note_depth",
  "authorNoteDepth",
  "world_info",
  "worldInfo",
  "temperature",
  "top_p",
  "topP",
  "top_k",
  "topK",
  "max_tokens",
  "maxTokens",
  "maxPredictTokens",
  "presence_penalty",
  "presencePenalty",
  "frequency_penalty",
  "frequencyPenalty",
  "seed",
  "token_streaming",
  "tokenStreaming",
  "logprobs",
  "use_basic_stopping_mode",
  "useBasicStoppingMode",
  "basic_stopping_mode_type",
  "basicStoppingModeType",
  "top_logprobs",
  "topLogprobs",
  "model",
  "model_id",
  "modelId",
  "endpointModel",
  "endpoint",
  "endpointAPI",
  "endpointApi",
  "endpoint_api",
  "endpointAPIKey",
  "endpointApiKey",
  "endpoint_api_key",
  "apiKey",
  "api_key",
  "proxyEndpoint",
  "proxy_endpoint",
  "sessionEndpoint",
  "session_endpoint",
  "provider",
  "api_provider",
  "apiProvider",
  "endpointProvider"
])

for (const mapping of ADVANCED_PARAM_MAP) {
  for (const key of mapping.keys) {
    RECOGNIZED_INPUT_KEYS.add(key)
  }
}

export const parseImportedSessionPayload = (
  item: Record<string, unknown>
): Record<string, unknown> => {
  const parsedPayload = parseMaybeJsonValue(item.payload)
  if (isRecord(parsedPayload)) {
    return parsedPayload
  }
  const parsedPayloadJson = parseMaybeJsonValue(item.payload_json)
  if (isRecord(parsedPayloadJson)) {
    return parsedPayloadJson
  }

  const source = isRecord(item.session) ? item.session : item
  const parsedSource: Record<string, unknown> = {}
  for (const [key, rawValue] of Object.entries(source)) {
    parsedSource[key] = parseMaybeJsonValue(rawValue)
  }

  const payload: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(parsedSource)) {
    if (IMPORT_METADATA_KEYS.has(key) || RECOGNIZED_INPUT_KEYS.has(key)) continue
    payload[key] = value
  }

  const prompt = normalizePrompt(firstDefined(parsedSource.prompt, parsedSource.text))
  if (prompt !== undefined) {
    payload.prompt = prompt
  }

  const settings = buildSettings(parsedSource)
  if (settings) {
    payload.settings = settings
  }

  const templateName = readString(parsedSource, [
    "template_name",
    "templateName",
    "template",
    "selectedTemplate"
  ])
  if (templateName !== undefined) {
    payload.template_name = templateName.trim()
  }

  const themeName = readString(parsedSource, ["theme_name", "themeName", "theme"])
  if (themeName !== undefined) {
    payload.theme_name = themeName.trim()
  }

  const directChatMode = readBoolean(parsedSource, ["chat_mode", "chatMode"])
  const chatApiMode = readBoolean(parsedSource, ["chatAPI", "useChatAPI"])
  const chatMode =
    directChatMode === true || chatApiMode === true
      ? true
      : firstDefined(directChatMode, chatApiMode)
  if (chatMode !== undefined) {
    payload.chat_mode = chatMode
  }

  const modelHint = readModelHint(parsedSource)
  if (modelHint !== undefined) {
    payload.model = modelHint
  }

  const providerHint = readProviderHint(parsedSource)
  if (providerHint !== undefined) {
    payload.provider = providerHint
  }

  return payload
}

export const getImportedSessionModelHint = (
  payload: Record<string, unknown> | null | undefined
): string | null => {
  if (!isRecord(payload)) return null
  return readModelHint(payload) ?? null
}

export const getImportedSessionProviderHint = (
  payload: Record<string, unknown> | null | undefined
): string | null => {
  if (!isRecord(payload)) return null
  return readProviderHint(payload) ?? null
}

const toRecordList = (value: unknown): Record<string, unknown>[] => {
  if (Array.isArray(value)) {
    return value.filter((entry): entry is Record<string, unknown> => isRecord(entry))
  }
  return []
}

const toStoreRows = (value: unknown): Array<{ key: unknown; value: unknown }> => {
  if (!Array.isArray(value)) return []
  const out: Array<{ key: unknown; value: unknown }> = []
  for (const entry of value) {
    if (!isRecord(entry)) continue
    out.push({
      key: entry.key,
      value: entry.value
    })
  }
  return out
}

const resolveDbStoreRows = (
  root: Record<string, unknown>,
  storeName: string
): Array<{ key: unknown; value: unknown }> => {
  const direct = root[storeName]
  if (direct !== undefined) {
    return toStoreRows(direct)
  }
  const lower = storeName.toLowerCase()
  for (const [key, value] of Object.entries(root)) {
    if (key.toLowerCase() !== lower) continue
    return toStoreRows(value)
  }
  return []
}

const extractSessionsFromDatabaseExport = (
  root: Record<string, unknown>
): Record<string, unknown>[] => {
  const sessionRows = resolveDbStoreRows(root, "Sessions")
  if (sessionRows.length === 0) return []

  const nameRows = resolveDbStoreRows(root, "Names")
  const namesByKey = new Map<string, string>()
  for (const row of nameRows) {
    const key = String(row.key ?? "").trim()
    const name = typeof row.value === "string" ? row.value.trim() : ""
    if (!key || !name) continue
    namesByKey.set(key, name)
  }

  const out: Record<string, unknown>[] = []
  for (const row of sessionRows) {
    const key = String(row.key ?? "").trim()
    if (!key || key === "nextSessionId" || key === "selectedSessionId") {
      continue
    }
    if (!isRecord(row.value)) continue
    const name = namesByKey.get(key)
    const item: Record<string, unknown> = {
      ...row.value
    }
    if (name) {
      item.name = name
    }
    out.push(item)
  }
  return out
}

const isSessionLikeObject = (value: Record<string, unknown>): boolean => {
  const sessionKeys = [
    "prompt",
    "payload",
    "payload_json",
    "settings",
    "temperature",
    "top_p",
    "chatMode",
    "chat_mode",
    "template",
    "template_name"
  ]
  return sessionKeys.some((key) => Object.prototype.hasOwnProperty.call(value, key))
}

export const extractImportedSessionItems = (
  value: unknown
): Record<string, unknown>[] => {
  if (Array.isArray(value)) {
    return toRecordList(value)
  }
  if (!isRecord(value)) {
    return []
  }

  const dbExportSessions = extractSessionsFromDatabaseExport(value)
  if (dbExportSessions.length > 0) {
    return dbExportSessions
  }

  if (Array.isArray(value.sessions)) {
    return toRecordList(value.sessions)
  }
  if (isRecord(value.sessions)) {
    return Object.values(value.sessions).filter(
      (entry): entry is Record<string, unknown> => isRecord(entry)
    )
  }
  if (isRecord(value.session)) {
    return [value.session]
  }

  const values = Object.values(value)
  const recordValues = values.filter(
    (entry): entry is Record<string, unknown> => isRecord(entry)
  )
  if (
    recordValues.length > 0 &&
    recordValues.length === values.length &&
    !isSessionLikeObject(value)
  ) {
    return recordValues
  }

  return [value]
}
