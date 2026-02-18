import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Button,
  Form,
  Input,
  Modal,
  Skeleton,
  Table,
  Tag,
  Tooltip,
  Select,
  Alert,
  Checkbox,
  Segmented,
  Pagination,
  Upload,
  Dropdown,
  InputNumber
} from "antd"
import type { InputRef, FormInstance } from "antd"
import React from "react"
import {
  tldwClient,
  type CharacterListSortBy,
  type CharacterListSortOrder,
  type ServerChatSummary
} from "@/services/tldw/TldwApiClient"
import { fetchChatModels } from "@/services/tldw-server"
import { History, Pen, Trash2, UserCircle2, MessageCircle, Copy, ChevronDown, ChevronUp, LayoutGrid, List, Keyboard, Download, CheckSquare, Square, Tags, X, MoreHorizontal } from "lucide-react"
import { CharacterPreview } from "./CharacterPreview"
import { CharacterGalleryCard, type GalleryCardDensity } from "./CharacterGalleryCard"
import { CharacterPreviewPopup } from "./CharacterPreviewPopup"
import { AvatarField, extractAvatarValues, createAvatarValue } from "./AvatarField"
import {
  applyTagOperationToTags,
  buildTagUsage,
  characterHasTag,
  parseCharacterTags,
  type CharacterTagOperation
} from "./tag-manager-utils"
import {
  filterCharactersForWorkspace,
  hasInlineConversationCount,
  paginateCharactersForWorkspace,
  sortCharactersForWorkspace
} from "./search-utils"
import { GenerateCharacterPanel, GenerationPreviewModal } from "./GenerateCharacterPanel"
import { GenerateFieldButton } from "./GenerateFieldButton"
import { useCharacterGeneration } from "@/hooks/useCharacterGeneration"
import { useFormDraft, formatDraftAge } from "@/hooks/useFormDraft"
import { useCharacterShortcuts } from "@/hooks/useCharacterShortcuts"
import { CHARACTER_TEMPLATES, type CharacterTemplate } from "@/data/character-templates"
import {
  CHARACTER_PROMPT_PRESETS,
  DEFAULT_CHARACTER_PROMPT_PRESET,
  isCharacterPromptPresetId,
  type CharacterPromptPresetId
} from "@/data/character-prompt-presets"
import type { GeneratedCharacter, CharacterField } from "@/services/character-generation"
import { useStorage } from "@plasmohq/storage/hook"
import { validateAndCreateImageDataUrl } from "@/utils/image-utils"
import { exportCharacterToJSON, exportCharacterToPNG, exportCharactersToJSON } from "@/utils/character-export"
import { useTranslation } from "react-i18next"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useNavigate } from "react-router-dom"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { focusComposer } from "@/hooks/useComposerFocus"
import { useStoreMessageOption } from "@/store/option"
import { shallow } from "zustand/shallow"
import { updatePageTitle } from "@/utils/update-page-title"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import {
  buildServerLogHint,
  sanitizeServerErrorMessage
} from "@/utils/server-error-message"

const MAX_NAME_LENGTH = 75
const MAX_DESCRIPTION_LENGTH = 65
const MAX_TAG_LENGTH = 20
const MAX_TAGS_DISPLAYED = 6
const DEFAULT_PAGE_SIZE = 10
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const
const PAGE_SIZE_STORAGE_KEY = "characters-page-size"
const GALLERY_DENSITY_KEY = "characters-gallery-density"
const SERVER_QUERY_ROLLOUT_FLAG_KEY = "ff_characters_server_query"
const TEMPLATE_CHOOSER_SEEN_KEY = "characters-template-chooser-seen"
const SYSTEM_PROMPT_EXAMPLE =
  CHARACTER_TEMPLATES.find((template) => template.id === "writing-assistant")
    ?.system_prompt ??
  "You are a skilled writing assistant who helps users improve drafts with clear, specific, and encouraging feedback."
type AdvancedSectionKey = "promptControl" | "generationSettings" | "metadata"
type AdvancedSectionState = Record<AdvancedSectionKey, boolean>
type CharacterListScope = "active" | "deleted"
const DEFAULT_ADVANCED_SECTION_STATE: AdvancedSectionState = {
  promptControl: true,
  generationSettings: false,
  metadata: false
}

const normalizePageSize = (value: unknown): number => {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseInt(value, 10)
        : Number.NaN
  return PAGE_SIZE_OPTIONS.includes(parsed as (typeof PAGE_SIZE_OPTIONS)[number])
    ? parsed
    : DEFAULT_PAGE_SIZE
}

type CharacterRecoveryTelemetryAction =
  | "delete"
  | "undo"
  | "restore"
  | "restore_failed"
  | "bulk_delete"
  | "bulk_undo"
  | "bulk_restore"
  | "bulk_restore_failed"

const emitCharacterRecoveryTelemetry = (
  action: CharacterRecoveryTelemetryAction,
  payload?: Record<string, unknown>
) => {
  if (typeof window === "undefined") return
  window.dispatchEvent(
    new CustomEvent("tldw:characters-recovery", {
      detail: {
        action,
        timestamp: new Date().toISOString(),
        ...(payload || {})
      }
    })
  )
}

type CharacterImportResult = {
  success: boolean
  fileName: string
  message: string
}

type CharacterQuickChatMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: number
}

type CharacterImportOptions = {
  allowImageOnly?: boolean
  suppressNotifications?: boolean
  invalidateOnSuccess?: boolean
}

type CharacterImportPreview = {
  id: string
  file: File
  fileName: string
  format: string
  name: string
  description: string
  tagCount: number
  fieldCount: number
  avatarUrl: string | null
  parseError: {
    key: string
    fallback: string
    values?: Record<string, string | number>
  } | null
}

const IMPORT_ALLOWED_EXTENSIONS = [
  ".png",
  ".webp",
  ".jpeg",
  ".jpg",
  ".json",
  ".yaml",
  ".yml",
  ".md",
  ".txt"
] as const
const IMPORT_ALLOWED_EXTENSION_SET = new Set<string>(IMPORT_ALLOWED_EXTENSIONS)
const IMPORT_UPLOAD_ACCEPT = IMPORT_ALLOWED_EXTENSIONS.join(",")
const IMPORT_IMAGE_EXTENSIONS = new Set([".png", ".webp", ".jpeg", ".jpg"])

const getImportFileExtension = (fileName: string): string => {
  const idx = fileName.lastIndexOf(".")
  return idx >= 0 ? fileName.slice(idx).toLowerCase() : ""
}

const buildDefaultImportName = (fileName: string): string => {
  const idx = fileName.lastIndexOf(".")
  const base = idx >= 0 ? fileName.slice(0, idx) : fileName
  return base.trim() || fileName
}

const isNonEmptyString = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0

const normalizeImportTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((tag) => String(tag).trim())
      .filter((tag) => tag.length > 0)
  }
  if (isNonEmptyString(value)) {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) {
        return parsed
          .map((tag) => String(tag).trim())
          .filter((tag) => tag.length > 0)
      }
    } catch {
      // fall through
    }
    return value
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0)
  }
  return []
}

const countPopulatedImportFields = (record: Record<string, unknown>): number =>
  Object.values(record).reduce((count, value) => {
    if (value == null) return count
    if (typeof value === "string") {
      return value.trim().length > 0 ? count + 1 : count
    }
    if (Array.isArray(value)) {
      return value.length > 0 ? count + 1 : count
    }
    if (typeof value === "object") {
      return Object.keys(value as Record<string, unknown>).length > 0
        ? count + 1
        : count
    }
    return count + 1
  }, 0)

const toPreviewAvatarUrl = (value: unknown): string | null => {
  if (!isNonEmptyString(value)) return null
  const trimmed = value.trim()
  if (trimmed.startsWith("data:image/")) return trimmed
  return `data:image/png;base64,${trimmed}`
}

const normalizeImportPayload = (rawPayload: unknown): Record<string, unknown> => {
  if (!rawPayload || typeof rawPayload !== "object" || Array.isArray(rawPayload)) {
    return {}
  }
  const record = rawPayload as Record<string, unknown>
  if (record.data && typeof record.data === "object" && !Array.isArray(record.data)) {
    return record.data as Record<string, unknown>
  }
  return record
}

const extractLooseTextCharacterFields = (text: string): Record<string, unknown> => {
  const fields: Record<string, unknown> = {}
  const nameMatch = text.match(/^\s*(?:name|char_name|character_name)\s*:\s*(.+)$/im)
  if (nameMatch?.[1]) {
    fields.name = nameMatch[1].trim()
  }

  const descriptionMatch = text.match(/^\s*description\s*:\s*(.+)$/im)
  if (descriptionMatch?.[1]) {
    fields.description = descriptionMatch[1].trim()
  }

  const inlineTagsMatch = text.match(/^\s*tags\s*:\s*\[(.+)\]\s*$/im)
  if (inlineTagsMatch?.[1]) {
    fields.tags = inlineTagsMatch[1]
      .split(",")
      .map((tag) => tag.trim().replace(/^["']|["']$/g, ""))
      .filter((tag) => tag.length > 0)
    return fields
  }

  const blockTagLines = text.match(
    /^\s*tags\s*:\s*$(?:\r?\n)([\s\S]*?)(?:\r?\n\s*\S.*:|$)/im
  )?.[1]
  if (blockTagLines) {
    const tags = blockTagLines
      .split(/\r?\n/)
      .map((line) => line.match(/^\s*-\s*(.+)$/)?.[1]?.trim())
      .filter((value): value is string => Boolean(value))
      .map((tag) => tag.replace(/^["']|["']$/g, ""))
    if (tags.length > 0) {
      fields.tags = tags
    }
  }

  return fields
}

const detectMalformedYamlPreview = (text: string): string | null => {
  const lines = text.split(/\r?\n/)

  for (const [lineIndex, rawLine] of lines.entries()) {
    const lineNumber = lineIndex + 1
    const trimmed = rawLine.trim()
    if (!trimmed || trimmed.startsWith("#")) continue

    if (rawLine.includes("\t")) {
      return `Line ${lineNumber}: tabs are not supported for indentation.`
    }

    const withoutComment = rawLine.replace(/\s+#.*$/, "")
    const openSquare = (withoutComment.match(/\[/g) || []).length
    const closeSquare = (withoutComment.match(/\]/g) || []).length
    if (openSquare !== closeSquare) {
      return `Line ${lineNumber}: inline list syntax is malformed.`
    }

    const openCurly = (withoutComment.match(/\{/g) || []).length
    const closeCurly = (withoutComment.match(/\}/g) || []).length
    if (openCurly !== closeCurly) {
      return `Line ${lineNumber}: inline object syntax is malformed.`
    }
  }

  return null
}

const parseCharacterImportPreview = async (
  file: File,
  index: number
): Promise<CharacterImportPreview> => {
  const extension = getImportFileExtension(file.name)
  const format = extension ? extension.slice(1).toUpperCase() : "FILE"
  const defaultName = buildDefaultImportName(file.name)
  if (!extension || !IMPORT_ALLOWED_EXTENSION_SET.has(extension)) {
    const allowed = IMPORT_ALLOWED_EXTENSIONS.join(", ")
    return {
      id: `${file.name}-${file.lastModified}-${index}`,
      file,
      fileName: file.name,
      format,
      name: defaultName,
      description: "",
      tagCount: 0,
      fieldCount: 0,
      avatarUrl: null,
      parseError: {
        key: "settings:manageCharacters.import.previewUnsupportedType",
        fallback:
          "Unsupported file type: {{extension}}. Supported formats: {{allowed}}",
        values: {
          extension: extension || "no extension",
          allowed
        }
      }
    }
  }

  if (IMPORT_IMAGE_EXTENSIONS.has(extension)) {
    const avatarUrl =
      typeof URL !== "undefined" && typeof URL.createObjectURL === "function"
        ? URL.createObjectURL(file)
        : null
    return {
      id: `${file.name}-${file.lastModified}-${index}`,
      file,
      fileName: file.name,
      format,
      name: defaultName,
      description: "",
      tagCount: 0,
      fieldCount: 0,
      avatarUrl,
      parseError: null
    }
  }

  let text = ""
  try {
    text = await file.text()
  } catch {
    return {
      id: `${file.name}-${file.lastModified}-${index}`,
      file,
      fileName: file.name,
      format,
      name: defaultName,
      description: "",
      tagCount: 0,
      fieldCount: 0,
      avatarUrl: null,
      parseError: {
        key: "settings:manageCharacters.import.previewReadError",
        fallback: "Unable to read file contents for preview."
      }
    }
  }

  let rawPayload: unknown = null
  if (extension === ".json") {
    try {
      rawPayload = JSON.parse(text)
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Invalid JSON"
      return {
        id: `${file.name}-${file.lastModified}-${index}`,
        file,
        fileName: file.name,
        format,
        name: defaultName,
        description: "",
        tagCount: 0,
        fieldCount: 0,
        avatarUrl: null,
        parseError: {
          key: "settings:manageCharacters.import.previewInvalidJson",
          fallback: "Invalid JSON syntax: {{message}}",
          values: { message }
        }
      }
    }
  } else if (extension === ".yaml" || extension === ".yml") {
    const yamlValidationError = detectMalformedYamlPreview(text)
    if (yamlValidationError) {
      return {
        id: `${file.name}-${file.lastModified}-${index}`,
        file,
        fileName: file.name,
        format,
        name: defaultName,
        description: "",
        tagCount: 0,
        fieldCount: 0,
        avatarUrl: null,
        parseError: {
          key: "settings:manageCharacters.import.previewInvalidYaml",
          fallback: "Malformed YAML content: {{message}}",
          values: { message: yamlValidationError }
        }
      }
    }
    const trimmed = text.trim()
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
      try {
        rawPayload = JSON.parse(trimmed)
      } catch {
        rawPayload = extractLooseTextCharacterFields(text)
      }
    } else {
      rawPayload = extractLooseTextCharacterFields(text)
    }
  } else {
    const trimmed = text.trim()
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
      try {
        rawPayload = JSON.parse(trimmed)
      } catch {
        rawPayload = extractLooseTextCharacterFields(text)
      }
    } else {
      rawPayload = extractLooseTextCharacterFields(text)
    }
  }

  const payload = normalizeImportPayload(rawPayload)
  const inferredName = isNonEmptyString(payload.name)
    ? payload.name.trim()
    : defaultName
  const description = isNonEmptyString(payload.description)
    ? payload.description.trim()
    : ""
  const tags = normalizeImportTags(payload.tags)
  const avatarUrl =
    toPreviewAvatarUrl(payload.image_base64) || toPreviewAvatarUrl(payload.avatar)
  const fieldCount = countPopulatedImportFields(payload)

  return {
    id: `${file.name}-${file.lastModified}-${index}`,
    file,
    fileName: file.name,
    format,
    name: inferredName,
    description,
    tagCount: tags.length,
    fieldCount,
    avatarUrl,
    parseError: null
  }
}

const toCharactersSortBy = (column: string | null): CharacterListSortBy => {
  switch (column) {
    case "creator":
      return "creator"
    case "createdAt":
      return "created_at"
    case "updatedAt":
      return "updated_at"
    case "conversations":
      return "conversation_count"
    case "name":
    default:
      return "name"
  }
}

const toCharactersSortOrder = (
  order: "ascend" | "descend" | null
): CharacterListSortOrder => (order === "descend" ? "desc" : "asc")

const truncateText = (value?: string, max?: number) => {
  if (!value) return ""
  if (!max || value.length <= max) return value
  return `${value.slice(0, max)}...`
}

const buildCharacterSelectionPayload = (record: any) => ({
  id: record.id || record.slug || record.name,
  name: record.name || record.title || record.slug,
  system_prompt:
    record.system_prompt ||
    record.systemPrompt ||
    record.instructions ||
    "",
  greeting:
    record.greeting ||
    record.first_message ||
    record.greet ||
    "",
  avatar_url:
    record.avatar_url ||
    validateAndCreateImageDataUrl(record.image_base64) ||
    ""
})

const makeQuickChatMessageId = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const resolveCharacterNumericId = (record: any): number | null => {
  const raw = record?.id ?? record?.character_id ?? record?.characterId
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null
  }
  return parsed
}

const normalizeAlternateGreetings = (value: any): string[] => {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.map((v) => String(v)).filter((v) => v.trim().length > 0)
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v)).filter((v) => v.trim().length > 0)
      }
    } catch {
      // fall through to newline splitting
    }
    return value
      .split(/\r?\n|;/)
      .map((v) => v.trim())
      .filter((v) => v.length > 0)
  }
  return []
}

const isPlainObject = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === "object" && !Array.isArray(value)

const parseExtensionsObject = (
  value: unknown
): Record<string, any> | null => {
  if (!value) return {}
  if (isPlainObject(value)) return { ...value }
  if (typeof value === "string") {
    if (!value.trim()) return {}
    try {
      const parsed = JSON.parse(value)
      return isPlainObject(parsed) ? { ...parsed } : {}
    } catch {
      return null
    }
  }
  return {}
}

const normalizePromptPresetId = (
  value: unknown
): CharacterPromptPresetId =>
  isCharacterPromptPresetId(value)
    ? value
    : DEFAULT_CHARACTER_PROMPT_PRESET

const readPromptPresetFromExtensions = (
  extensions: unknown
): CharacterPromptPresetId => {
  const parsed = parseExtensionsObject(extensions)
  if (!parsed) return DEFAULT_CHARACTER_PROMPT_PRESET
  const tldw = parsed.tldw
  const nestedPreset = isPlainObject(tldw)
    ? tldw.prompt_preset || tldw.promptPreset
    : undefined
  const topPreset = parsed.prompt_preset || parsed.promptPreset
  return normalizePromptPresetId(nestedPreset || topPreset)
}

const readDefaultAuthorNoteFromExtensions = (extensions: unknown): string => {
  const parsed = parseExtensionsObject(extensions)
  if (!parsed) return ""

  const tldw = isPlainObject(parsed.tldw) ? parsed.tldw : undefined
  const candidates: unknown[] = [
    parsed.default_author_note,
    parsed.defaultAuthorNote,
    parsed.author_note,
    parsed.authorNote,
    parsed.memory_note,
    parsed.memoryNote,
    tldw?.default_author_note,
    tldw?.defaultAuthorNote,
    tldw?.author_note,
    tldw?.authorNote,
    tldw?.memory_note,
    tldw?.memoryNote
  ]

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }
  return ""
}

const readDefaultAuthorNoteFromRecord = (record: any): string => {
  const directCandidates: unknown[] = [
    record?.default_author_note,
    record?.defaultAuthorNote,
    record?.author_note,
    record?.authorNote,
    record?.memory_note,
    record?.memoryNote
  ]
  for (const candidate of directCandidates) {
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }
  return readDefaultAuthorNoteFromExtensions(record?.extensions)
}

type CharacterGenerationSettings = {
  temperature?: number
  top_p?: number
  repetition_penalty?: number
  stop?: string[]
}

const parseGenerationNumber = (
  value: unknown,
  minimum: number,
  maximum: number
): number | undefined => {
  if (typeof value === "boolean" || value === null || value === undefined) {
    return undefined
  }
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number.parseFloat(value)
        : Number.NaN
  if (!Number.isFinite(parsed)) return undefined
  if (parsed < minimum || parsed > maximum) return undefined
  return parsed
}

const normalizeGenerationStopStrings = (value: unknown): string[] | undefined => {
  if (value === null || value === undefined) return undefined
  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
      .filter((entry) => entry.length > 0)
    return normalized.length > 0 ? normalized : undefined
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return undefined
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        const normalized = parsed
          .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
          .filter((entry) => entry.length > 0)
        if (normalized.length > 0) return normalized
      }
    } catch {
      // fall back to simple splitting
    }
    const normalized = trimmed
      .split(/\r?\n|;/)
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0)
    return normalized.length > 0 ? normalized : undefined
  }
  return undefined
}

const resolveGenerationSetting = <T,>(
  containers: Record<string, any>[],
  keys: string[],
  parser: (value: unknown) => T | undefined
): T | undefined => {
  for (const container of containers) {
    for (const key of keys) {
      if (!(key in container)) continue
      const parsed = parser(container[key])
      if (typeof parsed !== "undefined") {
        return parsed
      }
    }
  }
  return undefined
}

const readGenerationSettingsFromRecord = (
  record: any
): CharacterGenerationSettings => {
  const parsed = parseExtensionsObject(record?.extensions)
  const parsedObject = parsed && isPlainObject(parsed) ? parsed : undefined
  const tldw = parsedObject && isPlainObject(parsedObject.tldw)
    ? parsedObject.tldw
    : undefined
  const generation = tldw && isPlainObject(tldw.generation)
    ? tldw.generation
    : undefined

  const containers: Record<string, any>[] = []
  if (generation) containers.push(generation)
  if (parsedObject) containers.push(parsedObject)
  if (isPlainObject(record)) containers.push(record)

  const temperature = resolveGenerationSetting(
    containers,
    ["temperature", "generation_temperature"],
    (value) => parseGenerationNumber(value, 0, 2)
  )
  const topP = resolveGenerationSetting(
    containers,
    ["top_p", "topP", "generation_top_p"],
    (value) => parseGenerationNumber(value, 0, 1)
  )
  const repetitionPenalty = resolveGenerationSetting(
    containers,
    ["repetition_penalty", "repetitionPenalty", "generation_repetition_penalty"],
    (value) => parseGenerationNumber(value, 0, 3)
  )
  const stop = resolveGenerationSetting(
    containers,
    [
      "stop",
      "stop_strings",
      "stopStrings",
      "stop_sequences",
      "stopSequences",
      "generation_stop_strings"
    ],
    normalizeGenerationStopStrings
  )

  const settings: CharacterGenerationSettings = {}
  if (typeof temperature !== "undefined") settings.temperature = temperature
  if (typeof topP !== "undefined") settings.top_p = topP
  if (typeof repetitionPenalty !== "undefined") {
    settings.repetition_penalty = repetitionPenalty
  }
  if (stop && stop.length > 0) settings.stop = stop
  return settings
}

const readGenerationSettingsFromFormValues = (
  values: Record<string, any>
): CharacterGenerationSettings => {
  const settings: CharacterGenerationSettings = {}
  const temperature = parseGenerationNumber(values.generation_temperature, 0, 2)
  const topP = parseGenerationNumber(values.generation_top_p, 0, 1)
  const repetitionPenalty = parseGenerationNumber(
    values.generation_repetition_penalty,
    0,
    3
  )
  const stop = normalizeGenerationStopStrings(values.generation_stop_strings)

  if (typeof temperature !== "undefined") settings.temperature = temperature
  if (typeof topP !== "undefined") settings.top_p = topP
  if (typeof repetitionPenalty !== "undefined") {
    settings.repetition_penalty = repetitionPenalty
  }
  if (stop && stop.length > 0) settings.stop = stop
  return settings
}

const removeLegacyGenerationKeys = (target: Record<string, any>) => {
  delete target.generation
  delete target.top_p
  delete target.topP
  delete target.repetition_penalty
  delete target.repetitionPenalty
  delete target.stop_strings
  delete target.stopStrings
  delete target.stop_sequences
  delete target.stopSequences
}

