import type { Prompt } from "@/db/dexie/types"
import type { Character } from "@/types/character"
import type { RagPinnedResult } from "@/utils/rag-format"
import type { PresetKey } from "./ParameterPresets"

export type StartupTemplatePromptSource =
  | "none"
  | "system-template"
  | "prompt-library"
  | "prompt-studio"

export type StartupTemplateBundle = {
  id: string
  name: string
  createdAt: number
  updatedAt: number
  selectedModel: string | null
  systemPrompt: string
  selectedSystemPromptId: string | null
  promptStudioPromptId: number | null
  promptTitle: string | null
  promptSource: StartupTemplatePromptSource
  presetKey: PresetKey
  character: Character | null
  ragPinnedResults: RagPinnedResult[]
}

export type StartupTemplateCreateInput = {
  name: string
  selectedModel: string | null
  systemPrompt: string
  selectedSystemPromptId?: string | null
  promptStudioPromptId?: number | null
  promptTitle?: string | null
  promptSource?: StartupTemplatePromptSource
  presetKey?: PresetKey
  character?: Character | null
  ragPinnedResults?: RagPinnedResult[]
}

export type StartupTemplatePromptResolution = {
  prompt: Prompt | null
  source: StartupTemplatePromptSource
  promptTitle: string | null
  promptStudioPromptId: number | null
}

const MAX_TEMPLATE_NAME_LENGTH = 80
const FALLBACK_TEMPLATE_NAME = "New startup template"

const nowTimestamp = () => Date.now()

const createTemplateId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `startup-template-${nowTimestamp()}-${Math.random().toString(16).slice(2)}`
}

const normalizePromptSource = (
  value: unknown
): StartupTemplatePromptSource => {
  if (
    value === "none" ||
    value === "system-template" ||
    value === "prompt-library" ||
    value === "prompt-studio"
  ) {
    return value
  }
  return "none"
}

const normalizePresetKey = (value: unknown): PresetKey => {
  if (
    value === "creative" ||
    value === "balanced" ||
    value === "precise" ||
    value === "custom"
  ) {
    return value
  }
  return "custom"
}

const normalizeString = (value: unknown): string =>
  typeof value === "string" ? value : ""

const normalizeNullableString = (value: unknown): string | null => {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

const normalizeRagPinnedResult = (value: unknown): RagPinnedResult | null => {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  const id = normalizeString(record.id).trim()
  const snippet = normalizeString(record.snippet).trim()
  if (!id || !snippet) return null

  return {
    id,
    snippet,
    title: normalizeNullableString(record.title) ?? undefined,
    source: normalizeNullableString(record.source) ?? undefined,
    url: normalizeNullableString(record.url) ?? undefined,
    type: normalizeNullableString(record.type) ?? undefined,
    mediaId:
      typeof record.mediaId === "number" && Number.isFinite(record.mediaId)
        ? record.mediaId
        : undefined
  }
}

const normalizeRagPinnedResults = (value: unknown): RagPinnedResult[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => normalizeRagPinnedResult(entry))
    .filter((entry): entry is RagPinnedResult => Boolean(entry))
    .slice(0, 12)
}

const normalizeCharacter = (value: unknown): Character | null => {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  const id = record.id
  if (!(typeof id === "string" || typeof id === "number")) {
    return null
  }
  return value as Character
}

export const sanitizeStartupTemplateName = (
  value: string,
  fallback = FALLBACK_TEMPLATE_NAME
): string => {
  const normalized = value.replace(/\s+/g, " ").trim()
  if (!normalized) return fallback
  if (normalized.length <= MAX_TEMPLATE_NAME_LENGTH) return normalized
  return normalized.slice(0, MAX_TEMPLATE_NAME_LENGTH).trim()
}

export const inferStartupTemplatePromptSource = (
  selectedPrompt: Prompt | null,
  hasSystemPromptContent: boolean
): StartupTemplatePromptSource => {
  if (selectedPrompt) {
    if (
      selectedPrompt.sourceSystem === "studio" ||
      selectedPrompt.studioPromptId != null ||
      selectedPrompt.serverId != null
    ) {
      return "prompt-studio"
    }
    return "prompt-library"
  }
  if (hasSystemPromptContent) {
    return "system-template"
  }
  return "none"
}

export const createStartupTemplateBundle = (
  input: StartupTemplateCreateInput,
  options?: {
    id?: string
    now?: number
  }
): StartupTemplateBundle => {
  const now = options?.now ?? nowTimestamp()
  return {
    id: options?.id ?? createTemplateId(),
    name: sanitizeStartupTemplateName(input.name),
    createdAt: now,
    updatedAt: now,
    selectedModel:
      typeof input.selectedModel === "string" && input.selectedModel.trim().length > 0
        ? input.selectedModel
        : null,
    systemPrompt: normalizeString(input.systemPrompt),
    selectedSystemPromptId: normalizeNullableString(input.selectedSystemPromptId),
    promptStudioPromptId:
      typeof input.promptStudioPromptId === "number" &&
      Number.isFinite(input.promptStudioPromptId)
        ? input.promptStudioPromptId
        : null,
    promptTitle: normalizeNullableString(input.promptTitle),
    promptSource: normalizePromptSource(input.promptSource),
    presetKey: normalizePresetKey(input.presetKey),
    character: normalizeCharacter(input.character),
    ragPinnedResults: normalizeRagPinnedResults(input.ragPinnedResults)
  }
}