const applyCharacterMetadataToExtensions = (
  rawExtensions: unknown,
  params: {
    preset: CharacterPromptPresetId
    defaultAuthorNote?: unknown
    generation?: CharacterGenerationSettings
  }
): Record<string, any> | string | undefined => {
  const parsed = parseExtensionsObject(rawExtensions)
  const hadRawString =
    typeof rawExtensions === "string" &&
    rawExtensions.trim().length > 0 &&
    parsed === null

  if (hadRawString) {
    return rawExtensions as string
  }

  let next: Record<string, any> = parsed && parsed !== null ? { ...parsed } : {}

  const tldw = isPlainObject(next.tldw) ? { ...next.tldw } : {}

  if (params.preset === DEFAULT_CHARACTER_PROMPT_PRESET) {
    delete tldw.prompt_preset
    delete tldw.promptPreset
    delete next.prompt_preset
    delete next.promptPreset
  } else {
    tldw.prompt_preset = params.preset
    delete next.prompt_preset
    delete next.promptPreset
  }

  const defaultAuthorNote =
    typeof params.defaultAuthorNote === "string"
      ? params.defaultAuthorNote.trim()
      : ""
  if (defaultAuthorNote) {
    next.default_author_note = defaultAuthorNote
    delete next.defaultAuthorNote
  } else {
    delete next.default_author_note
    delete next.defaultAuthorNote
  }

  const generation = params.generation || {}
  const normalizedGeneration: Record<string, any> = {}
  const normalizedTemp = parseGenerationNumber(generation.temperature, 0, 2)
  const normalizedTopP = parseGenerationNumber(generation.top_p, 0, 1)
  const normalizedRepetition = parseGenerationNumber(
    generation.repetition_penalty,
    0,
    3
  )
  const normalizedStop = normalizeGenerationStopStrings(generation.stop)

  if (typeof normalizedTemp !== "undefined") {
    normalizedGeneration.temperature = normalizedTemp
  }
  if (typeof normalizedTopP !== "undefined") {
    normalizedGeneration.top_p = normalizedTopP
  }
  if (typeof normalizedRepetition !== "undefined") {
    normalizedGeneration.repetition_penalty = normalizedRepetition
  }
  if (normalizedStop && normalizedStop.length > 0) {
    normalizedGeneration.stop = normalizedStop
  }

  removeLegacyGenerationKeys(next)
  if (Object.keys(normalizedGeneration).length > 0) {
    tldw.generation = normalizedGeneration
  } else {
    delete tldw.generation
  }

  if (Object.keys(tldw).length > 0) {
    next.tldw = tldw
  } else {
    delete next.tldw
  }

  if (Object.keys(next).length > 0) {
    return next
  }

  return undefined
}

const hasAdvancedData = (record: any, extensionsValue: string): boolean => {
  const normalizedRecord = {
    ...record,
    extensions: record?.extensions ?? extensionsValue
  }
  const defaultAuthorNote = readDefaultAuthorNoteFromRecord(normalizedRecord)
  const generationSettings = readGenerationSettingsFromRecord(normalizedRecord)
  const hasGenerationSettings =
    typeof generationSettings.temperature !== "undefined" ||
    typeof generationSettings.top_p !== "undefined" ||
    typeof generationSettings.repetition_penalty !== "undefined" ||
    (Array.isArray(generationSettings.stop) &&
      generationSettings.stop.length > 0)
  return !!(
    record.personality ||
    record.scenario ||
    record.post_history_instructions ||
    record.message_example ||
    record.creator_notes ||
    (record.alternate_greetings && record.alternate_greetings.length > 0) ||
    record.creator ||
    record.character_version ||
    hasGenerationSettings ||
    defaultAuthorNote ||
    extensionsValue
  )
}

const buildCharacterPayload = (values: any): Record<string, any> => {
  const payload: Record<string, any> = {
    name: values.name,
    description: values.description,
    personality: values.personality,
    scenario: values.scenario,
    system_prompt: values.system_prompt,
    post_history_instructions: values.post_history_instructions,
    first_message: values.greeting || values.first_message,
    message_example: values.message_example,
    creator_notes: values.creator_notes,
    tags: Array.isArray(values.tags)
      ? values.tags.filter((tag: string) => tag && tag.trim().length > 0)
      : values.tags,
    alternate_greetings: Array.isArray(values.alternate_greetings)
      ? values.alternate_greetings.filter((g: string) => g && g.trim().length > 0)
      : values.alternate_greetings,
    creator: values.creator,
    character_version: values.character_version
  }

  // Extract avatar values from unified avatar field
  if (values.avatar) {
    const avatarValues = extractAvatarValues(values.avatar)
    if (avatarValues.avatar_url) {
      payload.avatar_url = avatarValues.avatar_url
    }
    if (avatarValues.image_base64) {
      payload.image_base64 = avatarValues.image_base64
    }
  } else {
    // Fallback for legacy form structure
    if (values.avatar_url) {
      payload.avatar_url = values.avatar_url
    }
    if (values.image_base64) {
      payload.image_base64 = values.image_base64
    }
  }

  // Keep compatibility with mock server / older deployments
  if (values.greeting) {
    payload.greeting = values.greeting
  }

  Object.keys(payload).forEach((key) => {
    if (key === "extensions") return
    const v = payload[key]
    if (
      typeof v === "undefined" ||
      v === null ||
      (typeof v === "string" && v.trim().length === 0) ||
      (Array.isArray(v) && v.length === 0)
    ) {
      delete payload[key]
    }
  })

  const resolvedPreset = normalizePromptPresetId(values.prompt_preset)
  const generationSettings = readGenerationSettingsFromFormValues(values)
  const mergedExtensions = applyCharacterMetadataToExtensions(values.extensions, {
    preset: resolvedPreset,
    defaultAuthorNote: values.default_author_note,
    generation: generationSettings
  })
  if (typeof mergedExtensions !== "undefined") {
    payload.extensions = mergedExtensions
  }

  return payload
}

type CharactersManagerProps = {
  forwardedNewButtonRef?: React.RefObject<HTMLButtonElement | null>
  autoOpenCreate?: boolean
}

type SharedCharacterFormProps = {
  form: FormInstance
  mode: "create" | "edit"
  initialValues?: Record<string, any>
  isSubmitting: boolean
  submitButtonClassName?: string
  submitPendingLabel: string
  submitIdleLabel: string
  showPreview: boolean
  onTogglePreview: () => void
  onValuesChange: (allValues: Record<string, any>) => void
  onFinish: (values: Record<string, any>) => void
}

export const CharactersManager: React.FC<CharactersManagerProps> = ({
  forwardedNewButtonRef,
  autoOpenCreate = false
}) => {
  const { t } = useTranslation(["settings", "common"])
  const promptPresetOptions = React.useMemo(
    () =>
      CHARACTER_PROMPT_PRESETS.map((preset) => ({
        value: preset.id,
        label: t(
          `settings:manageCharacters.promptPresets.${preset.id}.label`,
          { defaultValue: preset.label }
        )
      })),
    [t]
  )
  const qc = useQueryClient()
  const navigate = useNavigate()
  const notification = useAntdNotification()
  const confirmDanger = useConfirmDanger()
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [editId, setEditId] = React.useState<string | null>(null)
  const [editVersion, setEditVersion] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [, setSelectedCharacter] = useSelectedCharacter<any>(null)
  const newButtonRef = React.useRef<HTMLButtonElement | null>(null)
  const lastEditTriggerRef = React.useRef<HTMLButtonElement | null>(null)
  const importButtonContainerRef = React.useRef<HTMLDivElement | null>(null)
  const createNameRef = React.useRef<InputRef>(null)
  const editNameRef = React.useRef<InputRef>(null)
  const searchInputRef = React.useRef<InputRef>(null)
  const [searchTerm, setSearchTerm] = React.useState("")
  const [filterTags, setFilterTags] = React.useState<string[]>([])
  const [matchAllTags, setMatchAllTags] = React.useState(false)
  const [creatorFilter, setCreatorFilter] = React.useState<string | undefined>(undefined)
  const [hasConversationsOnly, setHasConversationsOnly] = React.useState(false)
  const [showEditAdvanced, setShowEditAdvanced] = React.useState(false)
  const [showCreateAdvanced, setShowCreateAdvanced] = React.useState(false)
  const [createAdvancedSections, setCreateAdvancedSections] = React.useState<AdvancedSectionState>(
    () => ({ ...DEFAULT_ADVANCED_SECTION_STATE })
  )
  const [editAdvancedSections, setEditAdvancedSections] = React.useState<AdvancedSectionState>(
    () => ({ ...DEFAULT_ADVANCED_SECTION_STATE })
  )
  const [conversationsOpen, setConversationsOpen] = React.useState(false)
  const [conversationCharacter, setConversationCharacter] = React.useState<any | null>(null)
  const [characterChats, setCharacterChats] = React.useState<ServerChatSummary[]>([])
  const [chatsError, setChatsError] = React.useState<string | null>(null)
  const [loadingChats, setLoadingChats] = React.useState(false)
  const [resumingChatId, setResumingChatId] = React.useState<string | null>(null)
  const [quickChatCharacter, setQuickChatCharacter] = React.useState<any | null>(null)
  const [quickChatMessages, setQuickChatMessages] = React.useState<CharacterQuickChatMessage[]>([])
  const [quickChatDraft, setQuickChatDraft] = React.useState("")
  const [quickChatModelOverride, setQuickChatModelOverride] = React.useState<string | null>(null)
  const [quickChatSessionId, setQuickChatSessionId] = React.useState<string | null>(null)
  const [quickChatSending, setQuickChatSending] = React.useState(false)
  const [quickChatError, setQuickChatError] = React.useState<string | null>(null)
  const [createFormDirty, setCreateFormDirty] = React.useState(false)
  const [editFormDirty, setEditFormDirty] = React.useState(false)
  const [showCreateSystemPromptExample, setShowCreateSystemPromptExample] = React.useState(false)
  const [showEditSystemPromptExample, setShowEditSystemPromptExample] = React.useState(false)
  const [debouncedSearchTerm, setDebouncedSearchTerm] = React.useState("")
  const searchDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const [showCreatePreview, setShowCreatePreview] = React.useState(true)
  const [showEditPreview, setShowEditPreview] = React.useState(true)
  const autoOpenCreateHandledRef = React.useRef(false)
  const [viewMode, setViewMode] = React.useState<'table' | 'gallery'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('characters-view-mode')
      return saved === 'gallery' ? 'gallery' : 'table'
    }
    return 'table'
  })
  const [characterListScope, setCharacterListScope] = React.useState<CharacterListScope>("active")
  const [galleryDensity, setGalleryDensity] = React.useState<GalleryCardDensity>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(GALLERY_DENSITY_KEY)
      return saved === "compact" ? "compact" : "rich"
    }
    return "rich"
  })
  const [sortColumn, setSortColumn] = React.useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('characters-sort-column')
    }
    return null
  })
  const [sortOrder, setSortOrder] = React.useState<'ascend' | 'descend' | null>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('characters-sort-order')
      return saved === 'ascend' || saved === 'descend' ? saved : null
    }
    return null
  })
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState<number>(() => {
    if (typeof window !== "undefined") {
      return normalizePageSize(localStorage.getItem(PAGE_SIZE_STORAGE_KEY))
    }
    return DEFAULT_PAGE_SIZE
  })
  const [importing, setImporting] = React.useState(false)
  const [importPreviewOpen, setImportPreviewOpen] = React.useState(false)
  const [importPreviewLoading, setImportPreviewLoading] = React.useState(false)
  const [importPreviewItems, setImportPreviewItems] = React.useState<CharacterImportPreview[]>([])
  const [previewCharacter, setPreviewCharacter] = React.useState<any | null>(null)
  const crossNavigationContext = React.useMemo(
    () => {
      if (typeof window === "undefined") {
        return {
          launchedFromWorldBooks: false,
          focusCharacterId: "",
          focusWorldBookId: null as number | null
        }
      }
      const params = new URLSearchParams(window.location.search)
      const focusWorldBookIdRaw = params.get("focusWorldBookId")
      const parsedFocusWorldBookId = Number(focusWorldBookIdRaw)
      return {
        launchedFromWorldBooks: params.get("from") === "world-books",
        focusCharacterId: params.get("focusCharacterId") || "",
        focusWorldBookId:
          Number.isFinite(parsedFocusWorldBookId) && parsedFocusWorldBookId > 0
            ? parsedFocusWorldBookId
            : null
      }
    },
    []
  )
  const hasHandledFocusCharacterRef = React.useRef(false)
  const previewCharacterId = React.useMemo(() => {
    const parsed = Number(previewCharacter?.id)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null
  }, [previewCharacter?.id])

  // Inline editing state (M1)
  const [inlineEdit, setInlineEdit] = React.useState<{
    id: string
    field: 'name' | 'description'
    value: string
    originalValue: string
  } | null>(null)
  const inlineEditInputRef = React.useRef<InputRef>(null)
  const inlineEditTriggerRef = React.useRef<HTMLElement | null>(null)
  const inlineEditFocusKeyRef = React.useRef<string | null>(null)

  const restoreInlineEditFocus = React.useCallback(() => {
    setTimeout(() => {
      const focusKey = inlineEditFocusKeyRef.current
      if (focusKey) {
        const target = document.querySelector<HTMLElement>(
          `[data-inline-edit-key=\"${focusKey}\"]`
        )
        if (target) {
          target.focus()
          return
        }
      }
      inlineEditTriggerRef.current?.focus()
    }, 0)
  }, [])

  // Bulk operations state (M5)
  const [selectedCharacterIds, setSelectedCharacterIds] = React.useState<Set<string>>(new Set())
  const [bulkTagModalOpen, setBulkTagModalOpen] = React.useState(false)
  const [bulkTagsToAdd, setBulkTagsToAdd] = React.useState<string[]>([])
  const [bulkOperationLoading, setBulkOperationLoading] = React.useState(false)
  const [tagManagerOpen, setTagManagerOpen] = React.useState(false)
  const [tagManagerLoading, setTagManagerLoading] = React.useState(false)
  const [tagManagerSubmitting, setTagManagerSubmitting] = React.useState(false)
  const [tagManagerCharacters, setTagManagerCharacters] = React.useState<any[]>([])
  const [tagManagerOperation, setTagManagerOperation] = React.useState<CharacterTagOperation>("rename")
  const [tagManagerSourceTag, setTagManagerSourceTag] = React.useState<string | undefined>(undefined)
  const [tagManagerTargetTag, setTagManagerTargetTag] = React.useState("")

  // Character generation state
  const {
    isGenerating,
    generatingField,
    error: generationError,
    generateFullCharacter,
    generateField,
    cancel: cancelGeneration,
    clearError: clearGenerationError
  } = useCharacterGeneration()
  const [selectedGenModel] = useStorage<string | null>("characterGenModel", null)
  const [selectedChatModel] = useStorage<string | null>("selectedModel", null)
  const [serverQueryRolloutFlag] = useStorage<boolean | null>(
    SERVER_QUERY_ROLLOUT_FLAG_KEY,
    true
  )
  const isServerQueryRolloutEnabled = serverQueryRolloutFlag !== false

  // Fetch models to get provider for selected model
  const { data: generationModels } = useQuery<Array<{ model: string; provider?: string }>>({
    queryKey: ["getModelsForFieldGeneration"],
    queryFn: () => fetchChatModels({ returnEmpty: true }),
    staleTime: 5 * 60 * 1000 // 5 minutes
  })

  // Get the provider for the selected generation model
  const selectedGenModelProvider = React.useMemo(() => {
    if (!selectedGenModel || !generationModels) return undefined
    const modelData = generationModels.find((m) => m.model === selectedGenModel)
    return modelData?.provider
  }, [selectedGenModel, generationModels])

  const quickChatModelOptions = React.useMemo(
    () =>
      (generationModels || [])
        .filter((model) => typeof model.model === "string" && model.model.trim())
        .map((model) => {
          const modelName = model.model.trim()
          return {
            value: modelName,
            label: model.provider
              ? `${modelName} (${model.provider})`
              : modelName
          }
        }),
    [generationModels]
  )

  const activeQuickChatModel =
    quickChatModelOverride ||
    selectedChatModel ||
    quickChatModelOptions[0]?.value ||
    null

  const [generationPreviewData, setGenerationPreviewData] = React.useState<GeneratedCharacter | null>(null)
  const [generationPreviewField, setGenerationPreviewField] = React.useState<string | null>(null)
  const [generationPreviewOpen, setGenerationPreviewOpen] = React.useState(false)
  const [generationTargetForm, setGenerationTargetForm] = React.useState<'create' | 'edit'>('create')

  // Template selection state
  const [hasSeenTemplateChooser, setHasSeenTemplateChooser] = React.useState(() => {
    if (typeof window === "undefined") return false
    return localStorage.getItem(TEMPLATE_CHOOSER_SEEN_KEY) === "true"
  })
  const [showTemplates, setShowTemplates] = React.useState(() => {
    if (typeof window === "undefined") return true
    return localStorage.getItem(TEMPLATE_CHOOSER_SEEN_KEY) !== "true"
  })

  // Form draft autosave (H4)
  const {
    hasDraft: hasCreateDraft,
    draftData: createDraftData,
    saveDraft: saveCreateDraft,
    clearDraft: clearCreateDraft,
    applyDraft: applyCreateDraft,
    dismissDraft: dismissCreateDraft,
    lastSaved: createLastSaved
  } = useFormDraft<Record<string, any>>({
    storageKey: 'character-form-draft-create',
    formType: 'create',
    autoSaveInterval: 30000
  })

  const {
    hasDraft: hasEditDraft,
    draftData: editDraftData,
    saveDraft: saveEditDraft,
    clearDraft: clearEditDraft,
    applyDraft: applyEditDraft,
    dismissDraft: dismissEditDraft,
    lastSaved: editLastSaved
  } = useFormDraft<Record<string, any>>({
    storageKey: 'character-form-draft-edit',
    formType: 'edit',
    editId: editId ?? undefined,
    autoSaveInterval: 30000
  })

  const markTemplateChooserSeen = React.useCallback(() => {
    setHasSeenTemplateChooser(true)
    if (typeof window !== "undefined") {
      localStorage.setItem(TEMPLATE_CHOOSER_SEEN_KEY, "true")
    }
  }, [])

  const openCreateModal = React.useCallback(() => {
    if (!hasSeenTemplateChooser) {
      setShowTemplates(true)
      markTemplateChooserSeen()
    }
    setOpen(true)
  }, [hasSeenTemplateChooser, markTemplateChooserSeen])

  const triggerImportPicker = React.useCallback(() => {
    const uploadButton =
      importButtonContainerRef.current?.querySelector<HTMLButtonElement>("button")
    uploadButton?.click()
  }, [])

  const applyTemplateToCreateForm = React.useCallback(
    (template: CharacterTemplate) => {
      createForm.setFieldsValue({
        name: template.name,
        description: template.description,
        system_prompt: template.system_prompt,
        greeting: template.greeting,
        tags: template.tags
      })
      setCreateFormDirty(true)
      setShowTemplates(false)
      markTemplateChooserSeen()
      setOpen(true)
      notification.info({
        message: t("settings:manageCharacters.templates.applied", {
          defaultValue: "Template applied"
        }),
        description: t("settings:manageCharacters.templates.appliedDesc", {
          defaultValue: "You can customize all fields before saving."
        })
      })
    },
    [createForm, markTemplateChooserSeen, notification, t]
  )

  const applySystemPromptExample = React.useCallback(
    (mode: "create" | "edit") => {
      const targetForm = mode === "create" ? createForm : editForm
      const currentValue = String(targetForm.getFieldValue("system_prompt") ?? "").trim()
      const shouldConfirmOverwrite =
        currentValue.length > 0 && currentValue !== SYSTEM_PROMPT_EXAMPLE

      const apply = () => {
        targetForm.setFieldValue("system_prompt", SYSTEM_PROMPT_EXAMPLE)
        if (mode === "create") {
          setCreateFormDirty(true)
          setShowCreateSystemPromptExample(false)
        } else {
          setEditFormDirty(true)
          setShowEditSystemPromptExample(false)
        }
      }

      if (!shouldConfirmOverwrite) {
        apply()
        return
      }

      Modal.confirm({
        title: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.title", {
          defaultValue: "Replace current system prompt?"
        }),
        content: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.content", {
          defaultValue:
            "This will replace your current system prompt with the Writing Assistant example."
        }),
        okText: t("settings:manageCharacters.form.systemPrompt.exampleOverwrite.confirm", {
          defaultValue: "Replace"
        }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" }),
        onOk: apply
      })
    },
    [createForm, editForm, t]
  )

  const closeQuickChat = React.useCallback(async (options?: { preserveSession?: boolean }) => {
    const chatIdToDelete = quickChatSessionId
    const shouldDeleteSession =
      Boolean(chatIdToDelete) && options?.preserveSession !== true

    setQuickChatCharacter(null)
    setQuickChatMessages([])
    setQuickChatDraft("")
    setQuickChatSending(false)
    setQuickChatError(null)
    setQuickChatSessionId(null)

    if (shouldDeleteSession && chatIdToDelete) {
      try {
        await tldwClient.deleteChat(chatIdToDelete, { hardDelete: true })
      } catch {
        // Best-effort cleanup of ephemeral quick-chat session.
      }
    }
  }, [quickChatSessionId])

  // Keyboard shortcuts (H1)
  const modalOpen =
    open ||
    openEdit ||
    conversationsOpen ||
    generationPreviewOpen ||
    Boolean(quickChatCharacter)
  useCharacterShortcuts({
    modalOpen,
    onNewCharacter: () => {
      if (!modalOpen) openCreateModal()
    },
    onFocusSearch: () => {
      searchInputRef.current?.focus()
    },
    onCloseModal: () => {
      if (generationPreviewOpen) {
        setGenerationPreviewOpen(false)
      } else if (conversationsOpen) {
        setConversationsOpen(false)
      } else if (quickChatCharacter) {
        void closeQuickChat()
      } else if (openEdit) {
        setOpenEdit(false)
        setShowEditSystemPromptExample(false)
      } else if (open) {
        setOpen(false)
        setShowCreateSystemPromptExample(false)
      }
    },
    onTableView: () => setViewMode("table"),
    onGalleryView: () => setViewMode("gallery"),
    enabled: true
  })

  const shortcutHelpItems = React.useMemo(
    () => [
      {
        id: "new",
        keys: ["N"],
        label: t("settings:manageCharacters.shortcuts.new", {
          defaultValue: "New character"
        })
      },
      {
        id: "search",
        keys: ["/"],
        label: t("settings:manageCharacters.shortcuts.search", {
          defaultValue: "Focus search"
        })
      },
      {
        id: "table",
        keys: ["G", "T"],
        label: t("settings:manageCharacters.shortcuts.tableView", {
          defaultValue: "Table view"
        })
      },
      {
        id: "gallery",
        keys: ["G", "G"],
        label: t("settings:manageCharacters.shortcuts.galleryView", {
          defaultValue: "Gallery view"
        })
      },
      {
        id: "close",
        keys: ["Esc"],
        label: t("settings:manageCharacters.shortcuts.close", {
          defaultValue: "Close modal"
        })
      }
    ],
    [t]
  )

  const shortcutSummaryText = React.useMemo(
    () =>
      shortcutHelpItems
        .map((item) => `${item.keys.join(" ")} ${item.label}`)
        .join(". "),
    [shortcutHelpItems]
  )

  // Helper to get current form values as GeneratedCharacter
  const getFormFieldsAsCharacter = (form: FormInstance): Partial<GeneratedCharacter> => {
    const values = form.getFieldsValue()
    return {
      name: values.name,
      description: values.description,
      personality: values.personality,
      scenario: values.scenario,
      system_prompt: values.system_prompt,
      first_message: values.greeting || values.first_message,
      message_example: values.message_example,
      creator_notes: values.creator_notes,
      tags: values.tags,
      alternate_greetings: values.alternate_greetings
    }
  }

  // Handle full character generation
  const handleGenerateFullCharacter = async (concept: string, model: string, apiProvider?: string) => {
    const result = await generateFullCharacter(concept, { model, apiProvider })
    if (result) {
      setGenerationPreviewData(result)
      setGenerationPreviewField(null)
      setGenerationTargetForm('create')
      setGenerationPreviewOpen(true)
    }
  }

  // Handle single field generation
  const handleGenerateField = async (
    field: CharacterField,
    form: FormInstance,
    targetForm: 'create' | 'edit'
  ) => {
    if (!selectedGenModel) {
      notification.warning({
        message: t("settings:manageCharacters.generate.noModelSelected", {
          defaultValue: "No model selected"
        }),
        description: t("settings:manageCharacters.generate.noModelSelectedDesc", {
          defaultValue: "Please select a model in the generation panel first."
        })
      })
      return
    }

    const existingFields = getFormFieldsAsCharacter(form)
    const currentValue = (existingFields as any)[field]

    const result = await generateField(field, existingFields, {
      model: selectedGenModel,
      apiProvider: selectedGenModelProvider
    })

    if (result !== null) {
      // If field has existing content, show preview
      if (currentValue && String(currentValue).trim().length > 0) {
        setGenerationPreviewData({ [field]: result } as GeneratedCharacter)
        setGenerationPreviewField(field)
        setGenerationTargetForm(targetForm)
        setGenerationPreviewOpen(true)
      } else {
        // Apply directly if field is empty
        applyGeneratedFieldToForm(field, result, form)
      }
    }
  }

  const renderSystemPromptField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => {
      const showExample =
        mode === "create"
          ? showCreateSystemPromptExample
          : showEditSystemPromptExample
      const toggleExample =
        mode === "create"
          ? setShowCreateSystemPromptExample
          : setShowEditSystemPromptExample

      return (
        <>
          <Form.Item
            name="system_prompt"
            label={
              <span>
                {t(
                  "settings:manageCharacters.form.systemPrompt.label",
                  { defaultValue: "Behavior / instructions" }
                )}
                <span className="text-danger ml-0.5" aria-hidden="true">*</span>
                <span className="sr-only"> ({t("common:required", { defaultValue: "required" })})</span>
                <GenerateFieldButton
                  isGenerating={generatingField === "system_prompt"}
                  disabled={isGenerating}
                  onClick={() =>
                    handleGenerateField("system_prompt", form, mode)
                  }
                />
              </span>
            }
          help={t(
            "settings:manageCharacters.form.systemPrompt.help",
            {
              defaultValue:
                "System prompt: full behavioral instructions sent to the model, including role, tone, and constraints. (max 2000 characters)"
            }
          )}
            extra={
              <div className="space-y-2">
                <button
                  type="button"
                  className="text-xs font-medium text-primary underline-offset-2 hover:underline"
                  onClick={() => toggleExample((value) => !value)}>
                  {showExample
                    ? t("settings:manageCharacters.form.systemPrompt.hideExample", {
                        defaultValue: "Hide example"
                      })
                    : t("settings:manageCharacters.form.systemPrompt.showExample", {
                        defaultValue: "Show example"
                      })}
                </button>
                {showExample && (
                  <div className="rounded border border-border bg-surface2 p-2">
                    <p className="mb-2 text-xs font-medium text-text">
                      {t("settings:manageCharacters.form.systemPrompt.exampleLabel", {
                        defaultValue: "Writing Assistant example"
                      })}
                    </p>
                    <p className="whitespace-pre-wrap text-xs text-text-muted">
                      {SYSTEM_PROMPT_EXAMPLE}
                    </p>
                    <Button
                      type="link"
                      size="small"
                      className="mt-2 p-0"
                      onClick={() => applySystemPromptExample(mode)}>
                      {t("settings:manageCharacters.form.systemPrompt.useExample", {
                        defaultValue: "Use this example"
                      })}
                    </Button>
                  </div>
                )}
              </div>
            }
            rules={[
              {
                required: true,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.required",
                  {
                    defaultValue:
                      "Please add instructions for how the character should respond."
                  }
                )
              },
              {
                min: 10,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.min",
                  {
                    defaultValue:
                      "Add a short description so the character knows how to respond."
                  }
                )
              },
              {
                max: 2000,
                message: t(
                  "settings:manageCharacters.form.systemPrompt.max",
                  {
                    defaultValue:
                      "System prompt must be 2000 characters or less."
                  }
                )
              }
            ]}>
            <Input.TextArea
              autoSize={{ minRows: 3, maxRows: 8 }}
              showCount
              maxLength={2000}
              placeholder={t(
                "settings:manageCharacters.form.systemPrompt.placeholder",
                {
                  defaultValue:
                    "E.g., You are a patient math teacher who explains concepts step by step and checks understanding with short examples."
                }
              )}
            />
          </Form.Item>

          <Form.Item
            name="prompt_preset"
            label={t(
              "settings:manageCharacters.form.promptPreset.label",
              { defaultValue: "Prompt preset" }
            )}
            help={t(
              "settings:manageCharacters.form.promptPreset.help",
              {
                defaultValue:
                  "Controls how character fields are formatted in system prompts for character chats."
              }
            )}>
            <Select options={promptPresetOptions} />
          </Form.Item>
        </>
      )
    },
    [
      applySystemPromptExample,
      generatingField,
      handleGenerateField,
      isGenerating,
      promptPresetOptions,
      showCreateSystemPromptExample,
      showEditSystemPromptExample,
      t
    ]
  )

  const renderAlternateGreetingsField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => {
      const markDirty =
        mode === "create" ? () => setCreateFormDirty(true) : () => setEditFormDirty(true)

      return (
        <Form.Item
          label={
            <span>
              {t(
                "settings:manageCharacters.form.alternateGreetings.label",
                {
                  defaultValue: "Alternate greetings"
                }
              )}
              <GenerateFieldButton
                isGenerating={generatingField === "alternate_greetings"}
                disabled={isGenerating}
                onClick={() =>
                  handleGenerateField("alternate_greetings", form, mode)
                }
              />
            </span>
          }
          help={t(
            "settings:manageCharacters.form.alternateGreetings.help",
            {
              defaultValue:
                "Optional alternate greetings to rotate between when starting chats."
            }
          )}>
          <Form.List name="alternate_greetings">
            {(fields, { add, remove, move }) => (
              <div className="space-y-2">
                {fields.length === 0 && (
                  <p className="text-xs text-text-subtle">
                    {t(
                      "settings:manageCharacters.form.alternateGreetings.empty",
                      {
                        defaultValue:
                          "No alternate greetings yet. Add one to vary how chats start."
                      }
                    )}
                  </p>
                )}
                {fields.map((field, index) => {
                  const { key, ...fieldProps } = field
                  return (
                    <div
                      key={key}
                      className="rounded-md border border-border bg-surface2 p-2">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-text-muted">
                          {t(
                            "settings:manageCharacters.form.alternateGreetings.itemLabel",
                            {
                              defaultValue: "Greeting {{index}}",
                              index: index + 1
                            }
                          )}
                        </span>
                        <div className="flex items-center gap-1">
                          <Button
                            type="text"
                            size="small"
                            icon={<ChevronUp className="h-4 w-4" />}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.moveUp",
                              { defaultValue: "Move greeting up" }
                            )}
                            disabled={index === 0}
                            onClick={() => {
                              move(index, index - 1)
                              markDirty()
                            }}
                          />
                          <Button
                            type="text"
                            size="small"
                            icon={<ChevronDown className="h-4 w-4" />}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.moveDown",
                              { defaultValue: "Move greeting down" }
                            )}
                            disabled={index === fields.length - 1}
                            onClick={() => {
                              move(index, index + 1)
                              markDirty()
                            }}
                          />
                          <Button
                            type="text"
                            size="small"
                            danger
                            icon={<X className="h-4 w-4" />}
                            aria-label={t(
                              "settings:manageCharacters.form.alternateGreetings.remove",
                              { defaultValue: "Remove greeting" }
                            )}
                            onClick={() => {
                              remove(field.name)
                              markDirty()
                            }}
                          />
                        </div>
                      </div>
                      <Form.Item
                        {...fieldProps}
                        className="mb-0"
                        rules={[
                          {
                            validator: async (_rule, value) => {
                              if (!value || String(value).trim().length === 0) {
                                return Promise.resolve()
                              }
                              if (String(value).trim().length > 1000) {
                                return Promise.reject(
                                  new Error(
                                    t(
                                      "settings:manageCharacters.form.alternateGreetings.max",
                                      {
                                        defaultValue:
                                          "Alternate greeting must be 1000 characters or less."
                                      }
                                    )
                                  )
                                )
                              }
                              return Promise.resolve()
                            }
                          }
                        ]}>
                        <Input.TextArea
                          autoSize={{ minRows: 2, maxRows: 6 }}
                          showCount
                          maxLength={1000}
                          placeholder={t(
                            "settings:manageCharacters.form.alternateGreetings.itemPlaceholder",
                            {
                              defaultValue:
                                "Enter an alternate greeting message"
                            }
                          )}
                          onChange={() => markDirty()}
                        />
                      </Form.Item>
                    </div>
                  )
                })}
                <Button
                  type="dashed"
                  size="small"
                  onClick={() => {
                    add("")
                    markDirty()
                  }}>
                  {t(
                    "settings:manageCharacters.form.alternateGreetings.add",
                    { defaultValue: "Add alternate greeting" }
                  )}
                </Button>
              </div>
            )}
          </Form.List>
        </Form.Item>
      )
    },
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const markModeDirty = React.useCallback((mode: "create" | "edit") => {
    if (mode === "create") {
      setCreateFormDirty(true)
    } else {
      setEditFormDirty(true)
    }
  }, [])

  const renderNameField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="name"
        label={
          <span>
            {t("settings:manageCharacters.form.name.label", {
              defaultValue: "Name"
            })}
            <span className="text-danger ml-0.5">*</span>
            <GenerateFieldButton
              isGenerating={generatingField === "name"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("name", form, mode)}
            />
          </span>
        }
        rules={[
          {
            required: true,
            message: t(
              "settings:manageCharacters.form.name.required",
              { defaultValue: "Please enter a name" }
            )
          },
          {
            max: MAX_NAME_LENGTH,
            message: t(
              "settings:manageCharacters.form.name.maxLength",
              {
                defaultValue: `Name must be ${MAX_NAME_LENGTH} characters or fewer`
              }
            )
          }
        ]}>
        <Input
          ref={mode === "create" ? createNameRef : editNameRef}
          placeholder={t(
            "settings:manageCharacters.form.name.placeholder",
            { defaultValue: "e.g. Writing coach" }
          )}
          maxLength={MAX_NAME_LENGTH}
          showCount
        />
      </Form.Item>
    ),
    [editNameRef, createNameRef, generatingField, handleGenerateField, isGenerating, t]
  )

  const renderGreetingField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="greeting"
        label={
          <span>
            {t("settings:manageCharacters.form.greeting.label", {
              defaultValue: "Greeting message (optional)"
            })}
            <GenerateFieldButton
              isGenerating={generatingField === "first_message"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("first_message", form, mode)}
            />
          </span>
        }
        help={t("settings:manageCharacters.form.greeting.help", {
          defaultValue:
            "Optional first message the character will send when you start a chat."
        })}>
        <Input.TextArea
          autoSize={{ minRows: 2, maxRows: 6 }}
          placeholder={t(
            "settings:manageCharacters.form.greeting.placeholder",
            {
              defaultValue:
                "Hi there! I'm your writing coach. Paste your draft and I'll help you tighten it up."
            }
          )}
          showCount
          maxLength={1000}
        />
      </Form.Item>
    ),
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const renderDescriptionField = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => (
      <Form.Item
        name="description"
        label={
          <span>
            {t("settings:manageCharacters.form.description.label", {
              defaultValue: "Description"
            })}
            <GenerateFieldButton
              isGenerating={generatingField === "description"}
              disabled={isGenerating}
              onClick={() => handleGenerateField("description", form, mode)}
            />
          </span>
        }
        help={t("settings:manageCharacters.form.description.help", {
          defaultValue: "Description: brief blurb shown in character lists and cards."
        })}>
        <Input
          placeholder={t(
            "settings:manageCharacters.form.description.placeholder",
            { defaultValue: "Short description" }
          )}
        />
      </Form.Item>
    ),
    [generatingField, handleGenerateField, isGenerating, t]
  )

  const renderTagsField = (form: FormInstance, mode: "create" | "edit") => (
    <Form.Item
      name="tags"
      label={
        <span>
          {t("settings:manageCharacters.tags.label", {
            defaultValue: "Tags"
          })}
          <GenerateFieldButton
            isGenerating={generatingField === "tags"}
            disabled={isGenerating}
            onClick={() => handleGenerateField("tags", form, mode)}
          />
        </span>
      }
      help={t("settings:manageCharacters.tags.help", {
        defaultValue:
          "Use tags to group characters by use case (e.g., 'writing', 'teaching')."
      })}>
      <div className="space-y-2">
        {popularTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            <span className="text-xs text-text-subtle mr-1">
              {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
            </span>
            {popularTags.map(({ tag, count }) => {
              const currentTags = form.getFieldValue("tags") || []
              const isSelected = currentTags.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors motion-reduce:transition-none ${
                    isSelected
                      ? "bg-primary/10 border-primary text-primary"
                      : "bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary"
                  }`}
                  onClick={() => {
                    const current = form.getFieldValue("tags") || []
                    if (isSelected) {
                      form.setFieldValue(
                        "tags",
                        current.filter((t: string) => t !== tag)
                      )
                    } else {
                      form.setFieldValue("tags", [...current, tag])
                    }
                    markModeDirty(mode)
                  }}>
                  {tag}
                  <span className="text-text-subtle">({count})</span>
                </button>
              )
            })}
          </div>
        )}
        <Form.Item name="tags" noStyle>
          <Select
            mode="tags"
            allowClear
            placeholder={t(
              "settings:manageCharacters.tags.placeholder",
              {
                defaultValue: "Add tags"
              }
            )}
            options={tagOptionsWithCounts}
            filterOption={(input, option) =>
              option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
        </Form.Item>
      </div>
    </Form.Item>
  )

  const renderAvatarField = React.useCallback(
    (form: FormInstance) => (
      <Form.Item
        noStyle
        shouldUpdate={(prev, cur) =>
          prev?.name !== cur?.name || prev?.description !== cur?.description
        }>
        {({ getFieldValue }) => (
          <Form.Item
            name="avatar"
            label={t("settings:manageCharacters.avatar.label", {
              defaultValue: "Avatar (optional)"
            })}>
            <AvatarField
              characterName={getFieldValue("name")}
              characterDescription={getFieldValue("description")}
            />
          </Form.Item>
        )}
      </Form.Item>
    ),
    [t]
  )

  const renderAdvancedFields = React.useCallback(
    (form: FormInstance, mode: "create" | "edit") => {
      const showAdvanced = mode === "create" ? showCreateAdvanced : showEditAdvanced
      const setShowAdvanced =
        mode === "create" ? setShowCreateAdvanced : setShowEditAdvanced
      const sectionState =
        mode === "create" ? createAdvancedSections : editAdvancedSections
      const setSectionState =
        mode === "create" ? setCreateAdvancedSections : setEditAdvancedSections
      const toggleSection = (section: AdvancedSectionKey) => {
        setSectionState((prev) => ({ ...prev, [section]: !prev[section] }))
      }
      const renderSection = (
        section: AdvancedSectionKey,
        title: string,
        children: React.ReactNode
      ) => (
        <div className="rounded-md border border-border/70 bg-bg/40">
          <button
            type="button"
            className="flex w-full items-center justify-between px-3 py-2 text-left"
            aria-expanded={sectionState[section]}
            onClick={() => toggleSection(section)}>
            <span className="text-sm font-medium text-text">{title}</span>
            {sectionState[section] ? (
              <ChevronUp className="h-4 w-4 text-text-subtle" />
            ) : (
              <ChevronDown className="h-4 w-4 text-text-subtle" />
            )}
          </button>
          {sectionState[section] && (
            <div className="space-y-3 border-t border-border/60 p-3">
              {children}
            </div>
          )}
        </div>
      )

      return (
        <>
          <button
            type="button"
            className="mb-2 text-xs font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => setShowAdvanced((v) => !v)}>
            {showAdvanced
              ? t("settings:manageCharacters.advanced.hide", {
                  defaultValue: "Hide advanced fields"
                })
              : t("settings:manageCharacters.advanced.show", {
                  defaultValue: "Show advanced fields"
                })}
          </button>
          {showAdvanced && (
            <div className="space-y-3 rounded-md border border-dashed border-border p-3">
              {renderSection(
                "promptControl",
                t("settings:manageCharacters.advanced.section.promptControl", {
                  defaultValue: "Prompt control"
                }),
                <>
                  <Form.Item
                    name="personality"
                    label={
                      <span>
                        {t("settings:manageCharacters.form.personality.label", {
                          defaultValue: "Personality"
                        })}
                        <GenerateFieldButton
                          isGenerating={generatingField === "personality"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("personality", form, mode)}
                        />
                      </span>
                    }
                    help={t("settings:manageCharacters.form.personality.help", {
                      defaultValue:
                        "Personality: adjectives and traits injected into context to shape voice and behavior."
                    })}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="scenario"
                    label={
                      <span>
                        {t("settings:manageCharacters.form.scenario.label", {
                          defaultValue: "Scenario"
                        })}
                        <GenerateFieldButton
                          isGenerating={generatingField === "scenario"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("scenario", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="post_history_instructions"
                    label={t("settings:manageCharacters.form.postHistory.label", {
                      defaultValue: "Post-history instructions"
                    })}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="message_example"
                    label={
                      <span>
                        {t(
                          "settings:manageCharacters.form.messageExample.label",
                          {
                            defaultValue: "Message example"
                          }
                        )}
                        <GenerateFieldButton
                          isGenerating={generatingField === "message_example"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("message_example", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  <Form.Item
                    name="creator_notes"
                    label={
                      <span>
                        {t(
                          "settings:manageCharacters.form.creatorNotes.label",
                          {
                            defaultValue: "Creator notes"
                          }
                        )}
                        <GenerateFieldButton
                          isGenerating={generatingField === "creator_notes"}
                          disabled={isGenerating}
                          onClick={() => handleGenerateField("creator_notes", form, mode)}
                        />
                      </span>
                    }>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                  </Form.Item>
                  {renderAlternateGreetingsField(form, mode)}
                  <Form.Item
                    name="default_author_note"
                    label={t(
                      "settings:manageCharacters.form.defaultAuthorNote.label",
                      { defaultValue: "Default author note" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.defaultAuthorNote.help",
                      {
                        defaultValue:
                          "Optional default note used by character chats when the chat-level author note is empty."
                      }
                    )}>
                    <Input.TextArea
                      autoSize={{ minRows: 2, maxRows: 6 }}
                      showCount
                      maxLength={2000}
                      placeholder={t(
                        "settings:manageCharacters.form.defaultAuthorNote.placeholder",
                        {
                          defaultValue:
                            "E.g., Keep replies concise, grounded, and in first-person voice."
                        }
                      )}
                    />
                  </Form.Item>
                </>
              )}

              {renderSection(
                "generationSettings",
                t("settings:manageCharacters.advanced.section.generationSettings", {
                  defaultValue: "Generation settings"
                }),
                <>
                  <Form.Item
                    name="generation_temperature"
                    label={t(
                      "settings:manageCharacters.form.generationTemperature.label",
                      { defaultValue: "Generation temperature" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationTemperature.help",
                      {
                        defaultValue:
                          "Optional per-character sampling temperature for character chat completions."
                      }
                    )}>
                    <InputNumber min={0} max={2} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_top_p"
                    label={t(
                      "settings:manageCharacters.form.generationTopP.label",
                      { defaultValue: "Generation top_p" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationTopP.help",
                      {
                        defaultValue:
                          "Optional per-character nucleus sampling value (0.0 to 1.0)."
                      }
                    )}>
                    <InputNumber min={0} max={1} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_repetition_penalty"
                    label={t(
                      "settings:manageCharacters.form.generationRepetitionPenalty.label",
                      { defaultValue: "Repetition penalty" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationRepetitionPenalty.help",
                      {
                        defaultValue:
                          "Optional per-character repetition penalty used for character chat completions."
                      }
                    )}>
                    <InputNumber min={0} max={3} step={0.01} className="w-full" />
                  </Form.Item>
                  <Form.Item
                    name="generation_stop_strings"
                    label={t(
                      "settings:manageCharacters.form.generationStopStrings.label",
                      { defaultValue: "Stop strings" }
                    )}
                    help={t(
                      "settings:manageCharacters.form.generationStopStrings.help",
                      {
                        defaultValue:
                          "Optional stop sequences for this character. Use one per line."
                      }
                    )}>
                    <Input.TextArea
                      autoSize={{ minRows: 2, maxRows: 6 }}
                      placeholder={t(
                        "settings:manageCharacters.form.generationStopStrings.placeholder",
                        {
                          defaultValue:
                            "Example:\n###\nEND"
                        }
                      )}
                    />
                  </Form.Item>
                </>
              )}

              {renderSection(
                "metadata",
                t("settings:manageCharacters.advanced.section.metadata", {
                  defaultValue: "Metadata"
                }),
                <>
                  <Form.Item
                    name="creator"
                    label={t("settings:manageCharacters.form.creator.label", {
                      defaultValue: "Creator"
                    })}>
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="character_version"
                    label={t(
                      "settings:manageCharacters.form.characterVersion.label",
                      {
                        defaultValue: "Character version"
                      }
                    )}
                    help={t(
                      "settings:manageCharacters.form.characterVersion.help",
                      {
                        defaultValue: "Free text, e.g. \"1.0\" or \"2024-01\""
                      }
                    )}>
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name="extensions"
                    label={t("settings:manageCharacters.form.extensions.label", {
                      defaultValue: "Extensions (JSON)"
                    })}
                    help={t(
                      "settings:manageCharacters.form.extensions.help",
                      {
                        defaultValue:
                          "Optional JSON object with additional metadata; invalid JSON will be sent as raw text."
                      }
                    )}>
                    <Input.TextArea autoSize={{ minRows: 2, maxRows: 8 }} />
                  </Form.Item>
                  <div className="rounded-md border border-dashed border-border px-3 py-2">
                    <p className="text-xs font-medium text-text">
                      {t("settings:manageCharacters.form.moodImages.placeholderTitle", {
                        defaultValue: "Mood images (coming soon)"
                      })}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {t("settings:manageCharacters.form.moodImages.placeholderBody", {
                        defaultValue:
                          "Per-mood image variants are planned but not yet available in the character editor."
                      })}
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )
    },
    [
      createAdvancedSections,
      editAdvancedSections,
      generatingField,
      handleGenerateField,
      isGenerating,
      renderAlternateGreetingsField,
      showCreateAdvanced,
      showEditAdvanced,
      t
    ]
  )

  const renderSharedCharacterForm = ({
    form,
    mode,
    initialValues,
    isSubmitting,
    submitButtonClassName,
    submitPendingLabel,
    submitIdleLabel,
    showPreview,
    onTogglePreview,
    onValuesChange,
    onFinish
  }: SharedCharacterFormProps) => (
    <Form
      layout="vertical"
      form={form}
      initialValues={initialValues}
      className="space-y-3"
      onValuesChange={(_, allValues) => {
        onValuesChange(allValues)
      }}
      onFinish={onFinish}>
      {/* Field order: Name → System Prompt (required) → Greeting → Description → Tags → Avatar */}
      {renderNameField(form, mode)}
      {renderSystemPromptField(form, mode)}
      {renderGreetingField(form, mode)}
      {renderDescriptionField(form, mode)}
      {renderTagsField(form, mode)}
      {renderAvatarField(form)}
      {renderAdvancedFields(form, mode)}

      {/* Preview toggle */}
      <button
        type="button"
        className="mt-4 mb-2 flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text"
        onClick={onTogglePreview}>
        {showPreview ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
        {showPreview
          ? t("settings:manageCharacters.preview.hide", {
              defaultValue: "Hide preview"
            })
          : t("settings:manageCharacters.preview.show", {
              defaultValue: "Show preview"
            })}
      </button>

      {/* Character Preview */}
      {showPreview && (
        <Form.Item noStyle shouldUpdate>
          {() => {
            const avatar = form.getFieldValue("avatar")
            const avatarValues = avatar ? extractAvatarValues(avatar) : {}
            return (
              <CharacterPreview
                name={form.getFieldValue("name")}
                description={form.getFieldValue("description")}
                avatar_url={avatarValues.avatar_url}
                image_base64={avatarValues.image_base64}
                system_prompt={form.getFieldValue("system_prompt")}
                greeting={form.getFieldValue("greeting")}
                tags={form.getFieldValue("tags")}
              />
            )
          }}
        </Form.Item>
      )}

      <Button
        type="primary"
        htmlType="submit"
        loading={isSubmitting}
        className={submitButtonClassName}>
        {isSubmitting ? submitPendingLabel : submitIdleLabel}
      </Button>
    </Form>
  )

  // Apply generated data to form
  const applyGeneratedFieldToForm = (
    field: string,
    value: any,
    form: FormInstance
  ) => {
    // Map field names to form field names
    const fieldMap: Record<string, string> = {
      first_message: 'greeting'
    }
    const formField = fieldMap[field] || field
    form.setFieldValue(formField, value)
    if (generationTargetForm === 'create') {
      setCreateFormDirty(true)
    } else {
      setEditFormDirty(true)
    }
  }

  // Apply full character generation preview
  const applyGenerationPreview = () => {
    if (!generationPreviewData) return

    const form = generationTargetForm === 'create' ? createForm : editForm

    if (generationPreviewField) {
      // Single field
      const value = (generationPreviewData as any)[generationPreviewField]
      if (value !== undefined) {
        applyGeneratedFieldToForm(generationPreviewField, value, form)
      }
    } else {
      // Full character - apply all non-empty fields
      const fieldMap: Record<string, string> = {
        first_message: 'greeting'
      }

      Object.entries(generationPreviewData).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          const formField = fieldMap[key] || key
          form.setFieldValue(formField, value)
        }
      })

      // Auto-expand advanced section if advanced fields were generated
      const hasAdvanced = generationPreviewData.personality ||
        generationPreviewData.scenario ||
        generationPreviewData.message_example ||
        generationPreviewData.creator_notes ||
        (generationPreviewData.alternate_greetings && generationPreviewData.alternate_greetings.length > 0)

      if (hasAdvanced) {
        if (generationTargetForm === 'create') {
          setShowCreateAdvanced(true)
        } else {
          setShowEditAdvanced(true)
        }
      }

      if (generationTargetForm === 'create') {
        setCreateFormDirty(true)
      } else {
        setEditFormDirty(true)
      }
    }

    setGenerationPreviewOpen(false)
    setGenerationPreviewData(null)
    setGenerationPreviewField(null)
  }

  React.useEffect(() => {
    if (forwardedNewButtonRef && newButtonRef.current) {
      // Expose the "New character" button to parent workspaces that may
      // want to focus it (e.g., when coming from a persistence error).
      // The ref object itself is stable; assign its current value once.
      // eslint-disable-next-line no-param-reassign
      ;(forwardedNewButtonRef as any).current = newButtonRef.current
    }
  }, [forwardedNewButtonRef])

  React.useEffect(() => {
    if (!autoOpenCreate) return
    if (autoOpenCreateHandledRef.current) return
    autoOpenCreateHandledRef.current = true
    if (!openEdit && !conversationsOpen) {
      openCreateModal()
    }
  }, [autoOpenCreate, conversationsOpen, openCreateModal, openEdit])

  // C8: Debounce search input to reduce API calls
  React.useEffect(() => {
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current)
    }
    searchDebounceRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm)
    }, 300)
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current)
        searchDebounceRef.current = null
      }
    }
  }, [searchTerm])

  // Persist view mode preference
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('characters-view-mode', viewMode)
    }
  }, [viewMode])

  React.useEffect(() => {
    if (characterListScope === "deleted" && viewMode !== "table") {
      setViewMode("table")
    }
  }, [characterListScope, viewMode])

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(GALLERY_DENSITY_KEY, galleryDensity)
    }
  }, [galleryDensity])

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(pageSize))
    }
  }, [pageSize])

  // Persist sort preference
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      if (sortColumn) {
        localStorage.setItem('characters-sort-column', sortColumn)
      } else {
        localStorage.removeItem('characters-sort-column')
      }
      if (sortOrder) {
        localStorage.setItem('characters-sort-order', sortOrder)
      } else {
        localStorage.removeItem('characters-sort-order')
      }
    }
  }, [sortColumn, sortOrder])

  // Keyboard shortcut: "/" to focus search
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if user is typing in an input/textarea or a modal is open
      const target = e.target as HTMLElement
      const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
      const modalOpen = open || openEdit || conversationsOpen || Boolean(quickChatCharacter)

      if (isTyping || modalOpen) return

      if (e.key === '/') {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [conversationsOpen, open, openEdit, quickChatCharacter])

  React.useEffect(() => {
    setCurrentPage(1)
  }, [
    characterListScope,
    creatorFilter,
    debouncedSearchTerm,
    filterTags,
    hasConversationsOnly,
    matchAllTags
  ])

  // Cleanup pending delete timeout on unmount
  React.useEffect(() => {
    return () => {
      if (undoDeleteRef.current) {
        clearTimeout(undoDeleteRef.current)
      }
      if (bulkUndoDeleteRef.current) {
        clearTimeout(bulkUndoDeleteRef.current)
      }
    }
  }, [])

  const resolveImportDetail = (error: unknown) => {
    const details = (error as any)?.details
    if (details && typeof details === "object") {
      return (details as any).detail ?? details
    }
    return null
  }

  const revokeImportPreviewAvatarUrls = React.useCallback(
    (items: CharacterImportPreview[]) => {
      if (typeof URL === "undefined" || typeof URL.revokeObjectURL !== "function") {
        return
      }
      for (const item of items) {
        const extension = getImportFileExtension(item.fileName)
        if (item.avatarUrl && IMPORT_IMAGE_EXTENSIONS.has(extension)) {
          try {
            URL.revokeObjectURL(item.avatarUrl)
          } catch {
            // no-op cleanup
          }
        }
      }
    },
    []
  )

  const resetImportPreview = React.useCallback(() => {
    setImportPreviewOpen(false)
    setImportPreviewLoading(false)
    setImportPreviewItems((previous) => {
      revokeImportPreviewAvatarUrls(previous)
      return []
    })
  }, [revokeImportPreviewAvatarUrls])

  React.useEffect(() => {
    return () => {
      revokeImportPreviewAvatarUrls(importPreviewItems)
    }
  }, [importPreviewItems, revokeImportPreviewAvatarUrls])

  const importablePreviewItems = React.useMemo(
    () => importPreviewItems.filter((item) => !item.parseError),
    [importPreviewItems]
  )

  const importCharacterFile = React.useCallback(
    async (
      file: File,
      options?: CharacterImportOptions
    ): Promise<CharacterImportResult> => {
      const allowImageOnly = options?.allowImageOnly ?? false
      const suppressNotifications = options?.suppressNotifications ?? false
      const invalidateOnSuccess = options?.invalidateOnSuccess ?? true
      setImporting(true)
      try {
        const response = await tldwClient.importCharacterFile(file, {
          allowImageOnly
        })
        if (invalidateOnSuccess) {
          qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        }
        const message =
          response?.message ||
          t("settings:manageCharacters.import.success", {
            defaultValue: "Character imported successfully"
          })
        if (!suppressNotifications) {
          notification.success({
            message: t("settings:manageCharacters.import.title", {
              defaultValue: "Import complete"
            }),
            description: message
          })
        }
        return {
          success: true,
          fileName: file.name,
          message
        }
      } catch (err: any) {
        const detail = resolveImportDetail(err)
        if (
          detail?.code === "missing_character_data" &&
          detail?.can_import_image_only &&
          !allowImageOnly
        ) {
          const message =
            detail?.message ||
            t("settings:manageCharacters.import.imageOnlyDesc", {
              defaultValue:
                "No character data detected in the image metadata. Import as an image-only character?"
            })
          if (suppressNotifications) {
            return {
              success: false,
              fileName: file.name,
              message
            }
          }
          Modal.confirm({
            title: t("settings:manageCharacters.import.imageOnlyTitle", {
              defaultValue: "No character data detected"
            }),
            content: message,
            okText: t("settings:manageCharacters.import.imageOnlyConfirm", {
              defaultValue: "Import image only"
            }),
            cancelText: t("common:cancel", { defaultValue: "Cancel" }),
            onOk: () => void importCharacterFile(file, { allowImageOnly: true })
          })
          return {
            success: false,
            fileName: file.name,
            message
          }
        }
        const errorMessage =
          err?.message ||
          t("settings:manageCharacters.import.errorDesc", {
            defaultValue: "Unable to import character. Please try again."
          })
        if (!suppressNotifications) {
          notification.error({
            message: t("settings:manageCharacters.import.errorTitle", {
              defaultValue: "Import failed"
            }),
            description: errorMessage
          })
        }
        return {
          success: false,
          fileName: file.name,
          message: errorMessage
        }
      } finally {
        setImporting(false)
      }
    },
    [notification, qc, t]
  )

  const runBatchImport = React.useCallback(
    async (batch: File[]) => {
      const results: CharacterImportResult[] = []
      for (const nextFile of batch) {
        results.push(
          await importCharacterFile(nextFile, {
            suppressNotifications: true,
            invalidateOnSuccess: false
          })
        )
      }

      const successCount = results.filter((result) => result.success).length
      const failed = results.filter((result) => !result.success)

      if (successCount > 0) {
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      }

      if (failed.length === 0) {
        notification.success({
          message: t("settings:manageCharacters.import.batchSuccessTitle", {
            defaultValue: "Batch import complete"
          }),
          description: t("settings:manageCharacters.import.batchSuccessDesc", {
            defaultValue: "Imported {{count}} files successfully.",
            count: successCount
          })
        })
        return
      }

      const failureDetails = failed
        .map((result) => `${result.fileName}: ${result.message}`)
        .join(" | ")

      const message =
        successCount > 0
          ? t("settings:manageCharacters.import.batchPartialTitle", {
              defaultValue: "Batch import partially complete"
            })
          : t("settings:manageCharacters.import.batchFailedTitle", {
              defaultValue: "Batch import failed"
            })
      const description = `${t(
        "settings:manageCharacters.import.batchSummary",
        {
          defaultValue: "{{success}} succeeded, {{failed}} failed.",
          success: successCount,
          failed: failed.length
        }
      )} ${failureDetails}`.trim()

      if (successCount > 0) {
        notification.warning({ message, description })
      } else {
        notification.error({ message, description })
      }
    },
    [importCharacterFile, notification, qc, t]
  )

  const openImportPreviewForBatch = React.useCallback(
    async (batch: File[]) => {
      setImportPreviewLoading(true)
      try {
        const previews = await Promise.all(
          batch.map((nextFile, index) =>
            parseCharacterImportPreview(nextFile, index)
          )
        )
        setImportPreviewItems((previous) => {
          revokeImportPreviewAvatarUrls(previous)
          return previews
        })
        setImportPreviewOpen(true)
      } catch (error: any) {
        notification.error({
          message: t("settings:manageCharacters.import.previewErrorTitle", {
            defaultValue: "Preview unavailable"
          }),
          description:
            error?.message ||
            t("settings:manageCharacters.import.previewErrorDesc", {
              defaultValue:
                "Could not build an import preview. Try uploading the file again."
            })
        })
      } finally {
        setImportPreviewLoading(false)
      }
    },
    [notification, revokeImportPreviewAvatarUrls, t]
  )

  const handleConfirmImportPreview = React.useCallback(async () => {
    const importableFiles = importablePreviewItems.map((item) => item.file)
    const skippedCount = importPreviewItems.length - importableFiles.length
    if (importableFiles.length === 0) {
      notification.error({
        message: t("settings:manageCharacters.import.previewNothingTitle", {
          defaultValue: "No importable files"
        }),
        description: t("settings:manageCharacters.import.previewNothingDesc", {
          defaultValue: "Fix preview errors or choose different files."
        })
      })
      return
    }

    resetImportPreview()

    if (importableFiles.length === 1) {
      await importCharacterFile(importableFiles[0])
    } else {
      await runBatchImport(importableFiles)
    }

    if (skippedCount > 0) {
      notification.warning({
        message: t("settings:manageCharacters.import.previewSkippedTitle", {
          defaultValue: "Some files were skipped"
        }),
        description: t("settings:manageCharacters.import.previewSkippedDesc", {
          defaultValue:
            "{{count}} files were skipped because preview parsing failed.",
          count: skippedCount
        })
      })
    }
  }, [
    importCharacterFile,
    importPreviewItems.length,
    importablePreviewItems,
    notification,
    resetImportPreview,
    runBatchImport,
    t
  ])

  const handleImportUpload = React.useCallback(
    async (file: File, fileList: File[]) => {
      const batch = (fileList && fileList.length > 0 ? fileList : [file]).filter(
        Boolean
      )

      if (batch.length > 1) {
        const first = batch[0]
        const firstUid = (first as any)?.uid
        const fileUid = (file as any)?.uid
        const isFirstFile =
          (typeof fileUid === "string" &&
            typeof firstUid === "string" &&
            fileUid === firstUid) ||
          (first &&
            file.name === first.name &&
            file.size === first.size &&
            file.lastModified === first.lastModified)
        if (!isFirstFile) return false
      }

      await openImportPreviewForBatch(batch)
      return false
    },
    [openImportPreviewForBatch]
  )

  const hasFilters =
    searchTerm.trim().length > 0 ||
    (filterTags && filterTags.length > 0) ||
    !!creatorFilter ||
    hasConversationsOnly

  const {
    setHistory,
    setMessages,
    setHistoryId,
    setServerChatId,
    setServerChatState,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef
  } = useStoreMessageOption(
    (state) => ({
      setHistory: state.setHistory,
      setMessages: state.setMessages,
      setHistoryId: state.setHistoryId,
      setServerChatId: state.setServerChatId,
      setServerChatState: state.setServerChatState,
      setServerChatTopic: state.setServerChatTopic,
      setServerChatClusterId: state.setServerChatClusterId,
      setServerChatSource: state.setServerChatSource,
      setServerChatExternalRef: state.setServerChatExternalRef
    }),
    shallow
  )

  const characterIdentifier = (record: any): string =>
    String(record?.id ?? record?.slug ?? record?.name ?? "")

  const formatUpdatedLabel = (value?: string | null) => {
    const fallback = t("settings:manageCharacters.conversations.unknownTime", {
      defaultValue: "Unknown"
    })
    let formatted = fallback
    if (value) {
      try {
        formatted = new Date(value).toLocaleString()
      } catch {
        formatted = String(value)
      }
    }
    return t("settings:manageCharacters.conversations.updated", {
      defaultValue: "Updated {{time}}",
      time: formatted
    })
  }

  const resolveTimestamp = (
    record: Record<string, any>,
    keys: string[]
  ): number | null => {
    for (const key of keys) {
      const raw = record?.[key]
      if (!raw) continue
      const timestamp =
        typeof raw === "number" ? raw : new Date(String(raw)).getTime()
      if (Number.isFinite(timestamp)) return timestamp
    }
    return null
  }

  const formatTableDateCell = (
    record: Record<string, any>,
    keys: string[]
  ): string => {
    const timestamp = resolveTimestamp(record, keys)
    if (!timestamp) return "—"
    return new Date(timestamp).toLocaleDateString()
  }

  const serverSortBy = React.useMemo(
    () => toCharactersSortBy(sortColumn),
    [sortColumn]
  )
  const serverSortOrder = React.useMemo(
    () => toCharactersSortOrder(sortOrder),
    [sortOrder]
  )
  const useServerQuery = isServerQueryRolloutEnabled || characterListScope === "deleted"
  const characterQueryParams = React.useMemo(
    () => ({
      page: currentPage,
      page_size: pageSize,
      query: debouncedSearchTerm.trim() || undefined,
      tags: filterTags.length > 0 ? filterTags : undefined,
      match_all_tags: filterTags.length > 0 ? matchAllTags : undefined,
      creator: creatorFilter || undefined,
      has_conversations: hasConversationsOnly ? true : undefined,
      include_deleted: characterListScope === "deleted" ? true : undefined,
      deleted_only: characterListScope === "deleted" ? true : undefined,
      sort_by: serverSortBy,
      sort_order: serverSortOrder,
      include_image_base64: false
    }),
    [
      characterListScope,
      creatorFilter,
      currentPage,
      debouncedSearchTerm,
      filterTags,
      hasConversationsOnly,
      matchAllTags,
      pageSize,
      serverSortBy,
      serverSortOrder
    ]
  )

  const {
    data: characterListResponse,
    status,
    error,
    refetch
  } = useQuery({
    queryKey: [
      "tldw:listCharacters",
      characterQueryParams,
      useServerQuery ? "server" : "legacy"
    ],
    queryFn: async () => {
      try {
        await tldwClient.initialize()
        if (useServerQuery) {
          return await tldwClient.listCharactersPage(characterQueryParams)
        }

        const allCharacters = await tldwClient.listAllCharacters({
          pageSize: 250,
          maxPages: 50
        })
        const filtered = filterCharactersForWorkspace(allCharacters, {
          query: debouncedSearchTerm.trim() || undefined,
          tags: filterTags,
          matchAllTags,
          creator: creatorFilter
        })
        const withConversationFilter = hasConversationsOnly
          ? filtered.filter((character) => hasInlineConversationCount(character))
          : filtered
        const sorted = sortCharactersForWorkspace(withConversationFilter, {
          sortBy: serverSortBy,
          sortOrder: serverSortOrder
        })
        const paged = paginateCharactersForWorkspace(sorted, {
          page: currentPage,
          pageSize
        })

        return {
          items: paged.items,
          total: paged.total,
          page: paged.page,
          page_size: paged.pageSize,
          has_more: paged.hasMore
        }
      } catch (e: any) {
        notification.error({
          message: t("settings:manageCharacters.notification.error", {
            defaultValue: "Error"
          }),
          description:
            e?.message ||
            t("settings:manageCharacters.notification.someError", {
              defaultValue: "Something went wrong. Please try again later"
            })
        })
        throw e
      }
    },
    staleTime: 5 * 60 * 1000
  })

  const isLegacyCharacterListResponse = Array.isArray(characterListResponse)
  const rawData = React.useMemo(
    () => {
      if (Array.isArray(characterListResponse)) return characterListResponse
      if (Array.isArray(characterListResponse?.items)) {
        return characterListResponse.items
      }
      return []
    },
    [characterListResponse]
  )
  const rawTotalCharacters = React.useMemo(
    () => {
      if (Array.isArray(characterListResponse)) {
        return characterListResponse.length
      }
      if (typeof characterListResponse?.total === "number") {
        return characterListResponse.total
      }
      return rawData.length
    },
    [characterListResponse, rawData.length]
  )

  // Fetch conversation counts for visible characters (H3)
  const characterIds = React.useMemo(() => {
    if (!Array.isArray(rawData)) return []
    return rawData
      .map((c: any) => String(c.id || c.slug || c.name))
      .filter(Boolean)
  }, [rawData])

  const { data: conversationCounts } = useQuery<Record<string, number>>({
    queryKey: ["tldw:characterConversationCounts", characterIds],
    queryFn: async () => {
      if (characterIds.length === 0) return {}
      await tldwClient.initialize()
      // Fetch all chats once and count by character_id
      const chats = await tldwClient.listChats({ limit: 1000 })
      const counts: Record<string, number> = {}
      for (const chat of chats) {
        const charId = String(chat.character_id ?? "")
        if (charId && characterIds.includes(charId)) {
          counts[charId] = (counts[charId] || 0) + 1
        }
      }
      return counts
    },
    enabled: characterIds.length > 0,
    staleTime: 60 * 1000 // Cache for 1 minute
  })

  const {
    data: previewCharacterWorldBooks = [],
    isFetching: previewCharacterWorldBooksLoading
  } = useQuery<Array<{ id: number; name: string }>>({
    queryKey: ["tldw:characterPreviewWorldBooks", previewCharacterId],
    queryFn: async () => {
      if (previewCharacterId == null) return []
      await tldwClient.initialize()
      const linkedBooks = await tldwClient.listCharacterWorldBooks(previewCharacterId)
      const parsed = Array.isArray(linkedBooks) ? linkedBooks : []
      return parsed
        .map((book: any) => {
          const worldBookId = Number(book?.world_book_id ?? book?.id)
          if (!Number.isFinite(worldBookId) || worldBookId <= 0) return null
          const rawName = book?.world_book_name ?? book?.name
          const worldBookName =
            typeof rawName === "string" && rawName.trim().length > 0
              ? rawName
              : `World Book ${worldBookId}`
          return { id: worldBookId, name: worldBookName }
        })
        .filter((book): book is { id: number; name: string } => book !== null)
        .sort((a, b) => a.name.localeCompare(b.name))
    },
    enabled: previewCharacterId != null,
    staleTime: 30 * 1000
  })

  const data = React.useMemo(
    () => {
      if (!isLegacyCharacterListResponse || !hasConversationsOnly) {
        return rawData
      }
      return rawData.filter((record: any) => {
        const charId = String(record?.id || record?.slug || record?.name || "")
        const mappedCount =
          typeof conversationCounts?.[charId] === "number"
            ? conversationCounts[charId]
            : undefined
        const inlineCountCandidates = [
          record?.conversation_count,
          record?.conversationCount,
          record?.chat_count,
          record?.chatCount
        ]
        const inlineCount = inlineCountCandidates.find(
          (value) => typeof value === "number" && Number.isFinite(value)
        ) as number | undefined
        return (mappedCount ?? inlineCount ?? 0) > 0
      })
    },
    [
      conversationCounts,
      hasConversationsOnly,
      isLegacyCharacterListResponse,
      rawData
    ]
  )

  React.useEffect(() => {
    if (hasHandledFocusCharacterRef.current) return
    const focusCharacterId = crossNavigationContext.focusCharacterId.trim()
    if (!focusCharacterId) {
      hasHandledFocusCharacterRef.current = true
      return
    }
    if (status !== "success") return

    const matchingCharacter = (data || []).find((character: any) => {
      const candidates = [
        character?.id,
        character?.slug,
        character?.name
      ]
      return candidates.some(
        (candidate) => String(candidate || "").trim() === focusCharacterId
      )
    })

    hasHandledFocusCharacterRef.current = true
    if (matchingCharacter) {
      setPreviewCharacter(matchingCharacter)
    }
  }, [crossNavigationContext.focusCharacterId, data, status])
  const totalCharacters = React.useMemo(
    () => (isLegacyCharacterListResponse ? data.length : rawTotalCharacters),
    [data.length, isLegacyCharacterListResponse, rawTotalCharacters]
  )

  React.useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(totalCharacters / pageSize))
    if (currentPage > maxPage) {
      setCurrentPage(maxPage)
    }
  }, [totalCharacters, currentPage, pageSize])

  const pagedGalleryData = data

  // Tag usage data with counts for M3 improvements
  const tagUsageData = React.useMemo(() => {
    const source = Array.isArray(data) ? data : []
    return buildTagUsage(source)
  }, [data])

  const allTags = React.useMemo(() => {
    return tagUsageData.map(({ tag }) => tag)
  }, [tagUsageData])

  // Popular tags (top 5 most used)
  const popularTags = React.useMemo(() => {
    return tagUsageData.slice(0, 5)
  }, [tagUsageData])

  // Tag options with usage counts for Select dropdown
  const tagOptionsWithCounts = React.useMemo(() => {
    return tagUsageData.map(({ tag, count }) => ({
      label: (
        <span className="flex items-center justify-between w-full">
          <span>{tag}</span>
          <span className="text-xs text-text-subtle ml-2">({count})</span>
        </span>
      ),
      value: tag
    }))
  }, [tagUsageData])

  const tagManagerTagUsageData = React.useMemo(
    () => buildTagUsage(tagManagerCharacters),
    [tagManagerCharacters]
  )

  const tagFilterOptions = React.useMemo(
    () =>
      Array.from(
        new Set([...(allTags || []), ...(filterTags || [])].filter(Boolean))
      ).map((tag) => ({ label: tag, value: tag })),
    [allTags, filterTags]
  )

  const creatorFilterOptions = React.useMemo(() => {
    const source = Array.isArray(data) ? data : []
    const creators = Array.from(
      new Set(
        source
          .map((character: any) =>
            String(
              character?.creator ?? character?.created_by ?? character?.createdBy ?? ""
            ).trim()
          )
          .filter((creator) => creator.length > 0)
      )
    ).sort((a, b) => a.localeCompare(b))
    return creators.map((creator) => ({ label: creator, value: creator }))
  }, [data])

  const { mutate: createCharacter, isPending: creating } = useMutation({
    mutationFn: async (values: any) =>
      tldwClient.createCharacter(buildCharacterPayload(values)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setOpen(false)
      createForm.resetFields()
      clearCreateDraft()
      setShowTemplates(false)
      setShowCreateSystemPromptExample(false)
      notification.success({
        message: t("settings:manageCharacters.notification.addSuccess", {
          defaultValue: "Character created"
        })
      })
      setTimeout(() => {
        newButtonRef.current?.focus()
      }, 0)
    },
    onError: (e: any) =>
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
  })
  React.useEffect(() => {
    if (open) {
      setTimeout(() => {
        createNameRef.current?.focus()
      }, 0)
    }
  }, [open])

  React.useEffect(() => {
    if (openEdit) {
      setTimeout(() => {
        editNameRef.current?.focus()
      }, 0)
    }
  }, [openEdit])

  React.useEffect(() => {
    if (!conversationsOpen || !conversationCharacter) return
    let cancelled = false
    const load = async () => {
      setLoadingChats(true)
      setChatsError(null)
      setCharacterChats([])
      try {
        await tldwClient.initialize()
        const characterId = characterIdentifier(conversationCharacter)
        const chats = await tldwClient.listChats({
          character_id: characterId || undefined,
          limit: 100,
          ordering: "-updated_at"
        })
        if (!cancelled) {
          const filtered = Array.isArray(chats)
            ? chats.filter(
                (c) =>
                  characterId &&
                  String(c.character_id ?? "") === String(characterId)
              )
            : []
          setCharacterChats(filtered)
        }
      } catch {
        if (!cancelled) {
          setChatsError(
            t("settings:manageCharacters.conversations.error", {
              defaultValue:
                "Unable to load conversations for this character."
            })
          )
        }
      } finally {
        if (!cancelled) {
          setLoadingChats(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [conversationsOpen, conversationCharacter, t])

  const { mutate: updateCharacter, isPending: updating } = useMutation({
    mutationFn: async (values: any) => {
      if (!editId) {
        throw new Error("No character selected for editing")
      }
      return await tldwClient.updateCharacter(
        editId,
        buildCharacterPayload(values),
        editVersion ?? undefined
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setOpenEdit(false)
      editForm.resetFields()
      setEditId(null)
      clearEditDraft()
      setShowEditSystemPromptExample(false)
      notification.success({
        message: t("settings:manageCharacters.notification.updatedSuccess", {
          defaultValue: "Character updated"
        })
      })
      setTimeout(() => {
        lastEditTriggerRef.current?.focus()
      }, 0)
    },
    onError: (e: any) =>
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
  })

  // Inline edit mutation (M1)
  const { mutate: inlineUpdateCharacter, isPending: inlineUpdating } = useMutation({
    mutationFn: async ({ id, field, value, version }: { id: string; field: 'name' | 'description'; value: string; version?: number }) => {
      return await tldwClient.updateCharacter(id, { [field]: value }, version)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      setInlineEdit(null)
      restoreInlineEditFocus()
    },
    onError: (e: any) => {
      notification.error({
        message: t("settings:manageCharacters.notification.error", { defaultValue: "Error" }),
        description: e?.message || t("settings:manageCharacters.notification.someError", { defaultValue: "Something went wrong" })
      })
    }
  })

  // Inline edit handlers (M1)
  const startInlineEdit = React.useCallback((
    record: any,
    field: 'name' | 'description',
    trigger?: HTMLElement | null
  ) => {
    const id = String(record.id || record.slug || record.name)
    const value = record[field] || ''
    if (trigger) {
      inlineEditTriggerRef.current = trigger
    }
    inlineEditFocusKeyRef.current = `${id}:${field}`
    setInlineEdit({ id, field, value, originalValue: value })
    setTimeout(() => inlineEditInputRef.current?.focus(), 0)
  }, [])

  const saveInlineEdit = React.useCallback(() => {
    if (!inlineEdit) return
    const trimmedValue = inlineEdit.value.trim()

    // Validate name field
    if (inlineEdit.field === 'name' && !trimmedValue) {
      notification.warning({
        message: t("settings:manageCharacters.form.name.required", { defaultValue: "Please enter a name" })
      })
      return
    }

    // Skip if unchanged
    if (trimmedValue === inlineEdit.originalValue) {
      setInlineEdit(null)
      return
    }

    // Find the record to get version
    const record = (data || []).find((c: any) =>
      String(c.id || c.slug || c.name) === inlineEdit.id
    )

    inlineUpdateCharacter({
      id: inlineEdit.id,
      field: inlineEdit.field,
      value: trimmedValue,
      version: record?.version
    })
  }, [inlineEdit, inlineUpdateCharacter, data, notification, t])

  const cancelInlineEdit = React.useCallback(() => {
    setInlineEdit(null)
    restoreInlineEditFocus()
  }, [restoreInlineEditFocus])

  // Bulk selection helpers (M5)
  const toggleCharacterSelection = React.useCallback((id: string) => {
    setSelectedCharacterIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const selectAllOnPage = React.useCallback(() => {
    if (!Array.isArray(data)) return
    const pageIds = data.map((c: any) => String(c.id || c.slug || c.name))
    setSelectedCharacterIds((prev) => new Set([...prev, ...pageIds]))
  }, [data])

  const clearSelection = React.useCallback(() => {
    setSelectedCharacterIds(new Set())
  }, [])

  const selectedCount = selectedCharacterIds.size
  const hasSelection = selectedCount > 0

  // Check if all items on current page are selected
  const allOnPageSelected = React.useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return false
    const pageIds = data.map((c: any) => String(c.id || c.slug || c.name))
    return pageIds.length > 0 && pageIds.every((id) => selectedCharacterIds.has(id))
  }, [data, selectedCharacterIds])

  const someOnPageSelected = React.useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return false
    const pageIds = data.map((c: any) => String(c.id || c.slug || c.name))
    const selectedOnPage = pageIds.filter((id) => selectedCharacterIds.has(id)).length
    return selectedOnPage > 0 && selectedOnPage < pageIds.length
  }, [data, selectedCharacterIds])

  // Clear selection when the active query/page changes
  React.useEffect(() => {
    setSelectedCharacterIds(new Set())
  }, [
    characterListScope,
    creatorFilter,
    currentPage,
    debouncedSearchTerm,
    filterTags,
    hasConversationsOnly,
    matchAllTags,
    pageSize,
    sortColumn,
    sortOrder
  ])

  const restoreBulkDeletedCharacters = React.useCallback(
    async (deletedCharacters: Array<{ id: string; version?: number }>) => {
      let restoredCount = 0
      let failedCount = 0

      for (const deletedCharacter of deletedCharacters) {
        try {
          await tldwClient.restoreCharacter(
            deletedCharacter.id,
            (deletedCharacter.version ?? 0) + 1
          )
          restoredCount++
        } catch {
          failedCount++
        }
      }

      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

      if (failedCount === 0) {
        emitCharacterRecoveryTelemetry("bulk_restore", {
          restored_count: restoredCount
        })
        notification.success({
          message: t("settings:manageCharacters.bulk.restoreSuccess", {
            defaultValue: "Restored {{count}} characters",
            count: restoredCount
          })
        })
      } else {
        emitCharacterRecoveryTelemetry("bulk_restore_failed", {
          restored_count: restoredCount,
          failed_count: failedCount
        })
        notification.warning({
          message: t("settings:manageCharacters.bulk.restorePartial", {
            defaultValue: "Restored {{success}} characters, {{fail}} failed",
            success: restoredCount,
            fail: failedCount
          })
        })
      }
    },
    [notification, qc, t]
  )

  // Bulk delete handler
  const handleBulkDelete = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0) return

    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    const ok = await confirmDanger({
      title: t("settings:manageCharacters.bulk.deleteTitle", {
        defaultValue: "Delete {{count}} characters?",
        count: selectedChars.length
      }),
      content: t("settings:manageCharacters.bulk.deleteContent", {
        defaultValue:
          "This will soft-delete {{count}} characters. You can undo for 10 seconds.",
        count: selectedChars.length
      }),
      okText: t("common:delete", { defaultValue: "Delete" }),
      cancelText: t("common:cancel", { defaultValue: "Cancel" })
    })

    if (!ok) return

    setBulkOperationLoading(true)
    const deletedCharacters: Array<{ id: string; version?: number }> = []
    let successCount = 0
    let failCount = 0

    for (const char of selectedChars) {
      try {
        const id = String(char.id || char.slug || char.name)
        await tldwClient.deleteCharacter(id, char.version)
        deletedCharacters.push({ id, version: char.version })
        successCount++
      } catch {
        failCount++
      }
    }

    setBulkOperationLoading(false)
    setSelectedCharacterIds(new Set())
    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

    if (successCount > 0) {
      emitCharacterRecoveryTelemetry("bulk_delete", {
        deleted_count: successCount,
        failed_count: failCount
      })
      if (bulkUndoDeleteRef.current) {
        clearTimeout(bulkUndoDeleteRef.current)
        bulkUndoDeleteRef.current = null
      }

      const timeoutId = setTimeout(() => {
        bulkUndoDeleteRef.current = null
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      }, 10000)
      bulkUndoDeleteRef.current = timeoutId

      notification.info({
        message:
          failCount === 0
            ? t("settings:manageCharacters.bulk.deleteSuccess", {
                defaultValue: "Deleted {{count}} characters",
                count: successCount
              })
            : t("settings:manageCharacters.bulk.deletePartial", {
                defaultValue: "Deleted {{success}} characters, {{fail}} failed",
                success: successCount,
                fail: failCount
              }),
        description: (
          <button
            type="button"
            className="mt-1 text-sm font-medium text-primary hover:underline"
            onClick={() => {
              if (bulkUndoDeleteRef.current) {
                clearTimeout(bulkUndoDeleteRef.current)
                bulkUndoDeleteRef.current = null
              }
              emitCharacterRecoveryTelemetry("bulk_undo", {
                deleted_count: deletedCharacters.length
              })
              void restoreBulkDeletedCharacters(deletedCharacters)
            }}>
            {t("common:undo", { defaultValue: "Undo" })}
          </button>
        ),
        duration: 10
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.deleteFailure", {
          defaultValue: "Unable to delete selected characters"
        })
      })
    }
  }, [
    selectedCharacterIds,
    data,
    confirmDanger,
    t,
    notification,
    qc,
    restoreBulkDeletedCharacters
  ])

  // Bulk export handler
  const handleBulkExport = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0) return

    setBulkOperationLoading(true)
    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    const exportedCharacters: any[] = []
    let failCount = 0

    for (const char of selectedChars) {
      try {
        const exported = await tldwClient.exportCharacter(
          String(char.id || char.slug || char.name),
          { format: 'v3' }
        )
        exportedCharacters.push(exported)
      } catch {
        failCount++
      }
    }

    if (exportedCharacters.length > 0) {
      // Use the new export utility
      exportCharactersToJSON(exportedCharacters)
    }

    setBulkOperationLoading(false)

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.bulk.exportSuccess", {
          defaultValue: "Exported {{count}} characters",
          count: exportedCharacters.length
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.exportPartial", {
          defaultValue: "Exported {{success}} characters, {{fail}} failed",
          success: exportedCharacters.length,
          fail: failCount
        })
      })
    }
  }, [selectedCharacterIds, data, notification, t])

  // Bulk add tags handler
  const handleBulkAddTags = React.useCallback(async () => {
    if (selectedCharacterIds.size === 0 || bulkTagsToAdd.length === 0) return

    setBulkOperationLoading(true)
    const selectedChars = (data || []).filter((c: any) =>
      selectedCharacterIds.has(String(c.id || c.slug || c.name))
    )

    let successCount = 0
    let failCount = 0

    for (const char of selectedChars) {
      try {
        const existingTags: string[] = Array.isArray(char.tags) ? char.tags : []
        const newTags = [...new Set([...existingTags, ...bulkTagsToAdd])]
        await tldwClient.updateCharacter(
          String(char.id || char.slug || char.name),
          { tags: newTags },
          char.version
        )
        successCount++
      } catch {
        failCount++
      }
    }

    setBulkOperationLoading(false)
    setBulkTagModalOpen(false)
    setBulkTagsToAdd([])
    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.bulk.tagSuccess", {
          defaultValue: "Added tags to {{count}} characters",
          count: successCount
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.bulk.tagPartial", {
          defaultValue: "Added tags to {{success}} characters, {{fail}} failed",
          success: successCount,
          fail: failCount
        })
      })
    }
  }, [selectedCharacterIds, data, bulkTagsToAdd, notification, t, qc])

  const loadTagManagerCharacters = React.useCallback(async () => {
    setTagManagerLoading(true)
    try {
      await tldwClient.initialize()
      const allCharacters: any[] = []
      let page = 1
      const maxPages = 50

      while (page <= maxPages) {
        const response = await tldwClient.listCharactersPage({
          page,
          page_size: 100,
          sort_by: "name",
          sort_order: "asc",
          include_image_base64: false
        })
        const pageItems = Array.isArray(response?.items) ? response.items : []
        allCharacters.push(...pageItems)
        if (!response?.has_more || pageItems.length === 0) break
        page += 1
      }

      setTagManagerCharacters(allCharacters)
    } catch (e: any) {
      notification.error({
        message: t("settings:manageCharacters.tags.manageLoadErrorTitle", {
          defaultValue: "Couldn't load tags"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.tags.manageLoadErrorDescription", {
            defaultValue: "Unable to load tags right now. Please try again."
          })
      })
    } finally {
      setTagManagerLoading(false)
    }
  }, [notification, t])

  const openTagManager = React.useCallback(() => {
    setTagManagerOpen(true)
    setTagManagerOperation("rename")
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")
    void loadTagManagerCharacters()
  }, [loadTagManagerCharacters])

  const closeTagManager = React.useCallback(() => {
    setTagManagerOpen(false)
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")
    setTagManagerCharacters([])
  }, [])

  const handleApplyTagManagerOperation = React.useCallback(async () => {
    const sourceTag = String(tagManagerSourceTag || "").trim()
    const targetTag = tagManagerTargetTag.trim()

    if (!sourceTag) {
      notification.warning({
        message: t("settings:manageCharacters.tags.selectSource", {
          defaultValue: "Select a tag to modify."
        })
      })
      return
    }

    if (
      (tagManagerOperation === "rename" || tagManagerOperation === "merge") &&
      targetTag.length === 0
    ) {
      notification.warning({
        message: t("settings:manageCharacters.tags.enterTarget", {
          defaultValue: "Enter a destination tag."
        })
      })
      return
    }

    if (
      (tagManagerOperation === "rename" || tagManagerOperation === "merge") &&
      sourceTag === targetTag
    ) {
      notification.info({
        message: t("settings:manageCharacters.tags.sourceEqualsTarget", {
          defaultValue: "Source and destination tags are the same."
        })
      })
      return
    }

    if (tagManagerOperation === "delete") {
      const confirmed = await confirmDanger({
        title: t("settings:manageCharacters.tags.deleteConfirmTitle", {
          defaultValue: "Delete tag '{{tag}}'?",
          tag: sourceTag
        }),
        content: t("settings:manageCharacters.tags.deleteConfirmContent", {
          defaultValue:
            "This removes the tag from every character that currently uses it."
        }),
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" })
      })
      if (!confirmed) return
    }

    const affectedCharacters = tagManagerCharacters.filter((character) =>
      characterHasTag(character, sourceTag)
    )

    if (affectedCharacters.length === 0) {
      notification.info({
        message: t("settings:manageCharacters.tags.noAffectedCharacters", {
          defaultValue: "No characters currently use that tag."
        })
      })
      return
    }

    setTagManagerSubmitting(true)
    let successCount = 0
    let failCount = 0

    try {
      for (const character of affectedCharacters) {
        const characterId = String(
          character?.id || character?.slug || character?.name || ""
        )
        if (!characterId) {
          failCount++
          continue
        }

        const currentTags = parseCharacterTags(character?.tags)
        const nextTags = applyTagOperationToTags(
          currentTags,
          tagManagerOperation,
          sourceTag,
          targetTag
        )

        const unchanged =
          currentTags.length === nextTags.length &&
          currentTags.every((tag, index) => tag === nextTags[index])

        if (unchanged) {
          continue
        }

        try {
          await tldwClient.updateCharacter(
            characterId,
            { tags: nextTags },
            character?.version
          )
          successCount++
        } catch {
          failCount++
        }
      }
    } finally {
      setTagManagerSubmitting(false)
    }

    qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
    await loadTagManagerCharacters()
    setTagManagerSourceTag(undefined)
    setTagManagerTargetTag("")

    if (failCount === 0) {
      notification.success({
        message: t("settings:manageCharacters.tags.manageSuccess", {
          defaultValue: "Updated tags on {{count}} characters.",
          count: successCount
        })
      })
    } else {
      notification.warning({
        message: t("settings:manageCharacters.tags.managePartial", {
          defaultValue: "Updated {{success}} characters, {{fail}} failed.",
          success: successCount,
          fail: failCount
        })
      })
    }
  }, [
    confirmDanger,
    loadTagManagerCharacters,
    notification,
    qc,
    tagManagerCharacters,
    tagManagerOperation,
    tagManagerSourceTag,
    tagManagerTargetTag,
    t
  ])

  // State for undo delete functionality
  const [pendingDelete, setPendingDelete] = React.useState<{
    character: any
    timeoutId: ReturnType<typeof setTimeout>
  } | null>(null)
  const undoDeleteRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const bulkUndoDeleteRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  const { mutate: deleteCharacter, isPending: deleting } = useMutation({
    mutationFn: async ({ id, expectedVersion }: { id: string; expectedVersion?: number }) =>
      tldwClient.deleteCharacter(id, expectedVersion),
    onSuccess: (_data, _variables, context: any) => {
      // Don't invalidate immediately - wait for undo timeout
      // The character is already removed from UI optimistically
    },
    onError: (e: any, _variables, context: any) => {
      // Restore character to list on error
      if (context?.character) {
        qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      }
      notification.error({
        message: t("settings:manageCharacters.notification.error", {
          defaultValue: "Error"
        }),
        description:
          e?.message ||
          t("settings:manageCharacters.notification.someError", {
            defaultValue: "Something went wrong. Please try again later"
          })
      })
    }
  })

  const { mutate: restoreCharacter } = useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      tldwClient.restoreCharacter(id, version),
    onSuccess: (_data, variables) => {
      emitCharacterRecoveryTelemetry("restore", {
        character_id: variables?.id ?? null
      })
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      notification.success({
        message: t("settings:manageCharacters.notification.restored", {
          defaultValue: "Character restored"
        })
      })
    },
    onError: (e: any) => {
      emitCharacterRecoveryTelemetry("restore_failed", {
        reason: e?.message ?? "unknown_error"
      })
      qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
      const detail = sanitizeServerErrorMessage(
        e,
        t("settings:manageCharacters.notification.restoreErrorDetail", {
          defaultValue: "Try refreshing the list and restoring again."
        })
      )
      notification.error({
        message: t("settings:manageCharacters.notification.restoreError", {
          defaultValue: "Failed to restore character"
        }),
        description: `${detail} ${buildServerLogHint(
          e,
          t("settings:manageCharacters.notification.restoreLogHint", {
            defaultValue: "If this keeps happening, check server logs."
          })
        )}`
      })
    }
  })

  const [exporting, setExporting] = React.useState<string | null>(null)
  const handleExport = React.useCallback(async (record: any, format: 'json' | 'png' = 'json') => {
    const id = record.id || record.slug || record.name
    const name = record.name || record.title || record.slug || "character"
    try {
      setExporting(id)
      const data = await tldwClient.exportCharacter(id, { format: 'v3' })

      if (format === 'png') {
        // Export as PNG with embedded metadata
        await exportCharacterToPNG(data, {
          avatarUrl: record.avatar_url,
          avatarBase64: record.image_base64,
          filename: `${name.replace(/[^a-z0-9]/gi, '_')}_character.png`
        })
      } else {
        // Export as JSON
        exportCharacterToJSON(data, `${name.replace(/[^a-z0-9]/gi, '_')}_character.json`)
      }

      notification.success({
        message: t("settings:manageCharacters.notification.exported", {
          defaultValue: "Character exported"
        })
      })
    } catch (e: any) {
      notification.error({
        message: t("settings:manageCharacters.notification.exportError", {
          defaultValue: "Failed to export character"
        }),
        description: e?.message
      })
    } finally {
      setExporting(null)
    }
  }, [notification, t])

  // Extracted action handlers for reuse between table and gallery views
  const handleChat = React.useCallback((record: any) => {
    setSelectedCharacter(buildCharacterSelectionPayload(record))
    navigate("/")
    setTimeout(() => {
      focusComposer()
    }, 0)
  }, [setSelectedCharacter, navigate])

  const openQuickChat = React.useCallback((record: any) => {
    const characterSelection = buildCharacterSelectionPayload(record)
    setQuickChatCharacter(record)
    setQuickChatDraft("")
    setQuickChatError(null)
    setQuickChatSessionId(null)
    const greeting = characterSelection.greeting?.trim()
    setQuickChatMessages(
      greeting
        ? [
            {
              id: makeQuickChatMessageId(),
              role: "assistant",
              content: greeting,
              timestamp: Date.now()
            }
          ]
        : []
    )
  }, [])

  const sendQuickChatMessage = React.useCallback(async () => {
    const trimmed = quickChatDraft.trim()
    if (!trimmed || quickChatSending || !quickChatCharacter) return
    if (!activeQuickChatModel) {
      setQuickChatError(
        t("settings:manageCharacters.quickChat.modelRequired", {
          defaultValue: "Select a model to start quick chat."
        })
      )
      return
    }

    const userMessage: CharacterQuickChatMessage = {
      id: makeQuickChatMessageId(),
      role: "user",
      content: trimmed,
      timestamp: Date.now()
    }

    const nextHistory = [...quickChatMessages, userMessage]
    setQuickChatMessages(nextHistory)
    setQuickChatDraft("")
    setQuickChatSending(true)
    setQuickChatError(null)

    try {
      let sessionId = quickChatSessionId
      if (!sessionId) {
        const characterId = resolveCharacterNumericId(quickChatCharacter)
        if (!characterId) {
          throw new Error(
            t("settings:manageCharacters.quickChat.unsupportedCharacter", {
              defaultValue:
                "Quick chat is only available for server-synced characters."
            })
          )
        }
        const created = await tldwClient.createChat({
          character_id: characterId,
          state: "in-progress",
          source: "characters-quick-chat",
          title: t("settings:manageCharacters.quickChat.sessionTitle", {
            defaultValue: "{{name}} quick chat",
            name:
              quickChatCharacter?.name ||
              quickChatCharacter?.title ||
              quickChatCharacter?.slug ||
              t("settings:manageCharacters.preview.untitled", {
                defaultValue: "Untitled character"
              })
          })
        })
        const rawId = (created as any)?.id ?? (created as any)?.chat_id ?? created
        sessionId = rawId != null ? String(rawId) : ""
        if (!sessionId) {
          throw new Error(
            t("settings:manageCharacters.quickChat.sessionCreateFailed", {
              defaultValue: "Unable to start a quick chat session."
            })
          )
        }
        setQuickChatSessionId(sessionId)
      }

      const payload = await tldwClient.completeCharacterChatTurn(sessionId, {
        append_user_message: trimmed,
        include_character_context: true,
        limit: 100,
        save_to_db: true,
        stream: false,
        model: activeQuickChatModel
      })
      const assistantContent =
        (typeof payload?.assistant_content === "string"
          ? payload.assistant_content
          : typeof payload?.content === "string"
            ? payload.content
            : typeof payload?.text === "string"
              ? payload.text
              : ""
        ).trim()

      if (!assistantContent) {
        throw new Error(
          t("settings:manageCharacters.quickChat.emptyResponse", {
            defaultValue: "No response received from the model."
          })
        )
      }

      setQuickChatMessages((previous) => [
        ...previous,
        {
          id: makeQuickChatMessageId(),
          role: "assistant",
          content: assistantContent,
          timestamp: Date.now()
        }
      ])
    } catch (error: any) {
      const message =
        error?.message ||
        t("settings:manageCharacters.quickChat.error", {
          defaultValue: "Quick chat failed. Please try again."
        })
      setQuickChatError(message)
    } finally {
      setQuickChatSending(false)
    }
  }, [
    activeQuickChatModel,
    quickChatCharacter,
    quickChatDraft,
    quickChatMessages,
    quickChatSessionId,
    quickChatSending,
    t
  ])

  const handlePromoteQuickChat = React.useCallback(async () => {
    if (!quickChatCharacter) return

    const characterSelection = buildCharacterSelectionPayload(quickChatCharacter)
    setSelectedCharacter(characterSelection)

    const assistantName =
      characterSelection.name ||
      t("common:assistant", {
        defaultValue: "Assistant"
      })
    const history = quickChatMessages.map((message) => ({
      role: message.role,
      content: message.content
    }))
    const mappedMessages = quickChatMessages.map((message) => ({
      createdAt: message.timestamp,
      isBot: message.role === "assistant",
      role: message.role,
      name:
        message.role === "assistant"
          ? assistantName
          : t("common:you", { defaultValue: "You" }),
      message: message.content,
      sources: [],
      images: []
    }))

    setHistoryId(null)
    setServerChatId(quickChatSessionId)
    setServerChatState("in-progress")
    setServerChatTopic(null)
    setServerChatClusterId(null)
    setServerChatSource("characters-quick-chat")
    setServerChatExternalRef(null)
    setHistory(history)
    setMessages(mappedMessages)

    await closeQuickChat({ preserveSession: true })
    navigate("/")
    setTimeout(() => {
      focusComposer()
    }, 0)
  }, [
    closeQuickChat,
    navigate,
    quickChatCharacter,
    quickChatMessages,
    quickChatSessionId,
    setHistory,
    setHistoryId,
    setMessages,
    setSelectedCharacter,
    setServerChatClusterId,
    setServerChatExternalRef,
    setServerChatId,
    setServerChatSource,
    setServerChatState,
    setServerChatTopic,
    t
  ])

  const handleEdit = React.useCallback((record: any, triggerRef?: HTMLButtonElement | null) => {
    if (triggerRef) {
      lastEditTriggerRef.current = triggerRef
    }
    setEditId(record.id || record.slug || record.name)
    setEditVersion(record?.version ?? null)
    const ex = record.extensions
    const extensionsValue =
      ex && typeof ex === "object" && !Array.isArray(ex)
        ? JSON.stringify(ex, null, 2)
        : typeof ex === "string"
          ? ex
          : ""
    const promptPreset = readPromptPresetFromExtensions(record.extensions)
    const defaultAuthorNote = readDefaultAuthorNoteFromRecord(record)
    const generationSettings = readGenerationSettingsFromRecord(record)
    editForm.setFieldsValue({
      name: record.name,
      description: record.description,
      avatar: createAvatarValue(record.avatar_url, record.image_base64),
      tags: record.tags,
      greeting:
        record.greeting ||
        record.first_message ||
        record.greet,
      system_prompt: record.system_prompt,
      personality: record.personality,
      scenario: record.scenario,
      post_history_instructions:
        record.post_history_instructions,
      message_example: record.message_example,
      creator_notes: record.creator_notes,
      alternate_greetings: normalizeAlternateGreetings(
        record.alternate_greetings
      ),
      creator: record.creator,
      character_version: record.character_version,
      prompt_preset: promptPreset,
      default_author_note: defaultAuthorNote,
      generation_temperature: generationSettings.temperature,
      generation_top_p: generationSettings.top_p,
      generation_repetition_penalty: generationSettings.repetition_penalty,
      generation_stop_strings: generationSettings.stop?.join("\n") || "",
      extensions: extensionsValue
    })
    setShowEditAdvanced(hasAdvancedData(record, extensionsValue))
    setOpenEdit(true)
  }, [editForm])

  const handleDuplicate = React.useCallback((record: any) => {
    const ex = record.extensions
    const extensionsValue =
      ex && typeof ex === "object" && !Array.isArray(ex)
        ? JSON.stringify(ex, null, 2)
        : typeof ex === "string"
          ? ex
          : ""
    const promptPreset = readPromptPresetFromExtensions(record.extensions)
    const defaultAuthorNote = readDefaultAuthorNoteFromRecord(record)
    const generationSettings = readGenerationSettingsFromRecord(record)
    createForm.setFieldsValue({
      name: `${record.name || ""} (copy)`,
      description: record.description,
      avatar: createAvatarValue(record.avatar_url, record.image_base64),
      tags: record.tags,
      greeting:
        record.greeting ||
        record.first_message ||
        record.greet,
      system_prompt: record.system_prompt,
      personality: record.personality,
      scenario: record.scenario,
      post_history_instructions:
        record.post_history_instructions,
      message_example: record.message_example,
      creator_notes: record.creator_notes,
      alternate_greetings: normalizeAlternateGreetings(
        record.alternate_greetings
      ),
      creator: record.creator,
      character_version: record.character_version,
      prompt_preset: promptPreset,
      default_author_note: defaultAuthorNote,
      generation_temperature: generationSettings.temperature,
      generation_top_p: generationSettings.top_p,
      generation_repetition_penalty: generationSettings.repetition_penalty,
      generation_stop_strings: generationSettings.stop?.join("\n") || "",
      extensions: extensionsValue
    })
    setShowCreateAdvanced(hasAdvancedData(record, extensionsValue))
    setOpen(true)

    // Show duplicate notification
    const name = record.name || record.title || record.slug || ""
    notification.info({
      message: t("settings:manageCharacters.notification.duplicated", {
        defaultValue: "Duplicated '{{name}}'. Editing copy.",
        name
      })
    })
  }, [createForm, notification, t])

  const handleDelete = React.useCallback(async (record: any) => {
    const name = record?.name || record?.title || record?.slug || ""
    const characterId = String(record.id || record.slug || record.name)
    const characterVersion = record.version

    // Clear any existing undo timeout
    if (undoDeleteRef.current) {
      clearTimeout(undoDeleteRef.current)
      undoDeleteRef.current = null
    }
    if (pendingDelete?.timeoutId) {
      clearTimeout(pendingDelete.timeoutId)
    }

    // Delete the character (soft delete on backend)
    deleteCharacter({ id: characterId, expectedVersion: characterVersion }, {
      onSuccess: () => {
        emitCharacterRecoveryTelemetry("delete", {
          character_id: characterId
        })
        // Create undo timeout - after 10 seconds, finalize delete
        const timeoutId = setTimeout(() => {
          setPendingDelete(null)
          undoDeleteRef.current = null
          // Refresh list to ensure consistency
          qc.invalidateQueries({ queryKey: ["tldw:listCharacters"] })
        }, 10000)

        undoDeleteRef.current = timeoutId
        setPendingDelete({ character: record, timeoutId })

        // Show undo notification
        notification.info({
          message: t("settings:manageCharacters.notification.deletedWithUndo", {
            defaultValue: "Character '{{name}}' deleted",
            name
          }),
          description: (
            <button
              type="button"
              className="mt-1 text-sm font-medium text-primary hover:underline"
              onClick={() => {
                // Cancel the timeout
                if (undoDeleteRef.current) {
                  clearTimeout(undoDeleteRef.current)
                  undoDeleteRef.current = null
                }
                setPendingDelete(null)
                emitCharacterRecoveryTelemetry("undo", {
                  character_id: characterId
                })

                // Restore the character
                // Version incremented by 1 after soft delete
                restoreCharacter({ id: characterId, version: (characterVersion ?? 0) + 1 })
              }}>
              {t("common:undo", { defaultValue: "Undo" })}
            </button>
          ),
          duration: 10
        })
      }
    })
  }, [deleteCharacter, notification, t, qc, pendingDelete, restoreCharacter])

  const handleViewConversations = React.useCallback((record: any) => {
    setConversationCharacter(record)
    setCharacterChats([])
    setChatsError(null)
    setConversationsOpen(true)
  }, [])

  const handleRestoreFromTrash = React.useCallback(
    (record: any) => {
      const characterId = String(record?.id || record?.slug || record?.name || "")
      const characterVersion = Number(record?.version)
      if (!characterId) return
      if (!Number.isFinite(characterVersion)) {
        notification.error({
          message: t("settings:manageCharacters.notification.restoreError", {
            defaultValue: "Failed to restore character"
          }),
          description: t("settings:manageCharacters.notification.restoreVersionMissing", {
            defaultValue: "Missing character version. Refresh and try again."
          })
        })
        return
      }
      restoreCharacter({ id: characterId, version: characterVersion })
    },
    [notification, restoreCharacter, t]
  )

  return (
    <div className="characters-page">
      <a
        href="#characters-main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:border focus:border-border focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-text focus:shadow">
        {t("settings:manageCharacters.skipToContent", {
          defaultValue: "Skip to characters content"
        })}
      </a>
      <div
        id="characters-main-content"
        role="main"
        tabIndex={-1}
        aria-describedby="characters-shortcuts-summary"
        className="space-y-4">
      <div id="characters-shortcuts-summary" className="sr-only">
        {`${t("settings:manageCharacters.shortcuts.title", {
          defaultValue: "Keyboard shortcuts"
        })}: ${shortcutSummaryText}`}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="primary"
            ref={newButtonRef}
            onClick={openCreateModal}>
            {t("settings:manageCharacters.addBtn", {
              defaultValue: "New character"
            })}
          </Button>
          <div ref={importButtonContainerRef}>
            <Upload
              accept={IMPORT_UPLOAD_ACCEPT}
              multiple
              showUploadList={false}
              beforeUpload={handleImportUpload}
              disabled={importing || importPreviewLoading}>
              <Button loading={importing || importPreviewLoading}>
                {t("settings:manageCharacters.import.button", {
                  defaultValue: "Upload character"
                })}
              </Button>
            </Upload>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <Tooltip title={t("settings:manageCharacters.search.shortcut", { defaultValue: "Press / to search" })}>
            <Input
              ref={searchInputRef}
              allowClear
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t(
                "settings:manageCharacters.search.placeholder",
                {
                  defaultValue: "Search characters"
                }
              )}
              aria-label={t("settings:manageCharacters.search.label", {
                defaultValue: "Search characters"
              })}
              className="sm:max-w-xs"
              suffix={<span className="text-xs text-text-subtle hidden sm:inline">/</span>}
            />
          </Tooltip>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center">
            <Segmented
              value={characterListScope}
              onChange={(value) =>
                setCharacterListScope(value as CharacterListScope)
              }
              options={[
                {
                  value: "active",
                  label: t("settings:manageCharacters.scope.active", {
                    defaultValue: "Active"
                  }),
                  title: t("settings:manageCharacters.scope.activeTitle", {
                    defaultValue: "Active characters"
                  })
                },
                {
                  value: "deleted",
                  label: t("settings:manageCharacters.scope.deleted", {
                    defaultValue: "Recently deleted"
                  }),
                  title: t("settings:manageCharacters.scope.deletedTitle", {
                    defaultValue: "Soft-deleted characters"
                  })
                }
              ]}
              aria-label={t("settings:manageCharacters.scope.label", {
                defaultValue: "Character list scope"
              })}
            />
            <Select
              mode="multiple"
              allowClear
              className="min-w-[12rem]"
              placeholder={t(
                "settings:manageCharacters.filter.tagsPlaceholder",
                {
                  defaultValue: "Filter by tags"
                }
              )}
              aria-label={t(
                "settings:manageCharacters.filter.tagsAriaLabel",
                {
                  defaultValue: "Filter characters by tags"
                }
              )}
              value={filterTags}
              options={tagFilterOptions}
              onChange={(value) =>
                setFilterTags(
                  (value as string[]).filter((v) => v && v.trim().length > 0)
                )
              }
            />
            <Select
              allowClear
              className="min-w-[10rem]"
              placeholder={t("settings:manageCharacters.filter.creatorPlaceholder", {
                defaultValue: "Filter by creator"
              })}
              aria-label={t("settings:manageCharacters.filter.creatorAriaLabel", {
                defaultValue: "Filter characters by creator"
              })}
              value={creatorFilter}
              options={creatorFilterOptions}
              onChange={(value) => setCreatorFilter(value || undefined)}
            />
            <Checkbox
              checked={matchAllTags}
              onChange={(e) => setMatchAllTags(e.target.checked)}>
              {t("settings:manageCharacters.filter.matchAll", {
                defaultValue: "Match all tags"
              })}
            </Checkbox>
            <Checkbox
              checked={hasConversationsOnly}
              onChange={(e) => setHasConversationsOnly(e.target.checked)}>
              {t("settings:manageCharacters.filter.hasConversations", {
                defaultValue: "Has conversations"
              })}
            </Checkbox>
            {hasFilters && (
              <Button
                size="small"
                onClick={() => {
                  setSearchTerm("")
                  setFilterTags([])
                  setMatchAllTags(false)
                  setCreatorFilter(undefined)
                  setHasConversationsOnly(false)
                }}>
                {t("settings:manageCharacters.filter.clear", {
                  defaultValue: "Clear filters"
                })}
              </Button>
            )}
            <Button
              size="small"
              onClick={openTagManager}>
              {t("settings:manageCharacters.tags.manageButton", {
                defaultValue: "Manage tags"
              })}
            </Button>
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as 'table' | 'gallery')}
              disabled={characterListScope === "deleted"}
              options={[
                {
                  value: 'table',
                  icon: <List className="w-4 h-4" />,
                  title: t("settings:manageCharacters.viewMode.table", {
                    defaultValue: "Table view"
                  })
                },
                {
                  value: 'gallery',
                  icon: <LayoutGrid className="w-4 h-4" />,
                  title: t("settings:manageCharacters.viewMode.gallery", {
                    defaultValue: "Gallery view"
                  })
                }
              ]}
              aria-label={t("settings:manageCharacters.viewMode.label", {
                defaultValue: "View mode"
              })}
            />
            {viewMode === "gallery" && (
              <Segmented
                value={galleryDensity}
                onChange={(v) => setGalleryDensity(v as GalleryCardDensity)}
                options={[
                  {
                    value: "rich",
                    label: t("settings:manageCharacters.galleryDensity.rich", {
                      defaultValue: "Rich"
                    }),
                    title: t("settings:manageCharacters.galleryDensity.richTitle", {
                      defaultValue: "Rich gallery cards"
                    })
                  },
                  {
                    value: "compact",
                    label: t("settings:manageCharacters.galleryDensity.compact", {
                      defaultValue: "Compact"
                    }),
                    title: t("settings:manageCharacters.galleryDensity.compactTitle", {
                      defaultValue: "Compact gallery cards"
                    })
                  }
                ]}
                aria-label={t("settings:manageCharacters.galleryDensity.label", {
                  defaultValue: "Gallery card density"
                })}
              />
            )}
            {/* Keyboard shortcuts help (H1) */}
            <Tooltip
              title={
                <div className="text-xs space-y-1">
                  <div className="font-medium mb-1">{t("settings:manageCharacters.shortcuts.title", { defaultValue: "Keyboard shortcuts" })}</div>
                  {shortcutHelpItems.map((item) => (
                    <div key={item.id}>
                      {item.keys.map((key, index) => (
                        <React.Fragment key={`${item.id}-${key}-${index}`}>
                          {index > 0 && " "}
                          <kbd className="px-1 bg-white/20 rounded">{key}</kbd>
                        </React.Fragment>
                      ))}{" "}
                      {item.label}
                    </div>
                  ))}
                </div>
              }
              placement="bottomRight"
              trigger={["hover", "focus"]}
              classNames={{ root: "characters-motion-overlay" }}>
              <Button
                type="text"
                size="small"
                icon={<Keyboard className="w-4 h-4" />}
                aria-label={t("settings:manageCharacters.shortcuts.ariaLabel", { defaultValue: "Keyboard shortcuts" })}
                aria-describedby="characters-shortcuts-summary"
              />
            </Tooltip>
          </div>
        </div>
      </div>
      {/* Accessible live region for search results */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        role="status"
      >
        {status === "success" &&
          t("settings:manageCharacters.aria.searchResults", {
            defaultValue: "{{count}} characters found",
            count: totalCharacters
          })}
      </div>
      {status === "error" && (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4">
          <Alert
            type="error"
            title={t("settings:manageCharacters.loadError.title", {
              defaultValue: "Couldn't load characters"
            })}
            description={
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm text-danger">
                  <p>
                    {sanitizeServerErrorMessage(
                      error,
                      t("settings:manageCharacters.loadError.description", {
                        defaultValue: "Check your connection and try again."
                      })
                    )}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {buildServerLogHint(
                      error,
                      t("settings:manageCharacters.loadError.logHint", {
                        defaultValue:
                          "If the issue persists, check server logs for more details."
                      })
                    )}
                  </p>
                </div>
                <Button size="small" onClick={() => refetch()}>
                  {t("common:retry", { defaultValue: "Retry" })}
                </Button>
              </div>
            }
            showIcon
            className="border-0 bg-transparent p-0"
          />
        </div>
      )}
      {status === "pending" && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === "success" &&
        Array.isArray(data) &&
        data.length === 0 &&
        characterListScope === "active" &&
        !hasFilters && (
          <div className="space-y-3">
            <FeatureEmptyState
              icon={UserCircle2}
              title={t("settings:manageCharacters.emptyTitle", {
                defaultValue: "No characters yet"
              })}
              description={t("settings:manageCharacters.emptyDescription", {
                defaultValue:
                  "Create reusable personas you can chat with. Each character keeps its own conversation history."
              })}
              examples={[
                t("settings:manageCharacters.emptyExample.writingCoach", {
                  defaultValue: "Create a writing coach"
                }),
                t("settings:manageCharacters.emptyExample.sillytavernImport", {
                  defaultValue: "Import a SillyTavern card"
                }),
                t("settings:manageCharacters.emptyExample.interviewPrep", {
                  defaultValue: "Build an interview practice persona"
                })
              ]}
              primaryActionLabel={t(
                "settings:manageCharacters.emptyPrimaryCta",
                {
                  defaultValue: "Create character"
                }
              )}
              onPrimaryAction={openCreateModal}
              secondaryActionLabel={t("settings:manageCharacters.emptySecondaryCta", {
                defaultValue: "Import character"
              })}
              onSecondaryAction={triggerImportPicker}
              secondaryDisabled={importing || importPreviewLoading}
            />

            <div className="rounded-xl border border-border bg-surface p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-medium">
                  {t("settings:manageCharacters.emptyTemplates.title", {
                    defaultValue: "Start from a template"
                  })}
                </span>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setShowTemplates(true)
                    markTemplateChooserSeen()
                    openCreateModal()
                  }}>
                  {t("settings:manageCharacters.emptyTemplates.browseAll", {
                    defaultValue: "Browse all"
                  })}
                </Button>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {CHARACTER_TEMPLATES.slice(0, 3).map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    className="rounded border border-border p-2 text-left transition-colors motion-reduce:transition-none hover:border-primary hover:bg-surface-hover"
                    onClick={() => applyTemplateToCreateForm(template)}>
                    <div className="text-sm font-medium">{template.name}</div>
                    <div className="text-xs text-text-muted">{template.description}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      {status === "success" &&
        Array.isArray(data) &&
        data.length === 0 &&
        characterListScope === "deleted" &&
        !hasFilters && (
          <div className="rounded-lg border border-dashed border-border bg-surface p-4 text-sm text-text">
            <div className="flex flex-col gap-2">
              <span className="font-medium">
                {t("settings:manageCharacters.deletedEmptyTitle", {
                  defaultValue: "No recently deleted characters"
                })}
              </span>
              <span className="text-text-muted">
                {t("settings:manageCharacters.deletedEmptyDescription", {
                  defaultValue:
                    "Soft-deleted characters appear here for up to 30 days."
                })}
              </span>
              <div>
                <Button
                  size="small"
                  onClick={() => setCharacterListScope("active")}>
                  {t("settings:manageCharacters.scope.backToActive", {
                    defaultValue: "Back to active"
                  })}
                </Button>
              </div>
            </div>
          </div>
        )}
      {status === "success" &&
        Array.isArray(data) &&
        data.length === 0 &&
        hasFilters && (
          <div className="rounded-lg border border-dashed border-border bg-surface p-4 text-sm text-text">
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {t("settings:manageCharacters.filteredEmptyTitle", {
                    defaultValue: "No characters match your filters"
                  })}
                </span>
                <Button
                  size="small"
                  onClick={() => {
                    setSearchTerm("")
                    setFilterTags([])
                    setMatchAllTags(false)
                    setCreatorFilter(undefined)
                    setHasConversationsOnly(false)
                    refetch()
                  }}>
                  {t("settings:manageCharacters.filter.clear", {
                    defaultValue: "Clear filters"
                  })}
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-subtle">
                {searchTerm.trim() && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeSearch", {
                      defaultValue: "Search: \"{{term}}\"",
                      term: searchTerm.trim()
                    })}
                  </span>
                )}
                {filterTags.length > 0 && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeTags", {
                      defaultValue: "Tags: {{tags}}",
                      tags: filterTags.join(", ")
                    })}
                    {matchAllTags && (
                      <span className="text-text-subtle">
                        ({t("settings:manageCharacters.filter.matchAllLabel", { defaultValue: "all" })})
                      </span>
                    )}
                  </span>
                )}
                {creatorFilter && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeCreator", {
                      defaultValue: "Creator: {{creator}}",
                      creator: creatorFilter
                    })}
                  </span>
                )}
                {hasConversationsOnly && (
                  <span className="inline-flex items-center gap-1 rounded bg-surface2 px-2 py-0.5">
                    {t("settings:manageCharacters.filter.activeHasConversations", {
                      defaultValue: "Has conversations"
                    })}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      {status === "success" && Array.isArray(data) && data.length > 0 && viewMode === 'table' && (
        <div className="space-y-3">
          {characterListScope === "deleted" && (
            <div className="rounded-md border border-border bg-surface2 p-3 text-sm text-text-muted">
              {t("settings:manageCharacters.deletedListDescription", {
                defaultValue:
                  "Showing recently deleted characters. Restore them within 30 days."
              })}
            </div>
          )}
          {/* Bulk Actions Toolbar (M5) */}
          {characterListScope === "active" && hasSelection && (
            <div className="flex items-center gap-3 p-2 bg-surface rounded-lg border border-border">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">
                  {t("settings:manageCharacters.bulk.selected", {
                    defaultValue: "{{count}} selected",
                    count: selectedCount
                  })}
                </span>
              </div>
              <div className="flex items-center gap-2 ml-auto">
                <Tooltip title={t("settings:manageCharacters.bulk.addTags", { defaultValue: "Add tags" })}>
                  <Button
                    size="small"
                    icon={<Tags className="w-4 h-4" />}
                    onClick={() => setBulkTagModalOpen(true)}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.addTags", { defaultValue: "Add tags" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.export", { defaultValue: "Export" })}>
                  <Button
                    size="small"
                    icon={<Download className="w-4 h-4" />}
                    onClick={handleBulkExport}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.export", { defaultValue: "Export" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.delete", { defaultValue: "Delete" })}>
                  <Button
                    size="small"
                    danger
                    icon={<Trash2 className="w-4 h-4" />}
                    onClick={handleBulkDelete}
                    loading={bulkOperationLoading}>
                    {t("settings:manageCharacters.bulk.delete", { defaultValue: "Delete" })}
                  </Button>
                </Tooltip>
                <Tooltip title={t("settings:manageCharacters.bulk.clearSelection", { defaultValue: "Clear selection" })}>
                  <Button
                    size="small"
                    type="text"
                    icon={<X className="w-4 h-4" />}
                    onClick={clearSelection}
                    aria-label={t("settings:manageCharacters.bulk.clearSelection", { defaultValue: "Clear selection" })}
                  />
                </Tooltip>
              </div>
            </div>
          )}
          <div className="overflow-x-auto">
            <Table
              rowKey={(r: any) => r.id || r.slug || r.name}
              dataSource={data}
              pagination={{
                current: currentPage,
                pageSize,
                total: totalCharacters,
                showSizeChanger: true,
                pageSizeOptions: PAGE_SIZE_OPTIONS.map((size) => String(size)),
                onShowSizeChange: (_page, nextPageSize) => {
                  setPageSize(normalizePageSize(nextPageSize))
                  setCurrentPage(1)
                },
                onChange: (page, nextPageSize) => {
                  const normalizedNextPageSize = normalizePageSize(nextPageSize)
                  if (normalizedNextPageSize !== pageSize) {
                    setPageSize(normalizedNextPageSize)
                    setCurrentPage(1)
                    return
                  }
                  setCurrentPage(page)
                }
              }}
              onChange={(_pagination, _filters, sorter) => {
                // Handle sort state for persistence
                if (!Array.isArray(sorter)) {
                  const nextOrder = sorter.order || null
                  setSortOrder(nextOrder)
                  setSortColumn(nextOrder ? ((sorter.columnKey as string) || null) : null)
                }
              }}
              columns={[
              characterListScope === "active" ? {
                // Bulk selection checkbox column (M5)
                title: (
                  <Checkbox
                    checked={allOnPageSelected}
                    indeterminate={someOnPageSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        selectAllOnPage()
                      } else {
                        // Deselect all on current page
                        if (!Array.isArray(data)) return
                        const pageIds = data.map((c: any) => String(c.id || c.slug || c.name))
                        setSelectedCharacterIds((prev) => {
                          const next = new Set(prev)
                          pageIds.forEach((id) => next.delete(id))
                          return next
                        })
                      }
                    }}
                    aria-label={t("settings:manageCharacters.bulk.selectAll", { defaultValue: "Select all on page" })}
                  />
                ),
                key: "selection",
                width: 48,
                render: (_: any, record: any) => {
                  const recordId = String(record.id || record.slug || record.name)
                  return (
                    <Checkbox
                      checked={selectedCharacterIds.has(recordId)}
                      onChange={(e) => {
                        e.stopPropagation()
                        toggleCharacterSelection(recordId)
                      }}
                      aria-label={t("settings:manageCharacters.bulk.selectOne", {
                        defaultValue: "Select {{name}}",
                        name: record.name || recordId
                      })}
                    />
                  )
                }
              } : null,
              {
                title: (
                  <span className="sr-only">
                    {t("settings:manageCharacters.columns.avatar", {
                      defaultValue: "Avatar"
                    })}
                  </span>
                ),
              key: "avatar",
              width: 48,
              render: (_: any, record: any) =>
                record?.avatar_url ? (
                  <img
                    src={record.avatar_url}
                    loading="lazy"
                    decoding="async"
                    className="w-6 h-6 rounded-full"
                    alt={
                      record?.name
                        ? t("settings:manageCharacters.avatarAltWithName", {
                            defaultValue: "Avatar of {{name}}",
                            name: record.name
                          })
                        : t("settings:manageCharacters.avatarAlt", {
                            defaultValue: "User avatar"
                          })
                    }
                  />
                ) : (
                  <UserCircle2 className="w-5 h-5" />
                )
            },
            {
              title: t("settings:manageCharacters.columns.name", {
                defaultValue: "Name"
              }),
              dataIndex: "name",
              key: "name",
              sorter: true,
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "name" ? sortOrder : undefined,
              render: (v: string, record: any) => {
                const recordId = String(record.id || record.slug || record.name)
                const isEditing = inlineEdit?.id === recordId && inlineEdit?.field === 'name'

                if (characterListScope === "deleted") {
                  return (
                    <span className="line-clamp-1" title={v || undefined}>
                      {truncateText(v, MAX_NAME_LENGTH)}
                    </span>
                  )
                }

                if (isEditing) {
                  return (
                    <Input
                      ref={inlineEditInputRef}
                      size="small"
                      value={inlineEdit.value}
                      onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          saveInlineEdit()
                        } else if (e.key === 'Escape') {
                          cancelInlineEdit()
                        }
                      }}
                      onBlur={saveInlineEdit}
                      disabled={inlineUpdating}
                      className="max-w-[200px]"
                    />
                  )
                }

                return (
                  <Tooltip title={t("settings:manageCharacters.table.doubleClickEdit", { defaultValue: "Double-click to edit" })}>
                    <span
                      className="line-clamp-1 cursor-text hover:bg-surface-hover rounded px-1 -mx-1"
                      title={v || undefined}
                      data-inline-edit-key={`${recordId}:name`}
                      role="button"
                      tabIndex={0}
                      aria-label={t("settings:manageCharacters.table.inlineEditName", {
                        defaultValue: "Edit name inline for {{name}}",
                        name: v || record?.name || record?.slug || "character"
                      })}
                      onDoubleClick={(event) =>
                        startInlineEdit(record, 'name', event.currentTarget)
                      }
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === 'F2') {
                          event.preventDefault()
                          startInlineEdit(record, 'name', event.currentTarget)
                        }
                      }}
                    >
                      {truncateText(v, MAX_NAME_LENGTH)}
                    </span>
                  </Tooltip>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.description", {
                defaultValue: "Description"
              }),
              dataIndex: "description",
              key: "description",
              render: (v: string, record: any) => {
                const recordId = String(record.id || record.slug || record.name)
                const isEditing = inlineEdit?.id === recordId && inlineEdit?.field === 'description'

                if (characterListScope === "deleted") {
                  return (
                    <span className="line-clamp-1" title={v || undefined}>
                      {v ? (
                        truncateText(v, MAX_DESCRIPTION_LENGTH)
                      ) : (
                        <span className="text-text-subtle">
                          {t("settings:manageCharacters.table.noDescription", {
                            defaultValue: "—"
                          })}
                        </span>
                      )}
                    </span>
                  )
                }

                if (isEditing) {
                  return (
                    <Input
                      ref={inlineEditInputRef}
                      size="small"
                      value={inlineEdit.value}
                      onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          saveInlineEdit()
                        } else if (e.key === 'Escape') {
                          cancelInlineEdit()
                        }
                      }}
                      onBlur={saveInlineEdit}
                      disabled={inlineUpdating}
                      className="max-w-[250px]"
                    />
                  )
                }

                return (
                  <Tooltip title={t("settings:manageCharacters.table.doubleClickEdit", { defaultValue: "Double-click to edit" })}>
                    <span
                      className="line-clamp-1 cursor-text hover:bg-surface-hover rounded px-1 -mx-1"
                      title={v || undefined}
                      data-inline-edit-key={`${recordId}:description`}
                      role="button"
                      tabIndex={0}
                      aria-label={t("settings:manageCharacters.table.inlineEditDescription", {
                        defaultValue: "Edit description inline for {{name}}",
                        name: record?.name || record?.slug || "character"
                      })}
                      onDoubleClick={(event) =>
                        startInlineEdit(record, 'description', event.currentTarget)
                      }
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === 'F2') {
                          event.preventDefault()
                          startInlineEdit(record, 'description', event.currentTarget)
                        }
                      }}
                    >
                      {v ? (
                        truncateText(v, MAX_DESCRIPTION_LENGTH)
                      ) : (
                        <span className="text-text-subtle">
                          {t("settings:manageCharacters.table.noDescription", {
                            defaultValue: "—"
                          })}
                        </span>
                      )}
                    </span>
                  </Tooltip>
                )
              }
            },
            {
              title: t("settings:manageCharacters.tags.label", {
                defaultValue: "Tags"
              }),
              dataIndex: "tags",
              key: "tags",
              render: (tags: string[]) => {
                const all = tags || []
                const visible = all.slice(0, MAX_TAGS_DISPLAYED)
                const hasMore = all.length > MAX_TAGS_DISPLAYED
                const hiddenCount = all.length - MAX_TAGS_DISPLAYED
                const hiddenTags = all.slice(MAX_TAGS_DISPLAYED)
                return (
                  <div className="flex flex-wrap gap-1">
                    {visible.map((tag: string, index: number) => (
                      <Tag key={`${tag}-${index}`}>
                        {truncateText(tag, MAX_TAG_LENGTH)}
                      </Tag>
                    ))}
                    {hasMore && (
                      <Tooltip
                        title={
                          <div>
                            <div className="font-medium mb-1">
                              {t("settings:manageCharacters.tags.moreCount", {
                                defaultValue: "+{{count}} more tags",
                                count: hiddenCount
                              })}
                            </div>
                            <div className="text-xs">
                              {hiddenTags.join(", ")}
                            </div>
                          </div>
                        }
                      >
                        <span className="text-xs text-text-subtle cursor-help">
                          +{hiddenCount}
                        </span>
                      </Tooltip>
                    )}
                  </div>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.creator", {
                defaultValue: "Creator"
              }),
              key: "creator",
              sorter: true,
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "creator" ? sortOrder : undefined,
              render: (_: any, record: any) => {
                const creatorValue =
                  record.creator || record.created_by || record.createdBy
                return creatorValue ? (
                  <span className="text-xs text-text">{creatorValue}</span>
                ) : (
                  <span className="text-text-subtle">—</span>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.createdAt", {
                defaultValue: "Created"
              }),
              key: "createdAt",
              sorter: true,
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "createdAt" ? sortOrder : undefined,
              render: (_: any, record: any) => (
                <span className="text-xs text-text-muted">
                  {formatTableDateCell(record, ["created_at", "createdAt", "created"])}
                </span>
              )
            },
            {
              title: t("settings:manageCharacters.columns.updatedAt", {
                defaultValue: "Updated"
              }),
              key: "updatedAt",
              sorter: true,
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "updatedAt" ? sortOrder : undefined,
              render: (_: any, record: any) => (
                <span className="text-xs text-text-muted">
                  {formatTableDateCell(record, [
                    "updated_at",
                    "updatedAt",
                    "modified_at",
                    "modifiedAt"
                  ])}
                </span>
              )
            },
            {
              title: t("settings:manageCharacters.columns.conversations", {
                defaultValue: "Chats"
              }),
              key: "conversations",
              width: 70,
              align: "center" as const,
              sorter: true,
              sortDirections: ["ascend", "descend"] as const,
              sortOrder: sortColumn === "conversations" ? sortOrder : undefined,
              render: (_: any, record: any) => {
                const charId = String(record.id || record.slug || record.name)
                const count = conversationCounts?.[charId] || 0
                return count > 0 ? (
                  <Tooltip
                    title={t("settings:manageCharacters.gallery.conversationCount", {
                      defaultValue: "{{count}} conversation(s)",
                      count
                    })}
                  >
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      <MessageCircle className="h-3 w-3" />
                      {count > 99 ? '99+' : count}
                    </span>
                  </Tooltip>
                ) : (
                  <span className="text-text-subtle">—</span>
                )
              }
            },
            {
              title: t("settings:manageCharacters.columns.actions", {
                defaultValue: "Actions"
              }),
              key: "actions",
              render: (_: any, record: any) => {
                const chatLabel = t("settings:manageCharacters.actions.chat", {
                  defaultValue: "Chat"
                })
                const editLabel = t(
                  "settings:manageCharacters.actions.edit",
                  {
                    defaultValue: "Edit"
                  }
                )
                const deleteLabel = t(
                  "settings:manageCharacters.actions.delete",
                  {
                    defaultValue: "Delete"
                  }
                )
                const duplicateLabel = t(
                  "settings:manageCharacters.actions.duplicate",
                  {
                    defaultValue: "Duplicate"
                  }
                )
                const exportLabel = t(
                  "settings:manageCharacters.actions.export",
                  {
                    defaultValue: "Export"
                  }
                )
                const restoreLabel = t(
                  "settings:manageCharacters.actions.restore",
                  {
                    defaultValue: "Restore"
                  }
                )
                const name = record?.name || record?.title || record?.slug || ""

                if (characterListScope === "deleted") {
                  return (
                    <div className="flex flex-wrap items-center gap-2">
                      <Tooltip title={restoreLabel}>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-primary transition motion-reduce:transition-none hover:border-primary/30 hover:bg-primary/10 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                          aria-label={t("settings:manageCharacters.aria.restore", {
                            defaultValue: "Restore character {{name}}",
                            name
                          })}
                          onClick={() => handleRestoreFromTrash(record)}>
                          <History className="w-4 h-4" />
                          <span className="hidden sm:inline text-xs font-medium">
                            {restoreLabel}
                          </span>
                        </button>
                      </Tooltip>
                    </div>
                  )
                }
                return (
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Primary: Chat */}
                    <Tooltip
                      title={chatLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-primary transition motion-reduce:transition-none hover:border-primary/30 hover:bg-primary/10 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                        aria-label={t("settings:manageCharacters.aria.chatWith", {
                          defaultValue: "Chat as {{name}}",
                          name
                        })}
                        onClick={() => {
                          const id = record.id || record.slug || record.name
                          setSelectedCharacter({
                            id,
                            name: record.name || record.title || record.slug,
                            system_prompt:
                              record.system_prompt ||
                              record.systemPrompt ||
                              record.instructions ||
                              "",
                            greeting:
                              record.greeting ||
                              record.first_message ||
                              record.greet ||
                              "",
                            avatar_url:
                              record.avatar_url ||
                              validateAndCreateImageDataUrl(record.image_base64) ||
                              ""
                          })
                          navigate("/")
                          setTimeout(() => {
                            focusComposer()
                          }, 0)
                        }}>
                        <MessageCircle className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {chatLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Primary: Edit */}
                    <Tooltip
                      title={editLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-text-muted transition motion-reduce:transition-none hover:border-border hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                        aria-label={t("settings:manageCharacters.aria.edit", {
                          defaultValue: "Edit character {{name}}",
                          name
                        })}
                        onClick={(e) => {
                          handleEdit(record, e.currentTarget)
                        }}>
                        <Pen className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {editLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Primary: Delete */}
                    <Tooltip
                      title={deleteLabel}>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-danger transition motion-reduce:transition-none hover:border-danger/30 hover:bg-danger/10 focus:outline-none focus:ring-2 focus:ring-danger focus:ring-offset-1 focus:ring-offset-bg disabled:cursor-not-allowed disabled:opacity-60"
                        aria-label={t("settings:manageCharacters.aria.delete", {
                          defaultValue: "Delete character {{name}}",
                          name
                        })}
                        disabled={deleting}
                        onClick={async () => {
                          const ok = await confirmDanger({
                            title: t("common:confirmTitle", {
                              defaultValue: "Please confirm"
                            }),
                            content: t(
                              "settings:manageCharacters.confirm.delete",
                              {
                                defaultValue:
                                  "Are you sure you want to delete this character? It will be soft-deleted and can be undone for 10 seconds."
                              }
                            ),
                            okText: t("common:delete", { defaultValue: "Delete" }),
                            cancelText: t("common:cancel", {
                              defaultValue: "Cancel"
                            })
                          })
                          if (ok) {
                            await handleDelete(record)
                          }
                        }}>
                        <Trash2 className="w-4 h-4" />
                        <span className="hidden sm:inline text-xs font-medium">
                          {deleteLabel}
                        </span>
                      </button>
                    </Tooltip>
                    {/* Overflow: View Conversations, Duplicate, Export */}
                    <Dropdown
                      menu={{
                        items: [
                          {
                            key: 'quick-chat',
                            icon: <MessageCircle className="w-4 h-4" />,
                            label: t("settings:manageCharacters.actions.quickChat", {
                              defaultValue: "Quick chat"
                            }),
                            onClick: () => openQuickChat(record)
                          },
                          {
                            key: 'conversations',
                            icon: <History className="w-4 h-4" />,
                            label: t("settings:manageCharacters.actions.viewConversations", {
                              defaultValue: "View conversations"
                            }),
                            onClick: () => {
                              setConversationCharacter(record)
                              setCharacterChats([])
                              setChatsError(null)
                              setConversationsOpen(true)
                            }
                          },
                          {
                            key: 'duplicate',
                            icon: <Copy className="w-4 h-4" />,
                            label: duplicateLabel,
                            onClick: () => handleDuplicate(record)
                          },
                          { type: 'divider' as const },
                          {
                            key: 'export-json',
                            icon: <Download className="w-4 h-4" />,
                            label: t("settings:manageCharacters.export.json", { defaultValue: "Export as JSON" }),
                            disabled: exporting === (record.id || record.slug || record.name),
                            onClick: () => handleExport(record, 'json')
                          },
                          {
                            key: 'export-png',
                            icon: <Download className="w-4 h-4" />,
                            label: t("settings:manageCharacters.export.png", { defaultValue: "Export as PNG (with metadata)" }),
                            disabled: exporting === (record.id || record.slug || record.name),
                            onClick: () => handleExport(record, 'png')
                          }
                        ]
                      }}
                      trigger={['click']}
                      placement="bottomRight">
                      <Tooltip title={t("settings:manageCharacters.actions.more", { defaultValue: "More actions" })}>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-text-muted transition motion-reduce:transition-none hover:border-border hover:bg-surface2 focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-bg"
                          aria-label={t("settings:manageCharacters.aria.moreActions", {
                            defaultValue: "More actions for {{name}}",
                            name
                          })}>
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </Tooltip>
                    </Dropdown>
                  </div>
                )
              }
            }
          ].filter(Boolean) as any}
          />
          </div>
        </div>
      )}

      {/* Gallery View */}
      {status === "success" && Array.isArray(data) && data.length > 0 && viewMode === 'gallery' && (
        <div className="space-y-4">
          <div
            className={`grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 ${
              galleryDensity === "compact" ? "gap-3" : "gap-4"
            }`}>
            {pagedGalleryData.map((character: any) => {
              const charId = String(character.id || character.slug || character.name)
              return (
                <CharacterGalleryCard
                  key={charId}
                  character={character}
                  onClick={() => setPreviewCharacter(character)}
                  conversationCount={conversationCounts?.[charId]}
                  density={galleryDensity}
                />
              )
            })}
          </div>
          {totalCharacters > pageSize && (
            <div className="flex justify-end">
              <Pagination
                current={currentPage}
                pageSize={pageSize}
                total={totalCharacters}
                onChange={(page, nextPageSize) => {
                  const normalizedNextPageSize = normalizePageSize(nextPageSize)
                  if (normalizedNextPageSize !== pageSize) {
                    setPageSize(normalizedNextPageSize)
                    setCurrentPage(1)
                    return
                  }
                  setCurrentPage(page)
                }}
                onShowSizeChange={(_page, nextPageSize) => {
                  setPageSize(normalizePageSize(nextPageSize))
                  setCurrentPage(1)
                }}
                showSizeChanger
                pageSizeOptions={PAGE_SIZE_OPTIONS.map((size) => String(size))}
              />
            </div>
          )}
        </div>
      )}

      {/* Character Preview Popup for Gallery View */}
      <CharacterPreviewPopup
        character={previewCharacter}
        open={!!previewCharacter}
        onClose={() => setPreviewCharacter(null)}
        onChat={() => {
          if (previewCharacter) {
            handleChat(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onQuickChat={() => {
          if (previewCharacter) {
            openQuickChat(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onEdit={() => {
          if (previewCharacter) {
            handleEdit(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onDuplicate={() => {
          if (previewCharacter) {
            handleDuplicate(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onExport={async (format?: 'json' | 'png') => {
          if (previewCharacter) {
            await handleExport(previewCharacter, format || 'json')
          }
        }}
        onDelete={async () => {
          if (previewCharacter) {
            await handleDelete(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        onViewConversations={() => {
          if (previewCharacter) {
            handleViewConversations(previewCharacter)
            setPreviewCharacter(null)
          }
        }}
        attachedWorldBooks={previewCharacterWorldBooks}
        attachedWorldBooksLoading={previewCharacterWorldBooksLoading}
        launchedFromWorldBooks={crossNavigationContext.launchedFromWorldBooks}
        launchedFromWorldBookId={crossNavigationContext.focusWorldBookId}
        deleting={deleting}
        exporting={!!exporting && exporting === (previewCharacter?.id || previewCharacter?.slug || previewCharacter?.name)}
      />

      <Modal
        title={t("settings:manageCharacters.import.previewTitle", {
          defaultValue: "Import preview"
        })}
        open={importPreviewOpen}
        onCancel={resetImportPreview}
        footer={[
          <Button
            key="cancel"
            onClick={resetImportPreview}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </Button>,
          <Button
            key="confirm"
            type="primary"
            loading={importing}
            disabled={importablePreviewItems.length === 0 || importPreviewLoading}
            onClick={() => {
              void handleConfirmImportPreview()
            }}>
            {t("settings:manageCharacters.import.confirmPreview", {
              defaultValue: "Confirm import"
            })}
          </Button>
        ]}
        rootClassName="characters-motion-modal">
        {importPreviewLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <div className="space-y-3">
            {importPreviewItems.map((item) => (
              <div
                key={item.id}
                className="rounded-md border border-border bg-surface2/40 p-3"
                data-testid="character-import-preview-item">
                <div className="flex items-start gap-3">
                  {item.avatarUrl ? (
                    <img
                      src={item.avatarUrl}
                      alt={item.name}
                      className="h-12 w-12 rounded-md object-cover border border-border"
                    />
                  ) : (
                    <div className="flex h-12 w-12 items-center justify-center rounded-md border border-border bg-surface">
                      <UserCircle2 className="h-6 w-6 text-text-muted" />
                    </div>
                  )}
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-sm text-text">
                        {item.name}
                      </span>
                      <span className="text-xs text-text-subtle uppercase">
                        {item.format}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted">{item.fileName}</div>
                    {item.description && (
                      <div className="text-sm text-text line-clamp-2">
                        {item.description}
                      </div>
                    )}
                    <div className="text-xs text-text-subtle">
                      {t("settings:manageCharacters.import.previewMeta", {
                        defaultValue: "Fields: {{fields}} · Tags: {{tags}}",
                        fields: item.fieldCount,
                        tags: item.tagCount
                      })}
                    </div>
                    {item.parseError && (
                      <div className="text-xs text-danger">
                        {t(item.parseError.key, {
                          defaultValue: item.parseError.fallback,
                          ...(item.parseError.values || {})
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      <Modal
        title={t("settings:manageCharacters.quickChat.title", {
          defaultValue: "Quick chat: {{name}}",
          name:
            quickChatCharacter?.name ||
            quickChatCharacter?.title ||
            quickChatCharacter?.slug ||
            t("settings:manageCharacters.preview.untitled", {
              defaultValue: "Untitled character"
            })
        })}
        open={!!quickChatCharacter}
        onCancel={() => {
          void closeQuickChat()
        }}
        footer={null}
        destroyOnHidden
        width={560}
        rootClassName="characters-motion-modal">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">
              {t("settings:manageCharacters.quickChat.modelLabel", {
                defaultValue: "Model"
              })}
            </span>
            <Select
              className="flex-1"
              size="small"
              showSearch
              placeholder={t("settings:manageCharacters.quickChat.modelPlaceholder", {
                defaultValue: "Select a model"
              })}
              options={quickChatModelOptions}
              value={activeQuickChatModel || undefined}
              optionFilterProp="label"
              onChange={(value) => setQuickChatModelOverride(value || null)}
              allowClear
            />
          </div>

          {quickChatError && (
            <Alert
              type="warning"
              showIcon
              message={quickChatError}
            />
          )}

          <div
            className="max-h-72 min-h-[12rem] overflow-y-auto rounded-md border border-border bg-surface2/40 p-3 space-y-2"
            role="log"
            aria-live="polite">
            {quickChatMessages.length === 0 ? (
              <div className="text-sm text-text-subtle">
                {t("settings:manageCharacters.quickChat.emptyState", {
                  defaultValue:
                    "Send a message to quickly test this character without leaving the page."
                })}
              </div>
            ) : (
              quickChatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}>
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap rounded-md px-3 py-2 text-sm ${
                      message.role === "user"
                        ? "bg-primary text-white"
                        : "bg-surface text-text border border-border"
                    }`}>
                    {message.content}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex gap-2">
            <Input.TextArea
              value={quickChatDraft}
              onChange={(event) => setQuickChatDraft(event.target.value)}
              placeholder={t("settings:manageCharacters.quickChat.placeholder", {
                defaultValue: "Ask this character a quick question..."
              })}
              autoSize={{ minRows: 1, maxRows: 4 }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  void sendQuickChatMessage()
                }
              }}
              disabled={quickChatSending}
            />
            <Button
              type="primary"
              loading={quickChatSending}
              onClick={() => {
                void sendQuickChatMessage()
              }}
              disabled={!quickChatDraft.trim() || !activeQuickChatModel}>
              {t("settings:manageCharacters.quickChat.send", {
                defaultValue: "Send"
              })}
            </Button>
          </div>
          <div className="flex justify-end">
            <Button
              onClick={() => {
                void handlePromoteQuickChat()
              }}
              disabled={!quickChatCharacter || quickChatSending}>
              {t("settings:manageCharacters.quickChat.openFullChat", {
                defaultValue: "Open full chat"
              })}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        title={
          conversationCharacter
            ? t("settings:manageCharacters.conversations.title", {
                defaultValue: "Conversations for {{name}}",
                name:
                  conversationCharacter.name ||
                  conversationCharacter.title ||
                  conversationCharacter.slug ||
                  ""
              })
            : t("settings:manageCharacters.conversations.titleGeneric", {
                defaultValue: "Character conversations"
              })
        }
        open={conversationsOpen}
        onCancel={() => {
          setConversationsOpen(false)
          setConversationCharacter(null)
          setCharacterChats([])
          setChatsError(null)
          setResumingChatId(null)
        }}
        footer={null}
        destroyOnHidden
        rootClassName="characters-motion-modal">
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            {t("settings:manageCharacters.conversations.subtitle", {
              defaultValue:
                "Select a conversation to continue as this character."
            })}
          </p>
          {chatsError && (
            <Alert
              type="error"
              showIcon
              title={chatsError}
              action={
                <Button
                  size="small"
                  onClick={async () => {
                    if (!conversationCharacter) return
                    setChatsError(null)
                    setLoadingChats(true)
                    setCharacterChats([])
                    try {
                      await tldwClient.initialize()
                      const characterId = characterIdentifier(conversationCharacter)
                      const chats = await tldwClient.listChats({
                        character_id: characterId || undefined,
                        limit: 100,
                        ordering: "-updated_at"
                      })
                      const filtered = Array.isArray(chats)
                        ? chats.filter(
                            (c) =>
                              characterId &&
                              String(c.character_id ?? "") === String(characterId)
                          )
                        : []
                      setCharacterChats(filtered)
                    } catch {
                      setChatsError(
                        t("settings:manageCharacters.conversations.error", {
                          defaultValue:
                            "Unable to load conversations for this character."
                        })
                      )
                    } finally {
                      setLoadingChats(false)
                    }
                  }}>
                  {t("common:retry", { defaultValue: "Retry" })}
                </Button>
              }
            />
          )}
          {loadingChats && <Skeleton active title paragraph={{ rows: 4 }} />}
          {!loadingChats && !chatsError && (
            <>
              {characterChats.length === 0 ? (
                <div className="rounded-md border border-dashed border-border bg-surface2 p-3 text-sm text-text-muted">
                  {t("settings:manageCharacters.conversations.empty", {
                    defaultValue: "No conversations found for this character yet."
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {characterChats.map((chat, index) => (
                    <div
                      key={chat.id}
                      className={`flex items-start justify-between gap-3 rounded-md border p-3 shadow-sm ${
                        index === 0
                          ? "border-primary/30 bg-primary/10"
                          : "border-border bg-surface"
                      }`}>
                      <div className="min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-text truncate">
                            {chat.title ||
                              t("settings:manageCharacters.conversations.untitled", {
                                defaultValue: "Untitled"
                              })}
                          </span>
                          {index === 0 && (
                            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                              {t("settings:manageCharacters.conversations.mostRecent", {
                                defaultValue: "Most recent"
                              })}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-text-subtle">
                          {formatUpdatedLabel(chat.updated_at || chat.created_at)}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-text-subtle">
                          <span className="inline-flex items-center rounded-full bg-surface2 px-2 py-0.5 lowercase text-text-muted">
                            {(chat.state as string) || "in-progress"}
                          </span>
                          {chat.topic_label && (
                            <span
                              className="truncate max-w-[14rem]"
                              title={String(chat.topic_label)}
                            >
                              {String(chat.topic_label)}
                            </span>
                          )}
                        </div>
                      </div>
                      <Tooltip
                        title={t("settings:manageCharacters.conversations.resumeTooltip", {
                          defaultValue: "Load chat history and continue this conversation"
                        })}>
                        <Button
                          type="primary"
                          size="small"
                          loading={resumingChatId === chat.id}
                          onClick={async () => {
                          if (!conversationCharacter) return
                          setResumingChatId(chat.id)
                          try {
                            await tldwClient.initialize()

                            const assistantName =
                              conversationCharacter.name ||
                              conversationCharacter.title ||
                              conversationCharacter.slug ||
                              t("common:assistant", {
                                defaultValue: "Assistant"
                              })

                            const messages = await tldwClient.listChatMessages(
                              chat.id,
                              { include_deleted: "false" } as any
                            )
                            const history = messages.map((m) => ({
                              role: normalizeChatRole(m.role),
                              content: m.content
                            }))
                            const mappedMessages = messages.map((m) => {
                              const createdAt = Date.parse(m.created_at)
                              const normalized = normalizeChatRole(m.role)
                              return {
                                createdAt: Number.isNaN(createdAt)
                                  ? undefined
                                  : createdAt,
                                isBot: normalized === "assistant",
                                role: normalized,
                                name:
                                  normalized === "assistant"
                                    ? assistantName
                                    : normalized === "system"
                                      ? t("common:system", {
                                          defaultValue: "System"
                                        })
                                      : t("common:you", { defaultValue: "You" }),
                                message: m.content,
                                sources: [],
                                images: [],
                                serverMessageId: m.id,
                                serverMessageVersion: m.version
                              }
                            })

                            const id = characterIdentifier(conversationCharacter)
                            setSelectedCharacter({
                              id,
                              name:
                                conversationCharacter.name ||
                                conversationCharacter.title ||
                                conversationCharacter.slug,
                              system_prompt:
                                conversationCharacter.system_prompt ||
                                conversationCharacter.systemPrompt ||
                                conversationCharacter.instructions ||
                                "",
                              greeting:
                                conversationCharacter.greeting ||
                                conversationCharacter.first_message ||
                                conversationCharacter.greet ||
                                "",
                              avatar_url:
                                conversationCharacter.avatar_url ||
                                validateAndCreateImageDataUrl(
                                  conversationCharacter.image_base64
                                ) ||
                                ""
                            })

                            setHistoryId(null)
                            setServerChatId(chat.id)
                            setServerChatState(
                              (chat as any)?.state ??
                                (chat as any)?.conversation_state ??
                                "in-progress"
                            )
                            setServerChatTopic(
                              (chat as any)?.topic_label ?? null
                            )
                            setServerChatClusterId(
                              (chat as any)?.cluster_id ?? null
                            )
                            setServerChatSource(
                              (chat as any)?.source ?? null
                            )
                            setServerChatExternalRef(
                              (chat as any)?.external_ref ?? null
                            )
                            setHistory(history)
                            setMessages(mappedMessages)
                            updatePageTitle(chat.title)
                            setConversationsOpen(false)
                            setConversationCharacter(null)
                            navigate("/")
                            setTimeout(() => {
                              focusComposer()
                            }, 0)
                          } catch (e) {
                            setChatsError(
                              t("settings:manageCharacters.conversations.error", {
                                defaultValue:
                                  "Unable to load conversations for this character."
                              })
                            )
                          } finally {
                            setResumingChatId(null)
                          }
                        }}>
                          {t("settings:manageCharacters.conversations.resume", {
                            defaultValue: "Continue chat"
                          })}
                        </Button>
                      </Tooltip>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </Modal>

      <Modal
        title={t("settings:manageCharacters.modal.addTitle", {
          defaultValue: "New character"
        })}
        open={open}
        onCancel={() => {
          if (createFormDirty) {
            Modal.confirm({
              title: t("settings:manageCharacters.modal.unsavedTitle", {
                defaultValue: "Discard changes?"
              }),
              content: t("settings:manageCharacters.modal.unsavedContent", {
                defaultValue: "You have unsaved changes. Are you sure you want to close?"
              }),
              okText: t("common:discard", { defaultValue: "Discard" }),
              cancelText: t("common:cancel", { defaultValue: "Cancel" }),
              onOk: () => {
                setOpen(false)
                createForm.resetFields()
                setCreateFormDirty(false)
                setShowCreateAdvanced(false)
                setShowCreateSystemPromptExample(false)
                setTimeout(() => {
                  newButtonRef.current?.focus()
                }, 0)
              }
            })
          } else {
            setOpen(false)
            createForm.resetFields()
            setShowCreateAdvanced(false)
            setShowCreateSystemPromptExample(false)
            setTimeout(() => {
              newButtonRef.current?.focus()
            }, 0)
          }
        }}
        footer={null}
        rootClassName="characters-motion-modal">
        <p className="text-sm text-text-muted mb-4">
          {t("settings:manageCharacters.modal.description", {
            defaultValue: "Define a reusable character you can chat with in the sidebar."
          })}
        </p>

        {/* Draft Recovery Banner (H4) */}
        {hasCreateDraft && createDraftData && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            title={
              <span>
                {t("settings:manageCharacters.draft.found", {
                  defaultValue: "Resume unsaved character?"
                })}
                {createDraftData.formData?.name && (
                  <strong className="ml-1">"{createDraftData.formData.name}"</strong>
                )}
                <span className="text-text-muted ml-1">
                  ({formatDraftAge(createDraftData.savedAt)})
                </span>
              </span>
            }
            action={
              <div className="flex gap-2">
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    const draft = applyCreateDraft()
                    if (draft) {
                      createForm.setFieldsValue(draft)
                      setCreateFormDirty(true)
                      if (hasAdvancedData(draft, draft.extensions || '')) {
                        setShowCreateAdvanced(true)
                      }
                    }
                  }}>
                  {t("settings:manageCharacters.draft.restore", { defaultValue: "Restore" })}
                </Button>
                <Button
                  size="small"
                  onClick={dismissCreateDraft}>
                  {t("settings:manageCharacters.draft.discard", { defaultValue: "Discard" })}
                </Button>
              </div>
            }
          />
        )}

        {/* Template Selection (M4) */}
        {!showTemplates ? (
          <div className="mb-4">
            <Button
              type="link"
              size="small"
              className="p-0"
              onClick={() => {
                setShowTemplates(true)
                markTemplateChooserSeen()
              }}>
              {t("settings:manageCharacters.templates.startFrom", {
                defaultValue: "Start from a template..."
              })}
            </Button>
          </div>
        ) : (
          <div className="mb-4 p-3 bg-surface rounded-lg border border-border">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium">
                {t("settings:manageCharacters.templates.title", {
                  defaultValue: "Choose a template"
                })}
              </span>
              <Button
                type="link"
                size="small"
                onClick={() => {
                  setShowTemplates(false)
                  markTemplateChooserSeen()
                }}>
                {t("common:cancel", { defaultValue: "Cancel" })}
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {CHARACTER_TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  className="text-left p-2 rounded border border-border hover:border-primary hover:bg-surface-hover transition-colors motion-reduce:transition-none"
                  onClick={() => applyTemplateToCreateForm(template)}>
                  <div className="font-medium text-sm">{template.name}</div>
                  <div className="text-xs text-text-muted">{template.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* AI Character Generation Panel */}
        <GenerateCharacterPanel
          isGenerating={isGenerating && generatingField === 'all'}
          error={generationError}
          onGenerate={handleGenerateFullCharacter}
          onCancel={cancelGeneration}
          onClearError={clearGenerationError}
        />

        {renderSharedCharacterForm({
          form: createForm,
          mode: "create",
          initialValues: { prompt_preset: DEFAULT_CHARACTER_PROMPT_PRESET },
          isSubmitting: creating,
          submitButtonClassName: "mt-4",
          submitPendingLabel: t("settings:manageCharacters.form.btnSave.saving", {
            defaultValue: "Creating character..."
          }),
          submitIdleLabel: t("settings:manageCharacters.form.btnSave.save", {
            defaultValue: "Create character"
          }),
          showPreview: showCreatePreview,
          onTogglePreview: () => setShowCreatePreview((v) => !v),
          onValuesChange: (allValues) => {
            setCreateFormDirty(true)
            saveCreateDraft(allValues)
          },
          onFinish: (values) => {
            createCharacter(values)
            clearCreateDraft()
            setCreateFormDirty(false)
            setShowCreateAdvanced(false)
          }
        })}
      </Modal>

      <Modal
        title={t("settings:manageCharacters.modal.editTitle", {
          defaultValue: "Edit character"
        })}
        open={openEdit}
        onCancel={() => {
          if (editFormDirty) {
            Modal.confirm({
              title: t("settings:manageCharacters.modal.unsavedTitle", {
                defaultValue: "Discard changes?"
              }),
              content: t("settings:manageCharacters.modal.unsavedContent", {
                defaultValue: "You have unsaved changes. Are you sure you want to close?"
              }),
              okText: t("common:discard", { defaultValue: "Discard" }),
              cancelText: t("common:cancel", { defaultValue: "Cancel" }),
              onOk: () => {
                setOpenEdit(false)
                editForm.resetFields()
                setEditId(null)
                setEditVersion(null)
                setEditFormDirty(false)
                setShowEditSystemPromptExample(false)
                setTimeout(() => {
                  lastEditTriggerRef.current?.focus()
                }, 0)
              }
            })
          } else {
            setOpenEdit(false)
            editForm.resetFields()
            setEditId(null)
            setEditVersion(null)
            setShowEditSystemPromptExample(false)
            setTimeout(() => {
              lastEditTriggerRef.current?.focus()
            }, 0)
          }
        }}
        footer={null}
        rootClassName="characters-motion-modal">
        <p className="text-sm text-text-muted mb-4">
          {t("settings:manageCharacters.modal.editDescription", {
            defaultValue: "Update the character's name, behavior, and other settings."
          })}
        </p>

        {/* Draft Recovery Banner for Edit Form (H4) */}
        {hasEditDraft && editDraftData && (
          <Alert
            type="info"
            showIcon
            className="mb-4"
            title={
              <span>
                {t("settings:manageCharacters.draft.resumeEdit", {
                  defaultValue: "Resume unsaved changes?"
                })}
                <span className="text-text-muted ml-1">
                  ({formatDraftAge(editDraftData.savedAt)})
                </span>
              </span>
            }
            action={
              <div className="flex gap-2">
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    const draft = applyEditDraft()
                    if (draft) {
                      editForm.setFieldsValue(draft)
                      setEditFormDirty(true)
                      if (hasAdvancedData(draft, draft.extensions || '')) {
                        setShowEditAdvanced(true)
                      }
                    }
                  }}>
                  {t("settings:manageCharacters.draft.restore", { defaultValue: "Restore" })}
                </Button>
                <Button
                  size="small"
                  onClick={dismissEditDraft}>
                  {t("settings:manageCharacters.draft.discard", { defaultValue: "Discard" })}
                </Button>
              </div>
            }
          />
        )}

        {renderSharedCharacterForm({
          form: editForm,
          mode: "edit",
          isSubmitting: updating,
          submitButtonClassName: "w-full",
          submitPendingLabel: t("settings:manageCharacters.form.btnEdit.saving", {
            defaultValue: "Saving changes..."
          }),
          submitIdleLabel: t("settings:manageCharacters.form.btnEdit.save", {
            defaultValue: "Save changes"
          }),
          showPreview: showEditPreview,
          onTogglePreview: () => setShowEditPreview((v) => !v),
          onValuesChange: (allValues) => {
            setEditFormDirty(true)
            saveEditDraft(allValues)
          },
          onFinish: (values) => {
            updateCharacter(values)
            clearEditDraft()
            setEditFormDirty(false)
          }
        })}
      </Modal>

      {/* Generation Preview Modal */}
      <GenerationPreviewModal
        open={generationPreviewOpen}
        generatedData={generationPreviewData}
        fieldName={generationPreviewField}
        onApply={applyGenerationPreview}
        onCancel={() => {
          setGenerationPreviewOpen(false)
          setGenerationPreviewData(null)
          setGenerationPreviewField(null)
        }}
      />

      <Modal
        title={t("settings:manageCharacters.tags.manageTitle", {
          defaultValue: "Manage tags"
        })}
        open={tagManagerOpen}
        onCancel={closeTagManager}
        onOk={() => {
          void handleApplyTagManagerOperation()
        }}
        okText={t("settings:manageCharacters.tags.applyOperation", {
          defaultValue: "Apply"
        })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        confirmLoading={tagManagerSubmitting}
        rootClassName="characters-motion-modal"
        okButtonProps={{
          disabled:
            tagManagerLoading ||
            !tagManagerSourceTag ||
            ((tagManagerOperation === "rename" || tagManagerOperation === "merge") &&
              tagManagerTargetTag.trim().length === 0)
        }}>
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            {t("settings:manageCharacters.tags.manageDescription", {
              defaultValue:
                "Rename, merge, or delete tags across your character library."
            })}
          </p>
          <Segmented
            value={tagManagerOperation}
            onChange={(value) =>
              setTagManagerOperation(value as CharacterTagOperation)
            }
            options={[
              {
                value: "rename",
                label: t("settings:manageCharacters.tags.operation.rename", {
                  defaultValue: "Rename"
                })
              },
              {
                value: "merge",
                label: t("settings:manageCharacters.tags.operation.merge", {
                  defaultValue: "Merge"
                })
              },
              {
                value: "delete",
                label: t("settings:manageCharacters.tags.operation.delete", {
                  defaultValue: "Delete"
                })
              }
            ]}
          />
          <Select
            allowClear
            showSearch
            className="w-full"
            loading={tagManagerLoading}
            placeholder={t("settings:manageCharacters.tags.sourcePlaceholder", {
              defaultValue: "Select source tag"
            })}
            value={tagManagerSourceTag}
            options={tagManagerTagUsageData.map(({ tag, count }) => ({
              value: tag,
              label: `${tag} (${count})`
            }))}
            onChange={(value) => setTagManagerSourceTag(value || undefined)}
            filterOption={(input, option) =>
              option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
          {(tagManagerOperation === "rename" || tagManagerOperation === "merge") && (
            <Input
              value={tagManagerTargetTag}
              onChange={(event) => setTagManagerTargetTag(event.target.value)}
              placeholder={t("settings:manageCharacters.tags.targetPlaceholder", {
                defaultValue: "Destination tag"
              })}
            />
          )}
          {tagManagerLoading ? (
            <Skeleton active paragraph={{ rows: 4 }} />
          ) : (
            <div className="max-h-60 overflow-y-auto rounded-md border border-border">
              {tagManagerTagUsageData.length === 0 ? (
                <div className="p-3 text-sm text-text-muted">
                  {t("settings:manageCharacters.tags.none", {
                    defaultValue: "No tags found."
                  })}
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {tagManagerTagUsageData.map(({ tag, count }) => (
                    <li
                      key={tag}
                      className="flex items-center justify-between px-3 py-2 text-sm">
                      <span className="font-medium">{tag}</span>
                      <span className="text-text-muted">{count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* Bulk Add Tags Modal (M5) */}
      <Modal
        title={t("settings:manageCharacters.bulk.addTagsTitle", {
          defaultValue: "Add tags to {{count}} characters",
          count: selectedCount
        })}
        open={bulkTagModalOpen}
        onCancel={() => {
          setBulkTagModalOpen(false)
          setBulkTagsToAdd([])
        }}
        onOk={handleBulkAddTags}
        okText={t("settings:manageCharacters.bulk.addTagsConfirm", { defaultValue: "Add tags" })}
        cancelText={t("common:cancel", { defaultValue: "Cancel" })}
        confirmLoading={bulkOperationLoading}
        rootClassName="characters-motion-modal"
        okButtonProps={{ disabled: bulkTagsToAdd.length === 0 }}>
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            {t("settings:manageCharacters.bulk.addTagsDescription", {
              defaultValue: "Select tags to add to all selected characters. Existing tags will be preserved."
            })}
          </p>
          {/* Popular tags suggestion chips */}
          {popularTags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-xs text-text-subtle mr-1">
                {t("settings:manageCharacters.tags.popular", { defaultValue: "Popular:" })}
              </span>
              {popularTags.map(({ tag, count }) => {
                const isSelected = bulkTagsToAdd.includes(tag)
                return (
                  <button
                    key={tag}
                    type="button"
                    className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border transition-colors motion-reduce:transition-none ${
                      isSelected
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-surface border-border text-text-muted hover:border-primary/50 hover:text-primary'
                    }`}
                    onClick={() => {
                      if (isSelected) {
                        setBulkTagsToAdd(bulkTagsToAdd.filter((t) => t !== tag))
                      } else {
                        setBulkTagsToAdd([...bulkTagsToAdd, tag])
                      }
                    }}>
                    {tag}
                    <span className="text-text-subtle">({count})</span>
                  </button>
                )
              })}
            </div>
          )}
          <Select
            mode="tags"
            allowClear
            className="w-full"
            placeholder={t("settings:manageCharacters.bulk.selectTags", {
              defaultValue: "Select or type tags to add"
            })}
            value={bulkTagsToAdd}
            onChange={(values) => setBulkTagsToAdd(values)}
            options={tagOptionsWithCounts}
            filterOption={(input, option) =>
              option?.value?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
            }
          />
        </div>
      </Modal>
      </div>
    </div>
  )
}