export const normalizeStartupTemplateBundle = (
  value: unknown
): StartupTemplateBundle | null => {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  const id = normalizeNullableString(record.id)
  if (!id) return null

  const createdAt =
    typeof record.createdAt === "number" && Number.isFinite(record.createdAt)
      ? record.createdAt
      : nowTimestamp()
  const updatedAt =
    typeof record.updatedAt === "number" && Number.isFinite(record.updatedAt)
      ? record.updatedAt
      : createdAt

  return {
    id,
    name: sanitizeStartupTemplateName(normalizeString(record.name)),
    createdAt,
    updatedAt,
    selectedModel: normalizeNullableString(record.selectedModel),
    systemPrompt: normalizeString(record.systemPrompt),
    selectedSystemPromptId: normalizeNullableString(record.selectedSystemPromptId),
    promptStudioPromptId:
      typeof record.promptStudioPromptId === "number" &&
      Number.isFinite(record.promptStudioPromptId)
        ? record.promptStudioPromptId
        : null,
    promptTitle: normalizeNullableString(record.promptTitle),
    promptSource: normalizePromptSource(record.promptSource),
    presetKey: normalizePresetKey(record.presetKey),
    character: normalizeCharacter(record.character),
    ragPinnedResults: normalizeRagPinnedResults(record.ragPinnedResults)
  }
}

export const parseStartupTemplateBundles = (
  value: unknown
): StartupTemplateBundle[] => {
  let parsedValue = value
  if (typeof value === "string") {
    try {
      parsedValue = JSON.parse(value)
    } catch {
      return []
    }
  }
  if (!Array.isArray(parsedValue)) return []

  return parsedValue
    .map((entry) => normalizeStartupTemplateBundle(entry))
    .filter((entry): entry is StartupTemplateBundle => Boolean(entry))
    .sort((a, b) => b.updatedAt - a.updatedAt)
}

export const serializeStartupTemplateBundles = (
  bundles: StartupTemplateBundle[]
): string => JSON.stringify(bundles)

export const upsertStartupTemplateBundle = (
  existing: StartupTemplateBundle[],
  incoming: StartupTemplateBundle
): StartupTemplateBundle[] => {
  const next = existing.filter((entry) => entry.id !== incoming.id)
  return [incoming, ...next].sort((a, b) => b.updatedAt - a.updatedAt)
}

export const removeStartupTemplateBundle = (
  existing: StartupTemplateBundle[],
  id: string
): StartupTemplateBundle[] => existing.filter((entry) => entry.id !== id)

export const resolveStartupTemplatePrompt = (
  template: StartupTemplateBundle,
  prompts: Prompt[]
): StartupTemplatePromptResolution => {
  const byId = template.selectedSystemPromptId
    ? prompts.find((prompt) => prompt.id === template.selectedSystemPromptId) || null
    : null
  if (byId) {
    return {
      prompt: byId,
      source: inferStartupTemplatePromptSource(byId, byId.content.trim().length > 0),
      promptTitle: byId.title || template.promptTitle,
      promptStudioPromptId:
        byId.studioPromptId ?? byId.serverId ?? template.promptStudioPromptId
    }
  }

  const studioPromptId = template.promptStudioPromptId
  const byStudioId =
    studioPromptId == null
      ? null
      :
          prompts.find(
            (prompt) =>
              prompt.studioPromptId === studioPromptId ||
              prompt.serverId === studioPromptId
          ) || null

  if (byStudioId) {
    return {
      prompt: byStudioId,
      source: "prompt-studio",
      promptTitle: byStudioId.title || template.promptTitle,
      promptStudioPromptId: byStudioId.studioPromptId ?? byStudioId.serverId ?? studioPromptId
    }
  }

  return {
    prompt: null,
    source: normalizePromptSource(template.promptSource),
    promptTitle: template.promptTitle,
    promptStudioPromptId: studioPromptId
  }
}

export const describeStartupTemplatePrompt = (
  template: StartupTemplateBundle,
  prompts: Prompt[]
): string => {
  const resolution = resolveStartupTemplatePrompt(template, prompts)

  if (resolution.source === "prompt-studio") {
    return resolution.promptTitle
      ? `Prompt Studio: ${resolution.promptTitle}`
      : "Prompt Studio prompt"
  }
  if (resolution.source === "prompt-library") {
    return resolution.promptTitle
      ? `Prompt library: ${resolution.promptTitle}`
      : "Prompt library"
  }
  if (template.systemPrompt.trim().length > 0) {
    return "Custom system prompt"
  }
  return "No prompt"
}
