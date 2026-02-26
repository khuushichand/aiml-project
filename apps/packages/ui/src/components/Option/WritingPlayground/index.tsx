import React from "react"
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Dropdown,
  Empty,
  Input,
  InputNumber,
  List,
  Modal,
  Select,
  Segmented,
  Skeleton,
  Tag,
  Tooltip,
  Typography,
  message
} from "antd"
import type { MenuProps } from "antd"
import type { TextAreaRef } from "antd/es/input/TextArea"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import {
  Columns2,
  Copy,
  Download,
  Edit3,
  Eye,
  MoreHorizontal,
  Pencil,
  Redo2,
  Search,
  Trash2,
  Undo2,
  X
} from "lucide-react"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"
import { formatRelativeTime } from "@/utils/dateFormatters"
import { MarkdownPreview } from "@/components/Common/MarkdownPreview"
import { TldwChatService } from "@/services/tldw/TldwChat"
import {
  cloneWritingSession,
  createWritingSession,
  createWritingTemplate,
  createWritingTheme,
  createWritingWordcloud,
  countWritingTokens,
  deleteWritingSession,
  deleteWritingTemplate,
  deleteWritingTheme,
  getWritingCapabilities,
  getWritingWordcloud,
  getWritingSession,
  listWritingSessions,
  listWritingTemplates,
  listWritingThemes,
  tokenizeWritingText,
  updateWritingSession,
  updateWritingTemplate,
  updateWritingTheme,
  type WritingExtraBodyCompat,
  type WritingTokenCountResponse,
  type WritingTokenizeResponse,
  type WritingWordcloudResponse,
  type WritingSessionListResponse,
  type WritingSessionListItem,
  type WritingTemplateListResponse,
  type WritingTemplateResponse,
  type WritingThemeListResponse,
  type WritingThemeResponse
} from "@/services/writing-playground"
import type { ChatMessage } from "@/services/tldw/TldwApiClient"
import { useStoreChatModelSettings } from "@/store/model"
import { useWritingPlaygroundStore } from "@/store/writing-playground"
import { cn } from "@/libs/utils"
import { resolveApiProviderForModel } from "@/utils/resolve-api-provider"
import {
  buildExtraBodyPayload,
  parseExtraBodyJsonObject,
  parseStringListInput
} from "./extra-body-utils"
import {
  buildContextSystemMessages,
  injectSystemMessages,
  parseWorldInfoKeysInput,
  type WritingAuthorNote,
  type WritingContextBlock,
  type WritingWorldInfoEntry,
  type WritingWorldInfoSettings
} from "./writing-context-utils"
import { buildTokenPreviewRows } from "./writing-token-utils"
import {
  normalizeWordcloudWords,
  parseWordcloudStopwordsInput
} from "./writing-wordcloud-utils"

const { Title, Paragraph } = Typography

type SessionUsage = {
  name: string
  lastUsedAt: number
}

type SessionUsageMap = Record<string, SessionUsage>

type WritingSessionPayload = Record<string, unknown> & {
  prompt?: string
  settings?: WritingSessionSettings
  template_name?: string | null
  templateName?: string | null
  theme_name?: string | null
  themeName?: string | null
  chat_mode?: boolean
  chatMode?: boolean
}

type PendingSave = {
  sessionId: string
  payload: WritingSessionPayload
}

type WritingSessionSettings = {
  temperature: number
  top_p: number
  top_k: number
  max_tokens: number
  presence_penalty: number
  frequency_penalty: number
  seed: number | null
  stop: string[]
  advanced_extra_body: Record<string, unknown>
  memory_block: WritingContextBlock
  author_note: WritingAuthorNote
  world_info: WritingWorldInfoSettings
}

type EditorViewMode = "edit" | "preview" | "split"

type GenerationMode = "append" | "predict" | "fill"

type GenerationPlan = {
  mode: GenerationMode
  placeholder: "{predict}" | "{fill}" | null
  prefix: string
  suffix: string
}

type GenerationHistoryEntry = {
  before: string
  after: string
}

type NormalizedTemplate = {
  name: string
  systemPrefix: string
  systemSuffix: string
  userPrefix: string
  userSuffix: string
  assistantPrefix: string
  assistantSuffix: string
  fimTemplate: string | null
}

type TemplateFormState = {
  name: string
  systemPrefix: string
  systemSuffix: string
  userPrefix: string
  userSuffix: string
  assistantPrefix: string
  assistantSuffix: string
  fimTemplate: string
  isDefault: boolean
}

type NormalizedTheme = {
  name: string
  className: string
  css: string
}

type ThemeFormState = {
  name: string
  className: string
  css: string
  order: number
  isDefault: boolean
}

const SAVE_DEBOUNCE_MS = 800
const MAX_MATCHES = 500
const MAX_CHUNKS = 80
const MAX_WORDCLOUD_WORDS = 200
const WORDCLOUD_POLL_ATTEMPTS = 20
const WORDCLOUD_POLL_DELAY_MS = 600

const PREDICT_PLACEHOLDER = "{predict}"
const FILL_PLACEHOLDER = "{fill}"

const DEFAULT_TEMPLATE: NormalizedTemplate = {
  name: "default",
  systemPrefix: "",
  systemSuffix: "",
  userPrefix: "",
  userSuffix: "",
  assistantPrefix: "",
  assistantSuffix: "",
  fimTemplate: null
}

const EMPTY_TEMPLATE_FORM: TemplateFormState = {
  name: "",
  systemPrefix: "",
  systemSuffix: "",
  userPrefix: "",
  userSuffix: "",
  assistantPrefix: "",
  assistantSuffix: "",
  fimTemplate: "",
  isDefault: false
}

const DEFAULT_THEME: NormalizedTheme = {
  name: "default",
  className: "",
  css: ""
}

const EMPTY_THEME_FORM: ThemeFormState = {
  name: "",
  className: "",
  css: "",
  order: 0,
  isDefault: false
}

const DEFAULT_MEMORY_BLOCK: WritingContextBlock = {
  enabled: false,
  prefix: "Memory:\n",
  text: "",
  suffix: ""
}

const DEFAULT_AUTHOR_NOTE: WritingAuthorNote = {
  enabled: false,
  prefix: "Author note:\n",
  text: "",
  suffix: "",
  insertion_depth: 1
}

const DEFAULT_WORLD_INFO: WritingWorldInfoSettings = {
  enabled: false,
  search_range: 2000,
  entries: []
}

const DEFAULT_SETTINGS: WritingSessionSettings = {
  temperature: 0.7,
  top_p: 0.9,
  top_k: 0,
  max_tokens: 512,
  presence_penalty: 0,
  frequency_penalty: 0,
  seed: null,
  stop: [],
  advanced_extra_body: {},
  memory_block: DEFAULT_MEMORY_BLOCK,
  author_note: DEFAULT_AUTHOR_NOTE,
  world_info: DEFAULT_WORLD_INFO
}

const cloneDefaultSettings = (): WritingSessionSettings => ({
  ...DEFAULT_SETTINGS,
  stop: [...DEFAULT_SETTINGS.stop],
  advanced_extra_body: {},
  memory_block: { ...DEFAULT_MEMORY_BLOCK },
  author_note: { ...DEFAULT_AUTHOR_NOTE },
  world_info: { ...DEFAULT_WORLD_INFO, entries: [] }
})

const ADVANCED_EXTRA_BODY_PARAM_KEYS = [
  "dynatemp_range",
  "dynatemp_exponent",
  "repeat_penalty",
  "repeat_last_n",
  "ignore_eos",
  "mirostat",
  "mirostat_tau",
  "mirostat_eta",
  "typical_p",
  "min_p",
  "tfs_z",
  "xtc_threshold",
  "xtc_probability",
  "dry_multiplier",
  "dry_base",
  "dry_allowed_length",
  "dry_penalty_last_n",
  "dry_sequence_breakers",
  "banned_tokens",
  "grammar"
] as const

type AdvancedNumberParamConfig = {
  key: string
  label: string
  min?: number
  max?: number
  step?: number
}

const ADVANCED_NUMBER_PARAMS: AdvancedNumberParamConfig[] = [
  { key: "dynatemp_range", label: "Dynatemp range", min: 0, max: 10, step: 0.01 },
  { key: "dynatemp_exponent", label: "Dynatemp exponent", min: 0, max: 10, step: 0.01 },
  { key: "repeat_penalty", label: "Repeat penalty", min: 0, max: 3, step: 0.01 },
  { key: "repeat_last_n", label: "Repeat last N", min: -1, max: 8192, step: 1 },
  { key: "typical_p", label: "Typical P", min: 0, max: 1, step: 0.01 },
  { key: "min_p", label: "Min P", min: 0, max: 1, step: 0.01 },
  { key: "tfs_z", label: "TFS Z", min: 0, max: 2, step: 0.01 },
  { key: "mirostat", label: "Mirostat", min: 0, max: 2, step: 1 },
  { key: "mirostat_tau", label: "Mirostat tau", min: 0, max: 20, step: 0.1 },
  { key: "mirostat_eta", label: "Mirostat eta", min: 0, max: 5, step: 0.01 },
  { key: "xtc_threshold", label: "XTC threshold", min: 0, max: 1, step: 0.01 },
  { key: "xtc_probability", label: "XTC probability", min: 0, max: 1, step: 0.01 },
  { key: "dry_multiplier", label: "DRY multiplier", min: 0, max: 10, step: 0.01 },
  { key: "dry_base", label: "DRY base", min: 0, max: 10, step: 0.01 },
  { key: "dry_allowed_length", label: "DRY allowed length", min: 0, max: 4096, step: 1 },
  { key: "dry_penalty_last_n", label: "DRY penalty last N", min: 0, max: 8192, step: 1 }
]

const PREDICT_SYSTEM_PROMPT =
  "Continue the text from the prompt. Respond with only the continuation."
const FILL_SYSTEM_PROMPT =
  "Fill in the missing text between the prefix and suffix. Respond with only the missing text."

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const buildRegex = (
  pattern: string,
  opts: { global: boolean; matchCase: boolean }
): RegExp | null => {
  try {
    const flags = `${opts.global ? "g" : ""}${opts.matchCase ? "" : "i"}`
    return new RegExp(pattern, flags)
  } catch {
    return null
  }
}

const toNumber = (value: unknown, fallback: number): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

const toNullableNumber = (
  value: unknown,
  fallback: number | null
): number | null => {
  if (value == null || value === "") return fallback
  const parsed = toNumber(value, Number.NaN)
  return Number.isFinite(parsed) ? parsed : fallback
}

const normalizeStopStrings = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(/\r?\n/)
      .map((entry) => entry.trim())
      .filter(Boolean)
  }
  return []
}

const normalizeStringArrayValue = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.map((entry) => String(entry).trim()).filter(Boolean)
}

const toBoolean = (value: unknown, fallback: boolean): boolean => {
  if (typeof value === "boolean") return value
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase()
    if (normalized === "true") return true
    if (normalized === "false") return false
  }
  return fallback
}

const toStringValue = (value: unknown, fallback = ""): string =>
  typeof value === "string" ? value : fallback

const createWorldInfoId = (): string =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

const normalizeWorldInfoEntries = (value: unknown): WritingWorldInfoEntry[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (!isRecord(entry)) return null
      const keys = Array.isArray(entry.keys)
        ? entry.keys.map((key) => String(key || "").trim()).filter(Boolean)
        : typeof entry.keys === "string"
          ? parseWorldInfoKeysInput(entry.keys)
          : []
      const content = toStringValue(entry.content).trim()
      if (!content) return null
      if (keys.length === 0) return null
      return {
        id: String(entry.id || createWorldInfoId()),
        enabled: toBoolean(entry.enabled, true),
        keys,
        content,
        use_regex: toBoolean(entry.use_regex ?? entry.useRegex, false),
        case_sensitive: toBoolean(
          entry.case_sensitive ?? entry.caseSensitive,
          false
        )
      } as WritingWorldInfoEntry
    })
    .filter(Boolean) as WritingWorldInfoEntry[]
}

const normalizeContextBlock = (
  raw: unknown,
  fallback: WritingContextBlock
): WritingContextBlock => {
  const value = isRecord(raw) ? raw : {}
  return {
    enabled: toBoolean(value.enabled, fallback.enabled),
    prefix: toStringValue(value.prefix, fallback.prefix),
    text: toStringValue(value.text, fallback.text),
    suffix: toStringValue(value.suffix, fallback.suffix)
  }
}

const normalizeAuthorNote = (raw: unknown): WritingAuthorNote => {
  const value = isRecord(raw) ? raw : {}
  return {
    ...normalizeContextBlock(value, DEFAULT_AUTHOR_NOTE),
    insertion_depth: Math.max(
      1,
      Math.floor(
        toNumber(
          value.insertion_depth ?? value.insertionDepth,
          DEFAULT_AUTHOR_NOTE.insertion_depth
        )
      )
    )
  }
}

const normalizeWorldInfoSettings = (raw: unknown): WritingWorldInfoSettings => {
  const value = isRecord(raw) ? raw : {}
  return {
    enabled: toBoolean(value.enabled, DEFAULT_WORLD_INFO.enabled),
    search_range: Math.max(
      0,
      Math.floor(toNumber(value.search_range ?? value.searchRange, 2000))
    ),
    entries: normalizeWorldInfoEntries(value.entries)
  }
}

const pickAdvancedExtraBodyFromSettings = (
  settings: Record<string, unknown>
): Record<string, unknown> => {
  const direct = isRecord(settings.advanced_extra_body)
    ? { ...settings.advanced_extra_body }
    : isRecord(settings.extra_body)
      ? { ...settings.extra_body }
      : {}

  for (const key of ADVANCED_EXTRA_BODY_PARAM_KEYS) {
    if (!(key in direct) && key in settings) {
      direct[key] = settings[key]
    }
  }

  if (Array.isArray(direct.banned_tokens)) {
    direct.banned_tokens = normalizeStringArrayValue(direct.banned_tokens)
  }
  if (Array.isArray(direct.dry_sequence_breakers)) {
    direct.dry_sequence_breakers = normalizeStringArrayValue(
      direct.dry_sequence_breakers
    )
  }
  if (typeof direct.grammar === "string") {
    direct.grammar = direct.grammar.trim()
  }
  return direct
}

const escapeRegex = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

const getStringValue = (
  payload: Record<string, unknown>,
  keys: string[]
): string => {
  for (const key of keys) {
    const value = payload[key]
    if (typeof value === "string" && value.trim() !== "") {
      return value
    }
  }
  return ""
}

const normalizeTemplatePayload = (
  template?: WritingTemplateResponse | null
): NormalizedTemplate => {
  if (!template || !isRecord(template.payload)) {
    return { ...DEFAULT_TEMPLATE }
  }
  const payload = template.payload
  const systemPrefix = getStringValue(payload, [
    "sys_pre",
    "sysPre",
    "sys_prefix",
    "system_prefix",
    "systemPrefix"
  ])
  const systemSuffix = getStringValue(payload, [
    "sys_suf",
    "sysSuf",
    "sys_suffix",
    "system_suffix",
    "systemSuffix"
  ])
  const userPrefix = getStringValue(payload, [
    "inst_pre",
    "instPre",
    "user_prefix",
    "userPrefix",
    "instruction_prefix",
    "instructionPrefix"
  ])
  const assistantPrefix = getStringValue(payload, [
    "inst_suf",
    "instSuf",
    "assistant_prefix",
    "assistantPrefix",
    "assistant_pre",
    "assistantPre"
  ])
  const userSuffix = getStringValue(payload, [
    "user_suffix",
    "userSuffix",
    "user_suf",
    "userSuf"
  ])
  const assistantSuffix = getStringValue(payload, [
    "assistant_suffix",
    "assistantSuffix",
    "assistant_suf",
    "assistantSuf"
  ])
  const fimTemplate = getStringValue(payload, [
    "fim_template",
    "fimTemplate",
    "fim"
  ])
  return {
    name: template.name,
    systemPrefix,
    systemSuffix,
    userPrefix,
    userSuffix,
    assistantPrefix,
    assistantSuffix,
    fimTemplate: fimTemplate || null
  }
}

const applyFimTemplate = (
  template: NormalizedTemplate,
  prefix: string,
  suffix: string
): string | null => {
  if (!template.fimTemplate) return null
  return template.fimTemplate
    .replace(/\{\{?\s*prefix\s*\}?\}/gi, prefix)
    .replace(/\{\{?\s*suffix\s*\}?\}/gi, suffix)
}

const resolveGenerationPlan = (text: string): GenerationPlan => {
  const predictIndex = text.indexOf(PREDICT_PLACEHOLDER)
  const fillIndex = text.indexOf(FILL_PLACEHOLDER)
  if (predictIndex === -1 && fillIndex === -1) {
    return {
      mode: "append",
      placeholder: null,
      prefix: text,
      suffix: ""
    }
  }
  const usePredict =
    predictIndex !== -1 && (fillIndex === -1 || predictIndex <= fillIndex)
  const placeholder = usePredict ? PREDICT_PLACEHOLDER : FILL_PLACEHOLDER
  const index = usePredict ? predictIndex : fillIndex
  const prefix = text.slice(0, index)
  const suffix = text.slice(index + placeholder.length)
  return {
    mode: usePredict ? "predict" : "fill",
    placeholder,
    prefix,
    suffix
  }
}

const buildFillPrompt = (prefix: string, suffix: string): string => {
  return [
    "Fill in the missing text between the prefix and suffix.",
    "",
    "Prefix:",
    prefix,
    "",
    "Suffix:",
    suffix,
    "",
    "Return only the missing text."
  ].join("\n")
}

const buildTemplateForm = (
  template?: WritingTemplateResponse | null
): TemplateFormState => {
  if (!template || !isRecord(template.payload)) {
    return { ...EMPTY_TEMPLATE_FORM }
  }
  const payload = template.payload
  return {
    name: template.name,
    systemPrefix: getStringValue(payload, [
      "sys_pre",
      "sysPre",
      "sys_prefix",
      "system_prefix",
      "systemPrefix"
    ]),
    systemSuffix: getStringValue(payload, [
      "sys_suf",
      "sysSuf",
      "sys_suffix",
      "system_suffix",
      "systemSuffix"
    ]),
    userPrefix: getStringValue(payload, [
      "inst_pre",
      "instPre",
      "user_prefix",
      "userPrefix",
      "instruction_prefix",
      "instructionPrefix"
    ]),
    userSuffix: getStringValue(payload, [
      "user_suffix",
      "userSuffix",
      "user_suf",
      "userSuf"
    ]),
    assistantPrefix: getStringValue(payload, [
      "inst_suf",
      "instSuf",
      "assistant_prefix",
      "assistantPrefix",
      "assistant_pre",
      "assistantPre"
    ]),
    assistantSuffix: getStringValue(payload, [
      "assistant_suffix",
      "assistantSuffix",
      "assistant_suf",
      "assistantSuf"
    ]),
    fimTemplate: getStringValue(payload, [
      "fim_template",
      "fimTemplate",
      "fim"
    ]),
    isDefault: template.is_default
  }
}

const buildTemplatePayload = (
  form: TemplateFormState
): Record<string, unknown> => {
  const payload: Record<string, unknown> = {}
  if (form.systemPrefix.trim()) payload.sys_pre = form.systemPrefix
  if (form.systemSuffix.trim()) payload.sys_suf = form.systemSuffix
  if (form.userPrefix.trim()) payload.inst_pre = form.userPrefix
  if (form.userSuffix.trim()) payload.user_suffix = form.userSuffix
  if (form.assistantPrefix.trim()) payload.inst_suf = form.assistantPrefix
  if (form.assistantSuffix.trim()) payload.assistant_suf = form.assistantSuffix
  if (form.fimTemplate.trim()) payload.fim_template = form.fimTemplate
  return payload
}

const normalizeThemeResponse = (
  theme?: WritingThemeResponse | null
): NormalizedTheme => {
  if (!theme) {
    return { ...DEFAULT_THEME }
  }
  return {
    name: theme.name,
    className: typeof theme.class_name === "string" ? theme.class_name : "",
    css: typeof theme.css === "string" ? theme.css : ""
  }
}

const buildThemeForm = (theme?: WritingThemeResponse | null): ThemeFormState => {
  if (!theme) {
    return { ...EMPTY_THEME_FORM }
  }
  return {
    name: theme.name,
    className: typeof theme.class_name === "string" ? theme.class_name : "",
    css: typeof theme.css === "string" ? theme.css : "",
    order: Number.isFinite(theme.order) ? theme.order : 0,
    isDefault: theme.is_default
  }
}

const buildThemePayload = (form: ThemeFormState): Record<string, unknown> => {
  const payload: Record<string, unknown> = {}
  if (form.className.trim()) payload.class_name = form.className
  if (form.css.trim()) payload.css = form.css
  if (Number.isFinite(form.order)) payload.order = form.order
  return payload
}

const sanitizeThemeCss = (css: string): string => {
  if (!css.trim()) return ""
  let sanitized = css
  sanitized = sanitized.replace(/@import[^;]+;/gi, "")
  sanitized = sanitized.replace(/@font-face\s*{[^}]*}/gi, "")
  sanitized = sanitized.replace(/@keyframes\s+[^{]+{[\s\S]*?}\s*/gi, "")
  sanitized = sanitized.replace(/url\([^)]*\)/gi, "")
  sanitized = sanitized.replace(/(^|})\s*([^@}{][^{]*)\{/g, (match, close, selector) => {
    const scoped = selector
      .split(",")
      .map((part) => {
        const trimmed = part.trim()
        if (!trimmed) return trimmed
        if (trimmed.startsWith(".writing-playground")) {
          return trimmed
        }
        return `.writing-playground ${trimmed}`
      })
      .join(", ")
    return `${close}${scoped}{`
  })
  return sanitized.trim()
}

const findNextBoundary = (text: string, markers: string[]): number => {
  let earliest = -1
  for (const marker of markers) {
    if (!marker) continue
    const idx = text.indexOf(marker)
    if (idx === -1) continue
    if (earliest === -1 || idx < earliest) {
      earliest = idx
    }
  }
  return earliest
}

type NonToolRole = Exclude<ChatMessage["role"], "tool">
type NonToolMessage = Extract<ChatMessage, { role: NonToolRole }>

const buildNonToolMessage = (
  role: NonToolRole,
  content: string
): NonToolMessage => {
  if (role === "system") {
    return { role, content }
  }
  if (role === "assistant") {
    return { role, content }
  }
  return { role, content }
}

const extractMessage = (
  text: string,
  prefix: string,
  boundaries: string[],
  role: NonToolRole
): { message: NonToolMessage; remaining: string } | null => {
  if (!prefix || !text.startsWith(prefix)) return null
  const rest = text.slice(prefix.length)
  const endIndex = findNextBoundary(rest, boundaries)
  if (endIndex === -1) {
    return {
      message: buildNonToolMessage(role, rest.trim()),
      remaining: ""
    }
  }
  return {
    message: buildNonToolMessage(role, rest.slice(0, endIndex).trim()),
    remaining: rest.slice(endIndex)
  }
}

const skipToNextPrefix = (text: string, prefixes: string[]): string => {
  const nextIndex = findNextBoundary(text, prefixes)
  if (nextIndex <= 0) {
    return ""
  }
  return text.slice(nextIndex)
}

const buildChatMessages = (
  text: string,
  template: NormalizedTemplate,
  chatMode: boolean
): ChatMessage[] => {
  const trimmed = text.trim()
  if (!trimmed) return []
  if (!chatMode) {
    return [{ role: "user", content: trimmed }]
  }
  const prefixes = [
    template.systemPrefix,
    template.userPrefix,
    template.assistantPrefix
  ].filter(Boolean)
  if (prefixes.length === 0 || !prefixes.some((p) => trimmed.includes(p))) {
    return [{ role: "user", content: trimmed }]
  }
  let remaining = trimmed
  const messages: ChatMessage[] = []
  while (remaining.length > 0) {
    const systemBoundaries = [
      template.systemSuffix,
      template.userPrefix,
      template.assistantPrefix
    ].filter(Boolean)
    const userBoundaries = [
      template.userSuffix || template.assistantPrefix,
      template.assistantPrefix,
      template.systemPrefix
    ].filter(Boolean)
    const assistantBoundaries = [
      template.assistantSuffix || template.userPrefix,
      template.userPrefix,
      template.systemPrefix
    ].filter(Boolean)

    let extracted =
      template.systemPrefix &&
      extractMessage(remaining, template.systemPrefix, systemBoundaries, "system")
    if (!extracted && template.userPrefix) {
      extracted = extractMessage(remaining, template.userPrefix, userBoundaries, "user")
    }
    if (!extracted && template.assistantPrefix) {
      extracted = extractMessage(
        remaining,
        template.assistantPrefix,
        assistantBoundaries,
        "assistant"
      )
    }
    if (!extracted) {
      remaining = skipToNextPrefix(remaining, prefixes)
      continue
    }
    if (extracted.message.content) {
      messages.push(extracted.message)
    }
    remaining = extracted.remaining.trimStart()
  }
  if (messages.length === 0) {
    return [{ role: "user", content: trimmed }]
  }
  const last = messages[messages.length - 1]
  if (last.role === "assistant" && !last.content.trim()) {
    messages.pop()
  }
  return messages
}

const isAbortError = (error: unknown): boolean => {
  if (!error) return false
  if (error instanceof Error) {
    if (error.name === "AbortError") return true
    if (error.message.toLowerCase().includes("aborted")) return true
  }
  const cause = (error as { cause?: unknown } | null)?.cause
  if (cause instanceof Error) {
    return (
      cause.name === "AbortError" ||
      cause.message.toLowerCase().includes("aborted")
    )
  }
  return false
}

const wait = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })

const getSettingsFromPayload = (
  payload?: Record<string, unknown> | null
): WritingSessionSettings => {
  if (!isRecord(payload)) return cloneDefaultSettings()
  const raw = payload.settings
  const settings = isRecord(raw) ? raw : {}
  const advancedExtraBody = pickAdvancedExtraBodyFromSettings(settings)
  const memoryBlock = normalizeContextBlock(
    settings.memory_block ?? settings.memoryBlock,
    DEFAULT_MEMORY_BLOCK
  )
  const authorNote = normalizeAuthorNote(
    settings.author_note ?? settings.authorNote
  )
  const worldInfo = normalizeWorldInfoSettings(
    settings.world_info ?? settings.worldInfo
  )
  return {
    temperature: toNumber(settings.temperature, DEFAULT_SETTINGS.temperature),
    top_p: toNumber(settings.top_p, DEFAULT_SETTINGS.top_p),
    top_k: toNumber(settings.top_k, DEFAULT_SETTINGS.top_k),
    max_tokens: Math.max(
      1,
      Math.round(toNumber(settings.max_tokens, DEFAULT_SETTINGS.max_tokens))
    ),
    presence_penalty: toNumber(
      settings.presence_penalty,
      DEFAULT_SETTINGS.presence_penalty
    ),
    frequency_penalty: toNumber(
      settings.frequency_penalty,
      DEFAULT_SETTINGS.frequency_penalty
    ),
    seed: toNullableNumber(settings.seed, DEFAULT_SETTINGS.seed),
    stop: normalizeStopStrings(settings.stop),
    advanced_extra_body: advancedExtraBody,
    memory_block: memoryBlock,
    author_note: authorNote,
    world_info: worldInfo
  }
}

const getPromptFromPayload = (payload?: Record<string, unknown> | null): string => {
  if (!isRecord(payload)) return ""
  const prompt = payload.prompt
  return typeof prompt === "string" ? prompt : ""
}

const getTemplateNameFromPayload = (
  payload?: Record<string, unknown> | null
): string | null => {
  if (!isRecord(payload)) return null
  const raw = payload.template_name ?? payload.templateName ?? payload.template
  if (typeof raw === "string" && raw.trim()) return raw.trim()
  return null
}

const getThemeNameFromPayload = (
  payload?: Record<string, unknown> | null
): string | null => {
  if (!isRecord(payload)) return null
  const raw = payload.theme_name ?? payload.themeName ?? payload.theme
  if (typeof raw === "string" && raw.trim()) return raw.trim()
  return null
}

const getChatModeFromPayload = (
  payload?: Record<string, unknown> | null
): boolean => {
  if (!isRecord(payload)) return false
  const raw = payload.chat_mode ?? payload.chatMode
  return Boolean(raw)
}

const mergePayloadIntoSession = (
  payload: Record<string, unknown> | null | undefined,
  prompt: string,
  settings: WritingSessionSettings,
  templateName: string | null,
  themeName: string | null,
  chatMode: boolean
): WritingSessionPayload => {
  const base = isRecord(payload) ? payload : {}
  return {
    ...base,
    prompt,
    settings,
    template_name: templateName,
    theme_name: themeName,
    chat_mode: chatMode
  }
}

const areSettingsEqual = (
  left: WritingSessionSettings,
  right: WritingSessionSettings
): boolean => {
  if (left.temperature !== right.temperature) return false
  if (left.top_p !== right.top_p) return false
  if (left.top_k !== right.top_k) return false
  if (left.max_tokens !== right.max_tokens) return false
  if (left.presence_penalty !== right.presence_penalty) return false
  if (left.frequency_penalty !== right.frequency_penalty) return false
  if (left.seed !== right.seed) return false
  if (left.stop.length !== right.stop.length) return false
  if (!left.stop.every((value, index) => value === right.stop[index])) return false
  const leftAdvanced = JSON.stringify(left.advanced_extra_body || {})
  const rightAdvanced = JSON.stringify(right.advanced_extra_body || {})
  if (leftAdvanced !== rightAdvanced) return false
  const leftMemory = JSON.stringify(left.memory_block || {})
  const rightMemory = JSON.stringify(right.memory_block || {})
  if (leftMemory !== rightMemory) return false
  const leftAuthor = JSON.stringify(left.author_note || {})
  const rightAuthor = JSON.stringify(right.author_note || {})
  if (leftAuthor !== rightAuthor) return false
  const leftWorldInfo = JSON.stringify(left.world_info || {})
  const rightWorldInfo = JSON.stringify(right.world_info || {})
  return leftWorldInfo === rightWorldInfo
}

export const WritingPlayground = () => {
  const { t } = useTranslation(["option"])
  const queryClient = useQueryClient()
  const isOnline = useServerOnline()
  const { capabilities } = useServerCapabilities()
  const {
    activeSessionId,
    activeSessionName,
    setActiveSessionId,
    setActiveSessionName
  } = useWritingPlaygroundStore()
  const [selectedModel] = useStorage<string>("selectedModel")
  const apiProviderOverride = useStoreChatModelSettings(
    (state) => state.apiProvider
  )
  const [sessionUsageMap, setSessionUsageMap] = useStorage<SessionUsageMap>(
    "writing:session-usage",
    {}
  )
  const [createModalOpen, setCreateModalOpen] = React.useState(false)
  const [newSessionName, setNewSessionName] = React.useState("")
  const [sessionImporting, setSessionImporting] = React.useState(false)
  const [renameModalOpen, setRenameModalOpen] = React.useState(false)
  const [renameSessionName, setRenameSessionName] = React.useState("")
  const [renameTarget, setRenameTarget] =
    React.useState<WritingSessionListItem | null>(null)
  const [editorText, setEditorText] = React.useState("")
  const [editorView, setEditorView] = React.useState<EditorViewMode>("edit")
  const [settings, setSettings] =
    React.useState<WritingSessionSettings>(() => cloneDefaultSettings())
  const [stopStringsInput, setStopStringsInput] = React.useState("")
  const [bannedTokensInput, setBannedTokensInput] = React.useState("")
  const [drySequenceBreakersInput, setDrySequenceBreakersInput] =
    React.useState("")
  const [extraBodyJsonModalOpen, setExtraBodyJsonModalOpen] =
    React.useState(false)
  const [extraBodyJsonDraft, setExtraBodyJsonDraft] = React.useState("{}")
  const [extraBodyJsonError, setExtraBodyJsonError] =
    React.useState<string | null>(null)
  const [selectedTemplateName, setSelectedTemplateName] =
    React.useState<string | null>(null)
  const [selectedThemeName, setSelectedThemeName] =
    React.useState<string | null>(null)
  const [chatMode, setChatMode] = React.useState(false)
  const [templatesModalOpen, setTemplatesModalOpen] = React.useState(false)
  const [templateForm, setTemplateForm] =
    React.useState<TemplateFormState>(EMPTY_TEMPLATE_FORM)
  const [editingTemplate, setEditingTemplate] =
    React.useState<WritingTemplateResponse | null>(null)
  const [templateImporting, setTemplateImporting] = React.useState(false)
  const [themesModalOpen, setThemesModalOpen] = React.useState(false)
  const [themeForm, setThemeForm] =
    React.useState<ThemeFormState>(EMPTY_THEME_FORM)
  const [editingTheme, setEditingTheme] =
    React.useState<WritingThemeResponse | null>(null)
  const [themeImporting, setThemeImporting] = React.useState(false)
  const [searchOpen, setSearchOpen] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [replaceQuery, setReplaceQuery] = React.useState("")
  const [matchCase, setMatchCase] = React.useState(false)
  const [useRegex, setUseRegex] = React.useState(false)
  const [activeMatchIndex, setActiveMatchIndex] = React.useState(0)
  const [isDirty, setIsDirty] = React.useState(false)
  const [lastSavedAt, setLastSavedAt] = React.useState<number | null>(null)
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [canUndoGeneration, setCanUndoGeneration] = React.useState(false)
  const [canRedoGeneration, setCanRedoGeneration] = React.useState(false)
  const [tokenCountResult, setTokenCountResult] =
    React.useState<WritingTokenCountResponse | null>(null)
  const [tokenizeResult, setTokenizeResult] =
    React.useState<WritingTokenizeResponse | null>(null)
  const [tokenInspectorError, setTokenInspectorError] =
    React.useState<string | null>(null)
  const [isCountingTokens, setIsCountingTokens] = React.useState(false)
  const [isTokenizingText, setIsTokenizingText] = React.useState(false)
  const [wordcloudId, setWordcloudId] = React.useState<string | null>(null)
  const [wordcloudStatus, setWordcloudStatus] = React.useState<string | null>(null)
  const [wordcloudWords, setWordcloudWords] =
    React.useState<Array<{ text: string; weight: number }>>([])
  const [wordcloudMeta, setWordcloudMeta] = React.useState<{
    input_chars: number
    total_tokens: number
    top_n: number
  } | null>(null)
  const [wordcloudError, setWordcloudError] = React.useState<string | null>(null)
  const [isGeneratingWordcloud, setIsGeneratingWordcloud] = React.useState(false)
  const [wordcloudMaxWords, setWordcloudMaxWords] = React.useState(100)
  const [wordcloudMinWordLength, setWordcloudMinWordLength] = React.useState(3)
  const [wordcloudKeepNumbers, setWordcloudKeepNumbers] = React.useState(false)
  const [wordcloudStopwordsInput, setWordcloudStopwordsInput] = React.useState("")
  const wordcloudRequestSeqRef = React.useRef(0)
  const wordcloudUnmountedRef = React.useRef(false)
  const saveTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingSaveMapRef = React.useRef<Record<string, WritingSessionPayload>>({})
  const pendingQueueRef = React.useRef<string[]>([])
  const saveInFlightRef = React.useRef(false)
  const savingSessionIdRef = React.useRef<string | null>(null)
  const sessionVersionRef = React.useRef<Record<string, number>>({})
  const sessionSchemaVersionRef = React.useRef<Record<string, number>>({})
  const lastLoadedSessionIdRef = React.useRef<string | null>(null)
  const lastSavedPromptRef = React.useRef<Record<string, string>>({})
  const lastSavedSettingsRef =
    React.useRef<Record<string, WritingSessionSettings>>({})
  const lastSavedTemplateNameRef = React.useRef<Record<string, string | null>>({})
  const lastSavedThemeNameRef = React.useRef<Record<string, string | null>>({})
  const lastSavedChatModeRef = React.useRef<Record<string, boolean>>({})
  const templateFileInputRef = React.useRef<HTMLInputElement | null>(null)
  const sessionFileInputRef = React.useRef<HTMLInputElement | null>(null)
  const themeFileInputRef = React.useRef<HTMLInputElement | null>(null)
  const generationServiceRef = React.useRef(new TldwChatService())
  const generationUndoRef = React.useRef<GenerationHistoryEntry[]>([])
  const generationRedoRef = React.useRef<GenerationHistoryEntry[]>([])
  const generationSessionIdRef = React.useRef<string | null>(null)
  const generationCancelledRef = React.useRef(false)
  const editorRef = React.useRef<TextAreaRef | null>(null)
  const previewRef = React.useRef<HTMLDivElement | null>(null)
  const isSyncingScrollRef = React.useRef(false)
  const {
    data: writingCaps,
    isLoading: capsLoading,
    error: capsError
  } = useQuery({
    queryKey: ["writing-capabilities"],
    queryFn: () => getWritingCapabilities({ includeProviders: false }),
    enabled: isOnline,
    staleTime: 5 * 60 * 1000
  })
  const hasWriting = Boolean(writingCaps?.server?.sessions)
  const hasTemplates = Boolean(writingCaps?.server?.templates)
  const hasThemes = Boolean(writingCaps?.server?.themes)
  const hasChat = capabilities?.hasChat !== false

  const { data: requestedCaps, isLoading: requestedCapsLoading } = useQuery({
    queryKey: [
      "writing-capabilities",
      "requested",
      selectedModel || "",
      apiProviderOverride || ""
    ],
    queryFn: async () => {
      const provider = await resolveApiProviderForModel({
        modelId: selectedModel,
        explicitProvider: apiProviderOverride
      })
      return await getWritingCapabilities({
        provider,
        model: selectedModel || undefined,
        includeProviders: false
      })
    },
    enabled: isOnline && hasWriting && Boolean(selectedModel),
    staleTime: 60 * 1000
  })

  const extraBodyCompat: WritingExtraBodyCompat | null =
    requestedCaps?.requested?.extra_body_compat ?? null

  const showOffline = !isOnline
  const showUnsupported =
    !showOffline && !capsLoading && (!hasWriting || Boolean(capsError))

  const {
    data: sessionsData,
    isLoading: sessionsLoading,
    isFetching: sessionsFetching,
    error: sessionsError
  } = useQuery({
    queryKey: ["writing-sessions"],
    queryFn: () => listWritingSessions({ limit: 200 }),
    enabled: isOnline && hasWriting,
    staleTime: 30 * 1000
  })
  const sessions = sessionsData?.sessions ?? []

  const {
    data: activeSessionDetail,
    isLoading: activeSessionLoading,
    error: activeSessionError
  } = useQuery({
    queryKey: ["writing-session", activeSessionId],
    queryFn: () => getWritingSession(activeSessionId ?? ""),
    enabled: isOnline && hasWriting && Boolean(activeSessionId),
    staleTime: 30 * 1000
  })

  const {
    data: templatesData,
    isLoading: templatesLoading,
    error: templatesError
  } = useQuery({
    queryKey: ["writing-templates"],
    queryFn: () => listWritingTemplates({ limit: 200 }),
    enabled: isOnline && hasWriting && hasTemplates,
    staleTime: 60 * 1000
  })

  const {
    data: themesData,
    isLoading: themesLoading,
    error: themesError
  } = useQuery({
    queryKey: ["writing-themes"],
    queryFn: () => listWritingThemes({ limit: 200 }),
    enabled: isOnline && hasWriting && hasThemes,
    staleTime: 60 * 1000
  })

  const isVersionConflictError = (error: unknown) => {
    const status = (error as { status?: number } | null)?.status
    const msg = String((error as { message?: string } | null)?.message || "")
    const lower = msg.toLowerCase()
    return (
      status === 409 ||
      lower.includes("expected-version") ||
      lower.includes("expected_version") ||
      lower.includes("version mismatch")
    )
  }

  const refreshSessionData = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
    if (activeSessionId) {
      queryClient.invalidateQueries({
        queryKey: ["writing-session", activeSessionId]
      })
    }
  }, [activeSessionId, queryClient])

  const handleVersionConflict = React.useCallback(() => {
    refreshSessionData()
    message.error({
      content: (
        <span
          className="inline-flex items-center gap-2"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              refreshSessionData()
            }
          }}>
          <span>
            {t(
              "option:writingPlayground.conflictError",
              "Session changed on the server."
            )}
          </span>
          <Button
            type="link"
            size="small"
            onClick={refreshSessionData}
            aria-label={t("option:reloadFromServer", "Reload from server")}>
            {t("option:reloadFromServer", "Reload from server")}
          </Button>
        </span>
      ),
      duration: 6
    })
  }, [refreshSessionData, t])

  const createSessionMutation = useMutation({
    mutationFn: (name: string) =>
      createWritingSession({
        name,
        payload: {
          prompt: "",
          settings: cloneDefaultSettings(),
          template_name: null,
          theme_name: null,
          chat_mode: false
        },
        schema_version: 1
      }),
    onSuccess: (session) => {
      message.success(
        t(
          "option:writingPlayground.createSuccess",
          "Session created."
        )
      )
      queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
      setCreateModalOpen(false)
      setNewSessionName("")
      setActiveSessionId(session.id)
      setActiveSessionName(session.name)
      const nextUsage = {
        ...(sessionUsageMap || {}),
        [session.id]: { name: session.name, lastUsedAt: Date.now() }
      }
      setSessionUsageMap(nextUsage)
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t("option:writingPlayground.createError", "Failed to create session: {{detail}}", {
          detail
        })
      )
    }
  })

  const renameSessionMutation = useMutation({
    mutationFn: (payload: { session: WritingSessionListItem; name: string }) =>
      updateWritingSession(
        payload.session.id,
        { name: payload.name },
        payload.session.version
      ),
    onSuccess: (session, payload) => {
      message.success(
        t(
          "option:writingPlayground.renameSuccess",
          "Session renamed."
        )
      )
      queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
      setRenameModalOpen(false)
      setRenameTarget(null)
      setRenameSessionName("")
      if (activeSessionId === payload.session.id) {
        setActiveSessionName(session.name)
      }
      const nextUsage = { ...(sessionUsageMap || {}) }
      if (nextUsage[payload.session.id]) {
        nextUsage[payload.session.id] = {
          ...nextUsage[payload.session.id],
          name: session.name
        }
        setSessionUsageMap(nextUsage)
      }
    },
    onError: (err) => {
      if (isVersionConflictError(err)) {
        handleVersionConflict()
        setRenameModalOpen(false)
        setRenameTarget(null)
        setRenameSessionName("")
        return
      }
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t("option:writingPlayground.renameError", "Failed to rename session: {{detail}}", {
          detail
        })
      )
    }
  })

  const deleteSessionMutation = useMutation({
    mutationFn: (payload: { session: WritingSessionListItem }) =>
      deleteWritingSession(payload.session.id, payload.session.version),
    onSuccess: (_data, payload) => {
      message.success(
        t("option:writingPlayground.deleteSuccess", "Session deleted.")
      )
      queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
      if (activeSessionId === payload.session.id) {
        setActiveSessionId(null)
        setActiveSessionName(null)
      }
      const nextUsage = { ...(sessionUsageMap || {}) }
      if (nextUsage[payload.session.id]) {
        delete nextUsage[payload.session.id]
        setSessionUsageMap(nextUsage)
      }
    },
    onError: (err) => {
      if (isVersionConflictError(err)) {
        handleVersionConflict()
        return
      }
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t("option:writingPlayground.deleteError", "Failed to delete session: {{detail}}", {
          detail
        })
      )
    }
  })

  const saveSessionMutation = useMutation({
    mutationFn: (payload: PendingSave & { expectedVersion: number }) =>
      updateWritingSession(
        payload.sessionId,
        {
          payload: payload.payload,
          schema_version:
            sessionSchemaVersionRef.current[payload.sessionId] ?? 1
        },
        payload.expectedVersion
      ),
    onMutate: () => {
      saveInFlightRef.current = true
    },
    onSuccess: (session, payload) => {
      saveInFlightRef.current = false
      if (savingSessionIdRef.current === session.id) {
        savingSessionIdRef.current = null
      }
      sessionVersionRef.current[session.id] = session.version
      sessionSchemaVersionRef.current[session.id] = session.schema_version
      lastSavedPromptRef.current[session.id] = getPromptFromPayload(session.payload)
      lastSavedSettingsRef.current[session.id] = getSettingsFromPayload(session.payload)
      lastSavedTemplateNameRef.current[session.id] =
        getTemplateNameFromPayload(session.payload)
      lastSavedThemeNameRef.current[session.id] =
        getThemeNameFromPayload(session.payload)
      lastSavedChatModeRef.current[session.id] = getChatModeFromPayload(
        session.payload
      )
      queryClient.setQueryData(
        ["writing-session", session.id],
        session
      )
      queryClient.setQueryData<WritingSessionListResponse | undefined>(
        ["writing-sessions"],
        (prev) => {
          if (!prev) return prev
          return {
            ...prev,
            sessions: prev.sessions.map((item) =>
              item.id === session.id
                ? {
                    ...item,
                    name: session.name,
                    last_modified: session.last_modified,
                    version: session.version
                  }
                : item
            )
          }
        }
      )
      const pendingPayload = pendingSaveMapRef.current[session.id]
      if (!pendingPayload || pendingPayload === payload.payload) {
        delete pendingSaveMapRef.current[session.id]
      }
      if (activeSessionId === session.id) {
        setLastSavedAt(Date.now())
        if (!pendingSaveMapRef.current[session.id]) {
          setIsDirty(false)
        }
      }
      if (!saveInFlightRef.current) {
        flushNextSave()
      }
    },
    onError: (err) => {
      saveInFlightRef.current = false
      savingSessionIdRef.current = null
      if (isVersionConflictError(err)) {
        handleVersionConflict()
        return
      }
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t("option:writingPlayground.saveError", "Failed to save session: {{detail}}", {
          detail
        })
      )
    }
  })

  const cloneSessionMutation = useMutation({
    mutationFn: (payload: { session: WritingSessionListItem }) =>
      cloneWritingSession(payload.session.id),
    onSuccess: (session) => {
      message.success(
        t("option:writingPlayground.cloneSuccess", "Session cloned.")
      )
      queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
      setActiveSessionId(session.id)
      setActiveSessionName(session.name)
      const nextUsage = {
        ...(sessionUsageMap || {}),
        [session.id]: { name: session.name, lastUsedAt: Date.now() }
      }
      setSessionUsageMap(nextUsage)
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t("option:writingPlayground.cloneError", "Failed to clone session: {{detail}}", {
          detail
        })
      )
    }
  })

  const exportSession = React.useCallback(
    async (session: WritingSessionListItem) => {
      try {
        const detail = await getWritingSession(session.id)
        const payload = {
          name: detail.name,
          payload: detail.payload,
          schema_version: detail.schema_version
        }
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json"
        })
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = `${detail.name || "session"}.json`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        message.success(
          t(
            "option:writingPlayground.sessionExportSuccess",
            "Session exported."
          )
        )
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : t("option:error", "Error")
        message.error(
          t(
            "option:writingPlayground.sessionExportError",
            "Failed to export session: {{detail}}",
            { detail }
          )
        )
      }
    },
    [t]
  )

  const handleSessionImport = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      setSessionImporting(true)
      try {
        const raw = await file.text()
        const parsed = JSON.parse(raw)
        const items = Array.isArray(parsed)
          ? parsed
          : Array.isArray(parsed?.sessions)
            ? parsed.sessions
            : parsed
              ? [parsed]
              : []
        if (!Array.isArray(items) || items.length === 0) {
          message.error(
            t(
              "option:writingPlayground.sessionImportInvalid",
              "No sessions found in file."
            )
          )
          return
        }
        const existingNames = new Set(sessions.map((session) => session.name))
        const resolveName = (base: string) => {
          if (!existingNames.has(base)) return base
          let idx = 1
          let candidate = `${base} (imported)`
          while (existingNames.has(candidate)) {
            idx += 1
            candidate = `${base} (imported ${idx})`
          }
          return candidate
        }
        for (const item of items) {
          if (!isRecord(item)) continue
          const rawName = String(item.name || item.title || "").trim()
          const name = resolveName(rawName || `Imported session ${Date.now()}`)
          existingNames.add(name)
          const payload = isRecord(item.payload)
            ? item.payload
            : isRecord(item.payload_json)
              ? item.payload_json
              : {}
          const schemaVersion =
            typeof item.schema_version === "number" ? item.schema_version : 1
          await createWritingSession({
            name,
            payload,
            schema_version: schemaVersion
          })
        }
        queryClient.invalidateQueries({ queryKey: ["writing-sessions"] })
        message.success(
          t(
            "option:writingPlayground.sessionImportSuccess",
            "Sessions imported."
          )
        )
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : t("option:error", "Error")
        message.error(
          t(
            "option:writingPlayground.sessionImportError",
            "Import failed: {{detail}}",
            { detail }
          )
        )
      } finally {
        setSessionImporting(false)
        event.target.value = ""
      }
    },
    [queryClient, sessions, t]
  )

  React.useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [])

  React.useEffect(() => {
    return () => {
      generationServiceRef.current.cancelStream()
    }
  }, [])

  React.useEffect(() => {
    wordcloudUnmountedRef.current = false
    return () => {
      wordcloudUnmountedRef.current = true
    }
  }, [])

  React.useEffect(() => {
    generationUndoRef.current = []
    generationRedoRef.current = []
    generationSessionIdRef.current = null
    generationCancelledRef.current = false
    setCanUndoGeneration(false)
    setCanRedoGeneration(false)
    setWordcloudId(null)
    setWordcloudStatus(null)
    setWordcloudWords([])
    setWordcloudMeta(null)
    setWordcloudError(null)
    setIsGeneratingWordcloud(false)
  }, [activeSessionId])

  const templates = templatesData?.templates ?? []
  const themes = themesData?.themes ?? []
  const defaultTemplate =
    templates.find((template) => template.is_default) ?? templates[0] ?? null
  const selectedTemplate =
    templates.find((template) => template.name === selectedTemplateName) ?? null
  const effectiveTemplate = normalizeTemplatePayload(
    selectedTemplate ?? defaultTemplate
  )
  const templateOptions = templates.map((template) => ({
    value: template.name,
    label: template.name
  }))
  const defaultTheme = themes.find((theme) => theme.is_default) ?? themes[0] ?? null
  const selectedTheme =
    themes.find((theme) => theme.name === selectedThemeName) ?? null
  const effectiveTheme = normalizeThemeResponse(selectedTheme ?? defaultTheme)
  const themeOptions = themes.map((theme) => ({
    value: theme.name,
    label: theme.name
  }))
  const activeThemeClassName = effectiveTheme.className.trim()
  const activeThemeCss = React.useMemo(
    () => sanitizeThemeCss(effectiveTheme.css),
    [effectiveTheme.css]
  )
  const sortedSessions = React.useMemo(() => {
    const usage = sessionUsageMap || {}
    return sessions
      .map((session, index) => ({
        session,
        index,
        lastUsedAt: usage[session.id]?.lastUsedAt ?? 0
      }))
      .sort((a, b) => {
        if (a.lastUsedAt !== b.lastUsedAt) {
          return b.lastUsedAt - a.lastUsedAt
        }
        return a.index - b.index
      })
  }, [sessions, sessionUsageMap])

  const handleSelectSession = React.useCallback(
    (session: WritingSessionListItem) => {
      if (isGenerating) {
        message.info(
          t(
            "option:writingPlayground.generationInProgress",
            "Stop generation before switching sessions."
          )
        )
        return
      }
      setActiveSessionId(session.id)
      setActiveSessionName(session.name)
      const nextUsage = {
        ...(sessionUsageMap || {}),
        [session.id]: { name: session.name, lastUsedAt: Date.now() }
      }
      setSessionUsageMap(nextUsage)
    },
    [
      isGenerating,
      setActiveSessionId,
      setActiveSessionName,
      sessionUsageMap,
      setSessionUsageMap,
      t
    ]
  )

  React.useEffect(() => {
    if (!activeSessionId) return
    const match = sessions.find((session) => session.id === activeSessionId)
    if (match && match.name !== activeSessionName) {
      setActiveSessionName(match.name)
    }
  }, [activeSessionId, activeSessionName, sessions, setActiveSessionName])

  React.useEffect(() => {
    if (!activeSessionId) return
    if (sessionsFetching) return
    const exists = sessions.some((session) => session.id === activeSessionId)
    if (!exists) {
      setActiveSessionId(null)
      setActiveSessionName(null)
    }
  }, [
    activeSessionId,
    sessions,
    sessionsFetching,
    setActiveSessionId,
    setActiveSessionName
  ])

  React.useEffect(() => {
    if (!activeSessionDetail) {
      setEditorText("")
      setSettings(cloneDefaultSettings())
      setStopStringsInput("")
      setBannedTokensInput("")
      setDrySequenceBreakersInput("")
      setSelectedTemplateName(null)
      setSelectedThemeName(null)
      setChatMode(false)
      setIsDirty(false)
      setTokenCountResult(null)
      setTokenizeResult(null)
      setTokenInspectorError(null)
      setWordcloudId(null)
      setWordcloudStatus(null)
      setWordcloudWords([])
      setWordcloudMeta(null)
      setWordcloudError(null)
      setIsGeneratingWordcloud(false)
      lastLoadedSessionIdRef.current = null
      return
    }
    sessionVersionRef.current[activeSessionDetail.id] = activeSessionDetail.version
    sessionSchemaVersionRef.current[activeSessionDetail.id] =
      activeSessionDetail.schema_version
    const nextPrompt = getPromptFromPayload(activeSessionDetail.payload)
    const nextSettings = getSettingsFromPayload(activeSessionDetail.payload)
    const nextTemplateName = getTemplateNameFromPayload(activeSessionDetail.payload)
    const nextThemeName = getThemeNameFromPayload(activeSessionDetail.payload)
    const nextChatMode = getChatModeFromPayload(activeSessionDetail.payload)
    const lastLoadedId = lastLoadedSessionIdRef.current
    if (activeSessionDetail.id !== lastLoadedId) {
      setEditorText(nextPrompt)
      setSettings(nextSettings)
      setStopStringsInput(nextSettings.stop.join("\n"))
      setBannedTokensInput(
        normalizeStringArrayValue(nextSettings.advanced_extra_body.banned_tokens).join(
          "\n"
        )
      )
      setDrySequenceBreakersInput(
        normalizeStringArrayValue(
          nextSettings.advanced_extra_body.dry_sequence_breakers
        ).join("\n")
      )
      setSelectedTemplateName(nextTemplateName)
      setSelectedThemeName(nextThemeName)
      setChatMode(nextChatMode)
      setIsDirty(false)
      setTokenCountResult(null)
      setTokenizeResult(null)
      setTokenInspectorError(null)
      setWordcloudId(null)
      setWordcloudStatus(null)
      setWordcloudWords([])
      setWordcloudMeta(null)
      setWordcloudError(null)
      setIsGeneratingWordcloud(false)
      setLastSavedAt(Date.now())
      lastSavedPromptRef.current[activeSessionDetail.id] = nextPrompt
      lastSavedSettingsRef.current[activeSessionDetail.id] = nextSettings
      lastSavedTemplateNameRef.current[activeSessionDetail.id] = nextTemplateName
      lastSavedThemeNameRef.current[activeSessionDetail.id] = nextThemeName
      lastSavedChatModeRef.current[activeSessionDetail.id] = nextChatMode
      lastLoadedSessionIdRef.current = activeSessionDetail.id
      return
    }
    if (!isDirty) {
      if (editorText !== nextPrompt) {
        setEditorText(nextPrompt)
      }
      if (!areSettingsEqual(settings, nextSettings)) {
        setSettings(nextSettings)
        setStopStringsInput(nextSettings.stop.join("\n"))
        setBannedTokensInput(
          normalizeStringArrayValue(
            nextSettings.advanced_extra_body.banned_tokens
          ).join("\n")
        )
        setDrySequenceBreakersInput(
          normalizeStringArrayValue(
            nextSettings.advanced_extra_body.dry_sequence_breakers
          ).join("\n")
        )
      }
      if (selectedTemplateName !== nextTemplateName) {
        setSelectedTemplateName(nextTemplateName)
      }
      if (selectedThemeName !== nextThemeName) {
        setSelectedThemeName(nextThemeName)
      }
      if (chatMode !== nextChatMode) {
        setChatMode(nextChatMode)
      }
      setLastSavedAt(Date.now())
      lastSavedPromptRef.current[activeSessionDetail.id] = nextPrompt
      lastSavedSettingsRef.current[activeSessionDetail.id] = nextSettings
      lastSavedTemplateNameRef.current[activeSessionDetail.id] = nextTemplateName
      lastSavedThemeNameRef.current[activeSessionDetail.id] = nextThemeName
      lastSavedChatModeRef.current[activeSessionDetail.id] = nextChatMode
    }
  }, [
    activeSessionDetail,
    chatMode,
    editorText,
    isDirty,
    selectedTemplateName,
    selectedThemeName,
    settings
  ])

  React.useEffect(() => {
    setTokenCountResult(null)
    setTokenizeResult(null)
    setTokenInspectorError(null)
    setWordcloudId(null)
    setWordcloudStatus(null)
    setWordcloudWords([])
    setWordcloudMeta(null)
    setWordcloudError(null)
    setIsGeneratingWordcloud(false)
  }, [selectedModel])

  const openRenameModal = React.useCallback(
    (session: WritingSessionListItem) => {
      setRenameTarget(session)
      setRenameSessionName(session.name)
      setRenameModalOpen(true)
    },
    []
  )

  const confirmDeleteSession = React.useCallback(
    (session: WritingSessionListItem) => {
      Modal.confirm({
        title: t("option:writingPlayground.deleteSessionTitle", "Delete session?"),
        content: t(
          "option:writingPlayground.deleteSessionBody",
          "This will permanently delete the session."
        ),
        okText: t("common:delete", "Delete"),
        okButtonProps: { danger: true },
        cancelText: t("common:cancel", "Cancel"),
        onOk: () => deleteSessionMutation.mutateAsync({ session })
      })
    },
    [deleteSessionMutation, t]
  )

  const activeSession = activeSessionId
    ? sessions.find((session) => session.id === activeSessionId)
    : null

  const flushNextSave = React.useCallback(() => {
    if (saveInFlightRef.current) return
    const queue = pendingQueueRef.current
    while (queue.length > 0) {
      const sessionId = queue.shift()
      if (!sessionId) continue
      const payload = pendingSaveMapRef.current[sessionId]
      if (!payload) continue
      const expectedVersion = sessionVersionRef.current[sessionId]
      if (expectedVersion == null) {
        delete pendingSaveMapRef.current[sessionId]
        continue
      }
      savingSessionIdRef.current = sessionId
      saveSessionMutation.mutate({
        sessionId,
        payload,
        expectedVersion
      })
      return
    }
  }, [saveSessionMutation])

  const scheduleSave = React.useCallback(
    (sessionId: string, payload: WritingSessionPayload) => {
      pendingSaveMapRef.current[sessionId] = payload
      if (!pendingQueueRef.current.includes(sessionId)) {
        pendingQueueRef.current.push(sessionId)
      }
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null
        flushNextSave()
      }, SAVE_DEBOUNCE_MS)
    },
    [flushNextSave]
  )

  const clearPendingSave = React.useCallback((sessionId: string) => {
    delete pendingSaveMapRef.current[sessionId]
    pendingQueueRef.current = pendingQueueRef.current.filter(
      (queuedId) => queuedId !== sessionId
    )
    if (pendingQueueRef.current.length === 0 && saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
    }
  }, [])

  const computeDirty = React.useCallback(
    (
      sessionId: string,
      prompt: string,
      nextSettings: WritingSessionSettings,
      templateName: string | null,
      themeName: string | null,
      nextChatMode: boolean
    ) => {
      const lastPrompt = lastSavedPromptRef.current[sessionId] ?? ""
      const lastSettings =
        lastSavedSettingsRef.current[sessionId] ?? DEFAULT_SETTINGS
      const lastTemplate = lastSavedTemplateNameRef.current[sessionId] ?? null
      const lastTheme = lastSavedThemeNameRef.current[sessionId] ?? null
      const lastChatMode = lastSavedChatModeRef.current[sessionId] ?? false
      return (
        prompt !== lastPrompt ||
        !areSettingsEqual(nextSettings, lastSettings) ||
        templateName !== lastTemplate ||
        themeName !== lastTheme ||
        nextChatMode !== lastChatMode
      )
    },
    []
  )

  const focusEditorSelection = React.useCallback(
    (start: number, end: number) => {
      if (editorView === "preview") {
        setEditorView("edit")
      }
      window.setTimeout(() => {
        const editorEl = editorRef.current?.resizableTextArea?.textArea
        if (!editorEl) return
        editorEl.focus()
        editorEl.setSelectionRange(start, end)
      }, 0)
    },
    [editorView]
  )

  const applyPromptValue = React.useCallback(
    (
      nextValue: string,
      selection?: { start: number; end: number }
    ) => {
      setEditorText(nextValue)
      if (!activeSessionDetail) return
      const nextPayload = mergePayloadIntoSession(
        activeSessionDetail.payload,
        nextValue,
        settings,
        selectedTemplateName,
        selectedThemeName,
        chatMode
      )
      const isDirtyNext = computeDirty(
        activeSessionDetail.id,
        nextValue,
        settings,
        selectedTemplateName,
        selectedThemeName,
        chatMode
      )
      setIsDirty(isDirtyNext)
      if (!isDirtyNext) {
        clearPendingSave(activeSessionDetail.id)
      } else {
        scheduleSave(activeSessionDetail.id, nextPayload)
      }
      if (selection) {
        focusEditorSelection(selection.start, selection.end)
      }
    },
    [
      activeSessionDetail,
      chatMode,
      clearPendingSave,
      computeDirty,
      focusEditorSelection,
      scheduleSave,
      selectedTemplateName,
      selectedThemeName,
      settings
    ]
  )

  const syncScroll = React.useCallback((source: "editor" | "preview") => {
    if (editorView !== "split") return
    if (isSyncingScrollRef.current) return
    const editorEl = editorRef.current?.resizableTextArea?.textArea
    const previewEl = previewRef.current
    if (!editorEl || !previewEl) return

    const sourceEl = source === "editor" ? editorEl : previewEl
    const targetEl = source === "editor" ? previewEl : editorEl
    const maxSource = sourceEl.scrollHeight - sourceEl.clientHeight
    const maxTarget = targetEl.scrollHeight - targetEl.clientHeight
    if (maxSource <= 0 || maxTarget <= 0) return
    const ratio = sourceEl.scrollTop / maxSource

    isSyncingScrollRef.current = true
    targetEl.scrollTop = ratio * maxTarget
    window.setTimeout(() => {
      isSyncingScrollRef.current = false
    }, 0)
  }, [editorView])

  const handleSettingsChange = React.useCallback(
    (
      nextSettings: WritingSessionSettings,
      nextStopInput?: string | null
    ) => {
      if (!activeSessionDetail) return
      setSettings(nextSettings)
      if (typeof nextStopInput === "string") {
        setStopStringsInput(nextStopInput)
      }
      const nextPayload = mergePayloadIntoSession(
        activeSessionDetail.payload,
        editorText,
        nextSettings,
        selectedTemplateName,
        selectedThemeName,
        chatMode
      )
      const isDirtyNext = computeDirty(
        activeSessionDetail.id,
        editorText,
        nextSettings,
        selectedTemplateName,
        selectedThemeName,
        chatMode
      )
      setIsDirty(isDirtyNext)
      if (!isDirtyNext) {
        clearPendingSave(activeSessionDetail.id)
        return
      }
      scheduleSave(activeSessionDetail.id, nextPayload)
    },
    [
      activeSessionDetail,
      chatMode,
      clearPendingSave,
      computeDirty,
      editorText,
      scheduleSave,
      selectedTemplateName,
      selectedThemeName
    ]
  )

  const updateSetting = React.useCallback(
    (partial: Partial<WritingSessionSettings>, nextStopInput?: string) => {
      const nextSettings = { ...settings, ...partial }
      handleSettingsChange(nextSettings, nextStopInput)
    },
    [handleSettingsChange, settings]
  )

  const advancedExtraBody = React.useMemo(
    () => (isRecord(settings.advanced_extra_body) ? settings.advanced_extra_body : {}),
    [settings.advanced_extra_body]
  )
  const knownExtraBodyParams = React.useMemo(
    () =>
      Array.isArray(extraBodyCompat?.known_params)
        ? extraBodyCompat.known_params
            .map((entry) => String(entry || "").trim())
            .filter(Boolean)
        : [],
    [extraBodyCompat?.known_params]
  )
  const knownExtraBodyParamSet = React.useMemo(
    () => new Set(knownExtraBodyParams),
    [knownExtraBodyParams]
  )
  const supportsAdvancedCompat = extraBodyCompat?.supported !== false

  const shouldShowAdvancedParam = React.useCallback(
    (key: string) => {
      if (Object.prototype.hasOwnProperty.call(advancedExtraBody, key)) {
        return true
      }
      if (knownExtraBodyParamSet.size === 0) return false
      return knownExtraBodyParamSet.has(key)
    },
    [advancedExtraBody, knownExtraBodyParamSet]
  )

  const updateAdvancedExtraBodyField = React.useCallback(
    (key: string, value: unknown) => {
      const nextAdvanced = { ...advancedExtraBody }
      const shouldRemove =
        value == null ||
        (typeof value === "string" && value.trim().length === 0) ||
        (Array.isArray(value) && value.length === 0)
      if (shouldRemove) {
        delete nextAdvanced[key]
      } else {
        nextAdvanced[key] = value
      }
      updateSetting({ advanced_extra_body: nextAdvanced })
    },
    [advancedExtraBody, updateSetting]
  )

  const getAdvancedNumberValue = React.useCallback(
    (key: string): number | null => {
      const raw = advancedExtraBody[key]
      if (typeof raw === "number" && Number.isFinite(raw)) {
        return raw
      }
      if (typeof raw === "string" && raw.trim()) {
        const parsed = Number(raw)
        return Number.isFinite(parsed) ? parsed : null
      }
      return null
    },
    [advancedExtraBody]
  )

  const openExtraBodyJsonEditor = React.useCallback(() => {
    setExtraBodyJsonDraft(
      JSON.stringify(advancedExtraBody || {}, null, 2) || "{}"
    )
    setExtraBodyJsonError(null)
    setExtraBodyJsonModalOpen(true)
  }, [advancedExtraBody])

  const applyExtraBodyJsonDraft = React.useCallback(() => {
    const parsed = parseExtraBodyJsonObject(extraBodyJsonDraft)
    if (parsed.error) {
      setExtraBodyJsonError(parsed.error)
      return
    }
    updateSetting({
      advanced_extra_body: parsed.value
    })
    setBannedTokensInput(
      normalizeStringArrayValue(parsed.value.banned_tokens).join("\n")
    )
    setDrySequenceBreakersInput(
      normalizeStringArrayValue(parsed.value.dry_sequence_breakers).join("\n")
    )
    setExtraBodyJsonError(null)
    setExtraBodyJsonModalOpen(false)
  }, [extraBodyJsonDraft, updateSetting])

  const memoryBlock = settings.memory_block
  const authorNote = settings.author_note
  const worldInfo = settings.world_info
  const worldInfoEntries = worldInfo.entries

  const updateMemoryBlock = React.useCallback(
    (patch: Partial<WritingContextBlock>) => {
      updateSetting({
        memory_block: {
          ...memoryBlock,
          ...patch
        }
      })
    },
    [memoryBlock, updateSetting]
  )

  const updateAuthorNote = React.useCallback(
    (patch: Partial<WritingAuthorNote>) => {
      updateSetting({
        author_note: {
          ...authorNote,
          ...patch,
          insertion_depth: Math.max(
            1,
            Math.floor(
              toNumber(
                patch.insertion_depth ?? authorNote.insertion_depth,
                authorNote.insertion_depth
              )
            )
          )
        }
      })
    },
    [authorNote, updateSetting]
  )

  const updateWorldInfo = React.useCallback(
    (patch: Partial<WritingWorldInfoSettings>) => {
      updateSetting({
        world_info: {
          ...worldInfo,
          ...patch,
          search_range: Math.max(
            0,
            Math.floor(
              toNumber(
                patch.search_range ?? worldInfo.search_range,
                worldInfo.search_range
              )
            )
          )
        }
      })
    },
    [updateSetting, worldInfo]
  )

  const addWorldInfoEntry = React.useCallback(() => {
    const entry: WritingWorldInfoEntry = {
      id: createWorldInfoId(),
      enabled: true,
      keys: [],
      content: "",
      use_regex: false,
      case_sensitive: false
    }
    updateWorldInfo({
      entries: [...worldInfoEntries, entry]
    })
  }, [updateWorldInfo, worldInfoEntries])

  const updateWorldInfoEntry = React.useCallback(
    (entryId: string, patch: Partial<WritingWorldInfoEntry>) => {
      updateWorldInfo({
        entries: worldInfoEntries.map((entry) =>
          entry.id === entryId
            ? {
                ...entry,
                ...patch
              }
            : entry
        )
      })
    },
    [updateWorldInfo, worldInfoEntries]
  )

  const removeWorldInfoEntry = React.useCallback(
    (entryId: string) => {
      updateWorldInfo({
        entries: worldInfoEntries.filter((entry) => entry.id !== entryId)
      })
    },
    [updateWorldInfo, worldInfoEntries]
  )

  const handleTemplateChange = React.useCallback(
    (nextTemplateName: string | null) => {
      setSelectedTemplateName(nextTemplateName)
      if (!activeSessionDetail) return
      const nextPayload = mergePayloadIntoSession(
        activeSessionDetail.payload,
        editorText,
        settings,
        nextTemplateName,
        selectedThemeName,
        chatMode
      )
      const isDirtyNext = computeDirty(
        activeSessionDetail.id,
        editorText,
        settings,
        nextTemplateName,
        selectedThemeName,
        chatMode
      )
      setIsDirty(isDirtyNext)
      if (!isDirtyNext) {
        clearPendingSave(activeSessionDetail.id)
        return
      }
      scheduleSave(activeSessionDetail.id, nextPayload)
    },
    [
      activeSessionDetail,
      chatMode,
      clearPendingSave,
      computeDirty,
      editorText,
      scheduleSave,
      settings,
      selectedThemeName
    ]
  )

  const handleThemeChange = React.useCallback(
    (nextThemeName: string | null) => {
      setSelectedThemeName(nextThemeName)
      if (!activeSessionDetail) return
      const nextPayload = mergePayloadIntoSession(
        activeSessionDetail.payload,
        editorText,
        settings,
        selectedTemplateName,
        nextThemeName,
        chatMode
      )
      const isDirtyNext = computeDirty(
        activeSessionDetail.id,
        editorText,
        settings,
        selectedTemplateName,
        nextThemeName,
        chatMode
      )
      setIsDirty(isDirtyNext)
      if (!isDirtyNext) {
        clearPendingSave(activeSessionDetail.id)
        return
      }
      scheduleSave(activeSessionDetail.id, nextPayload)
    },
    [
      activeSessionDetail,
      chatMode,
      clearPendingSave,
      computeDirty,
      editorText,
      scheduleSave,
      selectedTemplateName,
      settings
    ]
  )

  const handleChatModeChange = React.useCallback(
    (nextChatMode: boolean) => {
      setChatMode(nextChatMode)
      if (!activeSessionDetail) return
      const nextPayload = mergePayloadIntoSession(
        activeSessionDetail.payload,
        editorText,
        settings,
        selectedTemplateName,
        selectedThemeName,
        nextChatMode
      )
      const isDirtyNext = computeDirty(
        activeSessionDetail.id,
        editorText,
        settings,
        selectedTemplateName,
        selectedThemeName,
        nextChatMode
      )
      setIsDirty(isDirtyNext)
      if (!isDirtyNext) {
        clearPendingSave(activeSessionDetail.id)
        return
      }
      scheduleSave(activeSessionDetail.id, nextPayload)
    },
    [
      activeSessionDetail,
      clearPendingSave,
      computeDirty,
      editorText,
      scheduleSave,
      selectedTemplateName,
      selectedThemeName,
      settings
    ]
  )

  const createTemplateMutation = useMutation({
    mutationFn: (input: Parameters<typeof createWritingTemplate>[0]) =>
      createWritingTemplate(input),
    onSuccess: (template) => {
      message.success(
        t("option:writingPlayground.templateCreateSuccess", "Template created.")
      )
      queryClient.setQueryData<WritingTemplateListResponse | undefined>(
        ["writing-templates"],
        (prev) => {
          if (!prev) {
            return { templates: [template], total: 1 }
          }
          const exists = prev.templates.some(
            (item) => item.name === template.name
          )
          if (exists) {
            return {
              ...prev,
              templates: prev.templates.map((item) =>
                item.name === template.name ? template : item
              )
            }
          }
          const total = Number.isFinite(prev.total)
            ? prev.total + 1
            : prev.templates.length + 1
          return {
            ...prev,
            templates: [template, ...prev.templates],
            total
          }
        }
      )
      queryClient.invalidateQueries({ queryKey: ["writing-templates"] })
      setEditingTemplate(template)
      setTemplateForm(buildTemplateForm(template))
      if (!selectedTemplateName) {
        handleTemplateChange(template.name)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.templateCreateError",
          "Failed to create template: {{detail}}",
          { detail }
        )
      )
    }
  })

  const updateTemplateMutation = useMutation({
    mutationFn: (payload: {
      template: WritingTemplateResponse
      input: Parameters<typeof updateWritingTemplate>[1]
    }) =>
      updateWritingTemplate(
        payload.template.name,
        payload.input,
        payload.template.version
      ),
    onSuccess: (template, payload) => {
      message.success(
        t(
          "option:writingPlayground.templateSaveSuccess",
          "Template saved."
        )
      )
      queryClient.invalidateQueries({ queryKey: ["writing-templates"] })
      setEditingTemplate(template)
      setTemplateForm(buildTemplateForm(template))
      if (selectedTemplateName === payload.template.name) {
        handleTemplateChange(template.name)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.templateSaveError",
          "Failed to save template: {{detail}}",
          { detail }
        )
      )
    }
  })

  const deleteTemplateMutation = useMutation({
    mutationFn: (payload: { template: WritingTemplateResponse }) =>
      deleteWritingTemplate(payload.template.name, payload.template.version),
    onSuccess: (_data, payload) => {
      message.success(
        t(
          "option:writingPlayground.templateDeleteSuccess",
          "Template deleted."
        )
      )
      queryClient.invalidateQueries({ queryKey: ["writing-templates"] })
      if (editingTemplate?.name === payload.template.name) {
        setEditingTemplate(null)
        setTemplateForm({ ...EMPTY_TEMPLATE_FORM })
      }
      if (selectedTemplateName === payload.template.name) {
        handleTemplateChange(null)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.templateDeleteError",
          "Failed to delete template: {{detail}}",
          { detail }
        )
      )
    }
  })

  const createThemeMutation = useMutation({
    mutationFn: (input: Parameters<typeof createWritingTheme>[0]) =>
      createWritingTheme(input),
    onSuccess: (theme) => {
      message.success(
        t("option:writingPlayground.themeCreateSuccess", "Theme created.")
      )
      queryClient.setQueryData<WritingThemeListResponse | undefined>(
        ["writing-themes"],
        (prev) => {
          if (!prev) {
            return { themes: [theme], total: 1 }
          }
          const exists = prev.themes.some((item) => item.name === theme.name)
          if (exists) {
            return {
              ...prev,
              themes: prev.themes.map((item) =>
                item.name === theme.name ? theme : item
              )
            }
          }
          const total = Number.isFinite(prev.total)
            ? prev.total + 1
            : prev.themes.length + 1
          return {
            ...prev,
            themes: [theme, ...prev.themes],
            total
          }
        }
      )
      queryClient.invalidateQueries({ queryKey: ["writing-themes"] })
      setEditingTheme(theme)
      setThemeForm(buildThemeForm(theme))
      if (!selectedThemeName) {
        handleThemeChange(theme.name)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.themeCreateError",
          "Failed to create theme: {{detail}}",
          { detail }
        )
      )
    }
  })

  const updateThemeMutation = useMutation({
    mutationFn: (payload: {
      theme: WritingThemeResponse
      input: Parameters<typeof updateWritingTheme>[1]
    }) =>
      updateWritingTheme(
        payload.theme.name,
        payload.input,
        payload.theme.version
      ),
    onSuccess: (theme, payload) => {
      message.success(
        t("option:writingPlayground.themeSaveSuccess", "Theme saved.")
      )
      queryClient.invalidateQueries({ queryKey: ["writing-themes"] })
      setEditingTheme(theme)
      setThemeForm(buildThemeForm(theme))
      if (selectedThemeName === payload.theme.name) {
        handleThemeChange(theme.name)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.themeSaveError",
          "Failed to save theme: {{detail}}",
          { detail }
        )
      )
    }
  })

  const deleteThemeMutation = useMutation({
    mutationFn: (payload: { theme: WritingThemeResponse }) =>
      deleteWritingTheme(payload.theme.name, payload.theme.version),
    onSuccess: (_data, payload) => {
      message.success(
        t("option:writingPlayground.themeDeleteSuccess", "Theme deleted.")
      )
      queryClient.invalidateQueries({ queryKey: ["writing-themes"] })
      if (editingTheme?.name === payload.theme.name) {
        setEditingTheme(null)
        setThemeForm({ ...EMPTY_THEME_FORM })
      }
      if (selectedThemeName === payload.theme.name) {
        handleThemeChange(null)
      }
    },
    onError: (err) => {
      const detail =
        err instanceof Error ? err.message : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.themeDeleteError",
          "Failed to delete theme: {{detail}}",
          { detail }
        )
      )
    }
  })

  const updateTemplateForm = React.useCallback(
    (patch: Partial<TemplateFormState>) => {
      setTemplateForm((prev) => ({ ...prev, ...patch }))
    },
    []
  )

  const updateThemeForm = React.useCallback(
    (patch: Partial<ThemeFormState>) => {
      setThemeForm((prev) => ({ ...prev, ...patch }))
    },
    []
  )

  const handleTemplateSelect = React.useCallback(
    (template: WritingTemplateResponse) => {
      setEditingTemplate(template)
      setTemplateForm(buildTemplateForm(template))
    },
    []
  )

  const handleTemplateNew = React.useCallback(() => {
    setEditingTemplate(null)
    setTemplateForm({ ...EMPTY_TEMPLATE_FORM })
  }, [])

  const handleOpenTemplatesModal = React.useCallback(() => {
    const baseTemplate =
      selectedTemplate ?? defaultTemplate ?? templates[0] ?? null
    if (baseTemplate) {
      setEditingTemplate(baseTemplate)
      setTemplateForm(buildTemplateForm(baseTemplate))
    } else {
      setEditingTemplate(null)
      setTemplateForm({ ...EMPTY_TEMPLATE_FORM })
    }
    setTemplatesModalOpen(true)
  }, [defaultTemplate, selectedTemplate, templates])

  const handleThemeSelect = React.useCallback((theme: WritingThemeResponse) => {
    setEditingTheme(theme)
    setThemeForm(buildThemeForm(theme))
  }, [])

  const handleThemeNew = React.useCallback(() => {
    setEditingTheme(null)
    setThemeForm({ ...EMPTY_THEME_FORM })
  }, [])

  const handleOpenThemesModal = React.useCallback(() => {
    const baseTheme = selectedTheme ?? defaultTheme ?? themes[0] ?? null
    if (baseTheme) {
      setEditingTheme(baseTheme)
      setThemeForm(buildThemeForm(baseTheme))
    } else {
      setEditingTheme(null)
      setThemeForm({ ...EMPTY_THEME_FORM })
    }
    setThemesModalOpen(true)
  }, [defaultTheme, selectedTheme, themes])

  const handleTemplateSave = React.useCallback(() => {
    const name = templateForm.name.trim()
    if (!name) {
      message.info(
        t(
          "option:writingPlayground.templateNameRequired",
          "Enter a template name."
        )
      )
      return
    }
    const payload = buildTemplatePayload(templateForm)
    if (editingTemplate) {
      updateTemplateMutation.mutate({
        template: editingTemplate,
        input: {
          name,
          payload,
          schema_version: editingTemplate.schema_version,
          is_default: templateForm.isDefault
        }
      })
      return
    }
    createTemplateMutation.mutate({
      name,
      payload,
      schema_version: 1,
      is_default: templateForm.isDefault
    })
  }, [
    createTemplateMutation,
    editingTemplate,
    templateForm,
    updateTemplateMutation,
    t
  ])

  const handleThemeSave = React.useCallback(() => {
    const name = themeForm.name.trim()
    if (!name) {
      message.info(
        t("option:writingPlayground.themeNameRequired", "Enter a theme name.")
      )
      return
    }
    const payload = buildThemePayload(themeForm)
    if (editingTheme) {
      updateThemeMutation.mutate({
        theme: editingTheme,
        input: {
          name,
          ...payload,
          schema_version: editingTheme.schema_version,
          is_default: themeForm.isDefault
        }
      })
      return
    }
    createThemeMutation.mutate({
      name,
      ...payload,
      schema_version: 1,
      is_default: themeForm.isDefault
    })
  }, [
    createThemeMutation,
    editingTheme,
    themeForm,
    updateThemeMutation,
    t
  ])

  const confirmDeleteTemplate = React.useCallback(
    (template: WritingTemplateResponse) => {
      Modal.confirm({
        title: t(
          "option:writingPlayground.templateDeleteTitle",
          "Delete template?"
        ),
        content: t(
          "option:writingPlayground.templateDeleteBody",
          "This will permanently delete the template."
        ),
        okText: t("common:delete", "Delete"),
        okButtonProps: { danger: true },
        cancelText: t("common:cancel", "Cancel"),
        onOk: () => deleteTemplateMutation.mutateAsync({ template })
      })
    },
    [deleteTemplateMutation, t]
  )

  const confirmDeleteTheme = React.useCallback(
    (theme: WritingThemeResponse) => {
      Modal.confirm({
        title: t("option:writingPlayground.themeDeleteTitle", "Delete theme?"),
        content: t(
          "option:writingPlayground.themeDeleteBody",
          "This will permanently delete the theme."
        ),
        okText: t("common:delete", "Delete"),
        okButtonProps: { danger: true },
        cancelText: t("common:cancel", "Cancel"),
        onOk: () => deleteThemeMutation.mutateAsync({ theme })
      })
    },
    [deleteThemeMutation, t]
  )

  const exportTemplate = React.useCallback(
    (template: WritingTemplateResponse) => {
      const payload = {
        name: template.name,
        payload: template.payload,
        schema_version: template.schema_version,
        is_default: template.is_default
      }
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json"
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `${template.name || "template"}.json`
      link.click()
      URL.revokeObjectURL(url)
    },
    []
  )

  const handleTemplateImport = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      setTemplateImporting(true)
      try {
        const text = await file.text()
        const parsed = JSON.parse(text)
        const items: Array<{
          name?: unknown
          payload?: unknown
          schema_version?: unknown
          schemaVersion?: unknown
          is_default?: unknown
          isDefault?: unknown
        }> = Array.isArray(parsed)
          ? parsed
          : Array.isArray(parsed?.templates)
            ? parsed.templates
            : parsed && typeof parsed === "object"
              ? [parsed]
              : []
        if (!items.length) {
          throw new Error(
            t(
              "option:writingPlayground.templateImportInvalid",
              "No templates found in file."
            )
          )
        }
        for (const item of items) {
          const name =
            typeof item?.name === "string" ? item.name.trim() : ""
          if (!name) continue
          const payload = isRecord(item?.payload) ? item.payload : {}
          const schemaVersion =
            typeof item?.schema_version === "number"
              ? item.schema_version
              : typeof item?.schemaVersion === "number"
                ? item.schemaVersion
                : 1
          const isDefault =
            typeof item?.is_default === "boolean"
              ? item.is_default
              : typeof item?.isDefault === "boolean"
                ? item.isDefault
                : false
          const existing = templates.find((tmpl) => tmpl.name === name)
          if (existing) {
            await updateWritingTemplate(
              existing.name,
              {
                name,
                payload,
                schema_version: schemaVersion,
                is_default: isDefault
              },
              existing.version
            )
          } else {
            await createWritingTemplate({
              name,
              payload,
              schema_version: schemaVersion,
              is_default: isDefault
            })
          }
        }
        queryClient.invalidateQueries({ queryKey: ["writing-templates"] })
        message.success(
          t(
            "option:writingPlayground.templateImportSuccess",
            "Templates imported."
          )
        )
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : t("option:error", "Error")
        message.error(
          t(
            "option:writingPlayground.templateImportError",
            "Import failed: {{detail}}",
            { detail }
          )
        )
      } finally {
        setTemplateImporting(false)
        event.target.value = ""
      }
    },
    [queryClient, t, templates]
  )

  const exportTheme = React.useCallback((theme: WritingThemeResponse) => {
    const payload = {
      name: theme.name,
      class_name: theme.class_name,
      css: theme.css,
      schema_version: theme.schema_version,
      is_default: theme.is_default,
      order: theme.order
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json"
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `${theme.name || "theme"}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }, [])

  const handleThemeImport = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      setThemeImporting(true)
      try {
        const raw = await file.text()
        const parsed = JSON.parse(raw)
        const items = Array.isArray(parsed)
          ? parsed
          : Array.isArray(parsed?.themes)
            ? parsed.themes
            : parsed
              ? [parsed]
              : []
        if (!Array.isArray(items) || items.length === 0) {
          message.error(
            t(
              "option:writingPlayground.themeImportInvalid",
              "No themes found in file."
            )
          )
          return
        }
        for (const item of items) {
          if (!item || typeof item !== "object") continue
          const name = String((item as { name?: string }).name || "").trim()
          if (!name) continue
          const existing = themes.find((theme) => theme.name === name)
          const rawClassName = (item as { class_name?: string; className?: string })
            .class_name ?? (item as { className?: string }).className
          const rawIsDefault = (item as { is_default?: boolean; isDefault?: boolean })
            .is_default ?? (item as { isDefault?: boolean }).isDefault
          const payload = {
            class_name:
              typeof rawClassName === "string"
                ? rawClassName
                : null,
            css:
              typeof (item as { css?: string }).css === "string"
                ? (item as { css?: string }).css
                : null,
            schema_version:
              typeof (item as { schema_version?: number }).schema_version ===
              "number"
                ? (item as { schema_version?: number }).schema_version
                : 1,
            is_default:
              typeof rawIsDefault === "boolean"
                ? rawIsDefault
                : false,
            order:
              typeof (item as { order?: number }).order === "number"
                ? (item as { order?: number }).order
                : 0
          }
          if (existing) {
            await updateWritingTheme(existing.name, payload, existing.version)
          } else {
            await createWritingTheme({ name, ...payload })
          }
        }
        queryClient.invalidateQueries({ queryKey: ["writing-themes"] })
        message.success(
          t(
            "option:writingPlayground.themeImportSuccess",
            "Themes imported."
          )
        )
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : t("option:error", "Error")
        message.error(
          t(
            "option:writingPlayground.themeImportError",
            "Import failed: {{detail}}",
            { detail }
          )
        )
      } finally {
        setThemeImporting(false)
        event.target.value = ""
      }
    },
    [queryClient, t, themes]
  )

  const insertPlaceholder = React.useCallback(
    (placeholder: "{predict}" | "{fill}") => {
      const editorEl = editorRef.current?.resizableTextArea?.textArea
      const currentValue = editorText
      if (!editorEl) {
        applyPromptValue(currentValue + placeholder, {
          start: currentValue.length + placeholder.length,
          end: currentValue.length + placeholder.length
        })
        return
      }
      const start = editorEl.selectionStart ?? currentValue.length
      const end = editorEl.selectionEnd ?? currentValue.length
      const nextValue =
        currentValue.slice(0, start) + placeholder + currentValue.slice(end)
      const cursor = start + placeholder.length
      applyPromptValue(nextValue, { start: cursor, end: cursor })
    },
    [applyPromptValue, editorText]
  )

  const insertTemplateBlock = React.useCallback(
    (kind: "system" | "user" | "assistant") => {
      const blocks = {
        system: {
          prefix: effectiveTemplate.systemPrefix,
          suffix: effectiveTemplate.systemSuffix,
          label: t("option:writingPlayground.templateInsertSystem", "System")
        },
        user: {
          prefix: effectiveTemplate.userPrefix,
          suffix: effectiveTemplate.userSuffix,
          label: t("option:writingPlayground.templateInsertUser", "User")
        },
        assistant: {
          prefix: effectiveTemplate.assistantPrefix,
          suffix: effectiveTemplate.assistantSuffix,
          label: t(
            "option:writingPlayground.templateInsertAssistant",
            "Assistant"
          )
        }
      }
      const block = blocks[kind]
      if (!block.prefix && !block.suffix) {
        message.info(
          t(
            "option:writingPlayground.templateInsertMissing",
            "{{label}} markers missing in template.",
            { label: block.label }
          )
        )
        return
      }
      const editorEl = editorRef.current?.resizableTextArea?.textArea
      const currentValue = editorText
      const start = editorEl?.selectionStart ?? currentValue.length
      const end = editorEl?.selectionEnd ?? currentValue.length
      const selected = currentValue.slice(start, end)
      const nextValue =
        currentValue.slice(0, start) +
        block.prefix +
        selected +
        block.suffix +
        currentValue.slice(end)
      const cursor = start + block.prefix.length + selected.length
      applyPromptValue(nextValue, { start: cursor, end: cursor })
    },
    [applyPromptValue, editorText, effectiveTemplate, t]
  )

  const insertMenuItems: NonNullable<MenuProps["items"]> = React.useMemo(
    () => [
      {
        key: "predict",
        label: t(
          "option:writingPlayground.insertPredict",
          "Insert {predict}"
        ),
        onClick: () => insertPlaceholder("{predict}")
      },
      {
        key: "fill",
        label: t("option:writingPlayground.insertFill", "Insert {fill}"),
        onClick: () => insertPlaceholder("{fill}")
      },
      { type: "divider" },
      {
        key: "template-system",
        label: t(
          "option:writingPlayground.templateInsertSystem",
          "System"
        ),
        disabled:
          !effectiveTemplate.systemPrefix && !effectiveTemplate.systemSuffix,
        onClick: () => insertTemplateBlock("system")
      },
      {
        key: "template-user",
        label: t("option:writingPlayground.templateInsertUser", "User"),
        disabled: !effectiveTemplate.userPrefix && !effectiveTemplate.userSuffix,
        onClick: () => insertTemplateBlock("user")
      },
      {
        key: "template-assistant",
        label: t(
          "option:writingPlayground.templateInsertAssistant",
          "Assistant"
        ),
        disabled:
          !effectiveTemplate.assistantPrefix &&
          !effectiveTemplate.assistantSuffix,
        onClick: () => insertTemplateBlock("assistant")
      }
    ],
    [effectiveTemplate, insertPlaceholder, insertTemplateBlock, t]
  )

  const editorMenuItems: MenuProps["items"] = React.useMemo(
    () => [
      ...insertMenuItems,
      { type: "divider" },
      {
        key: "search",
        label: t(
          "option:writingPlayground.searchReplace",
          "Search & replace"
        ),
        onClick: () => setSearchOpen(true)
      }
    ],
    [insertMenuItems, t]
  )

  const searchData = React.useMemo(() => {
    if (!searchQuery.trim()) {
      return { matches: [], error: null }
    }

    if (useRegex) {
      const regex = buildRegex(searchQuery, {
        global: true,
        matchCase
      })
      if (!regex) {
        return {
          matches: [],
          error: t("option:writingPlayground.searchRegexError", "Invalid regex")
        }
      }
      const matches: Array<{ start: number; end: number }> = []
      let match: RegExpExecArray | null
      while ((match = regex.exec(editorText)) !== null) {
        matches.push({ start: match.index, end: match.index + match[0].length })
        if (match[0].length === 0) {
          regex.lastIndex += 1
        }
        if (matches.length >= MAX_MATCHES) break
      }
      return { matches, error: null }
    }

    const source = matchCase ? editorText : editorText.toLowerCase()
    const query = matchCase ? searchQuery : searchQuery.toLowerCase()
    const matches: Array<{ start: number; end: number }> = []
    let idx = 0
    while (query && (idx = source.indexOf(query, idx)) !== -1) {
      matches.push({ start: idx, end: idx + query.length })
      idx += query.length || 1
      if (matches.length >= MAX_MATCHES) break
    }
    return { matches, error: null }
  }, [editorText, matchCase, searchQuery, t, useRegex])

  const searchMatches = searchData.matches
  const searchError = searchData.error

  React.useEffect(() => {
    setActiveMatchIndex(0)
  }, [searchQuery, useRegex, matchCase])

  React.useEffect(() => {
    if (activeMatchIndex >= searchMatches.length) {
      setActiveMatchIndex(0)
    }
  }, [activeMatchIndex, searchMatches.length])

  const navigateMatch = React.useCallback(
    (direction: "next" | "prev") => {
      if (!searchMatches.length) return
      const nextIndex =
        direction === "next"
          ? (activeMatchIndex + 1) % searchMatches.length
          : (activeMatchIndex - 1 + searchMatches.length) %
            searchMatches.length
      setActiveMatchIndex(nextIndex)
      const match = searchMatches[nextIndex]
      focusEditorSelection(match.start, match.end)
    },
    [activeMatchIndex, focusEditorSelection, searchMatches]
  )

  const replaceCurrent = React.useCallback(() => {
    if (!searchMatches.length) return
    const match = searchMatches[activeMatchIndex] ?? searchMatches[0]
    if (!match) return
    const matchText = editorText.slice(match.start, match.end)
    let replacement = replaceQuery
    if (useRegex) {
      const regex = buildRegex(searchQuery, {
        global: false,
        matchCase
      })
      if (!regex) return
      replacement = matchText.replace(regex, replaceQuery)
    }
    const nextValue =
      editorText.slice(0, match.start) +
      replacement +
      editorText.slice(match.end)
    const cursor = match.start + replacement.length
    applyPromptValue(nextValue, { start: cursor, end: cursor })
  }, [
    activeMatchIndex,
    applyPromptValue,
    editorText,
    matchCase,
    replaceQuery,
    searchMatches,
    searchQuery,
    useRegex
  ])

  const replaceAll = React.useCallback(() => {
    if (!searchQuery.trim()) return
    if (useRegex) {
      const regex = buildRegex(searchQuery, {
        global: true,
        matchCase
      })
      if (!regex) return
      const nextValue = editorText.replace(regex, replaceQuery)
      applyPromptValue(nextValue)
      return
    }
    const source = matchCase ? editorText : editorText.toLowerCase()
    const query = matchCase ? searchQuery : searchQuery.toLowerCase()
    if (!query) return
    let idx = 0
    let result = ""
    while (idx < editorText.length) {
      const found = source.indexOf(query, idx)
      if (found === -1) {
        result += editorText.slice(idx)
        break
      }
      result += editorText.slice(idx, found) + replaceQuery
      idx = found + query.length
    }
    applyPromptValue(result)
  }, [
    applyPromptValue,
    editorText,
    matchCase,
    replaceQuery,
    searchQuery,
    useRegex
  ])

  const syncGenerationHistory = React.useCallback(() => {
    setCanUndoGeneration(generationUndoRef.current.length > 0)
    setCanRedoGeneration(generationRedoRef.current.length > 0)
  }, [])

  const pushGenerationHistory = React.useCallback(
    (before: string, after: string) => {
      if (before === after) return
      generationUndoRef.current.push({ before, after })
      generationRedoRef.current = []
      syncGenerationHistory()
    },
    [syncGenerationHistory]
  )

  const applyHistoryText = React.useCallback(
    (nextText: string) => {
      if (activeSessionDetail) {
        applyPromptValue(nextText)
      } else {
        setEditorText(nextText)
      }
    },
    [activeSessionDetail, applyPromptValue]
  )

  const handleUndoGeneration = React.useCallback(() => {
    if (isGenerating) return
    const entry = generationUndoRef.current.pop()
    if (!entry) return
    generationRedoRef.current.push(entry)
    syncGenerationHistory()
    applyHistoryText(entry.before)
  }, [applyHistoryText, isGenerating, syncGenerationHistory])

  const handleRedoGeneration = React.useCallback(() => {
    if (isGenerating) return
    const entry = generationRedoRef.current.pop()
    if (!entry) return
    generationUndoRef.current.push(entry)
    syncGenerationHistory()
    applyHistoryText(entry.after)
  }, [applyHistoryText, isGenerating, syncGenerationHistory])

  const handleCancelGeneration = React.useCallback(() => {
    if (!isGenerating) return
    generationCancelledRef.current = true
    generationServiceRef.current.cancelStream()
  }, [isGenerating])

  const handleGenerate = React.useCallback(async () => {
    if (isGenerating) return
    if (!activeSessionDetail) {
      message.info(
        t(
          "option:writingPlayground.selectSession",
          "Select a session to begin."
        )
      )
      return
    }
    if (!isOnline || !hasChat) {
      message.error(
        t(
          "option:writingPlayground.generateUnavailable",
          "Chat completions unavailable."
        )
      )
      return
    }
    if (!selectedModel) {
      message.info(
        t(
          "option:writingPlayground.modelMissing",
          "Select a model in Settings to generate."
        )
      )
      return
    }

    const beforeText = editorText
    const plan = resolveGenerationPlan(beforeText)
    const fimPrompt =
      plan.mode === "fill"
        ? applyFimTemplate(effectiveTemplate, plan.prefix, plan.suffix)
        : null
    if (plan.mode === "fill" && !fimPrompt) {
      message.info(
        t(
          "option:writingPlayground.fillFallbackNotice",
          "Fill template missing; using a basic fill prompt."
        )
      )
    }
    const promptText =
      plan.mode === "fill"
        ? fimPrompt ?? buildFillPrompt(plan.prefix, plan.suffix)
        : plan.prefix
    const baseMessages = buildChatMessages(
      promptText,
      effectiveTemplate,
      chatMode
    )
    const contextMessages = buildContextSystemMessages(beforeText, {
      memory_block: settings.memory_block,
      author_note: settings.author_note,
      world_info: settings.world_info
    })
    const messages = injectSystemMessages(baseMessages, contextMessages)
    const advancedExtraBody =
      supportsAdvancedCompat ? settings.advanced_extra_body : {}
    const extraBody = buildExtraBodyPayload({
      top_k: settings.top_k,
      seed: settings.seed,
      stop: settings.stop,
      advanced_extra_body: advancedExtraBody
    })

    generationSessionIdRef.current = activeSessionDetail.id
    generationCancelledRef.current = false
    setIsGenerating(true)
    setIsDirty(true)
    if (plan.placeholder) {
      setEditorText(plan.prefix + plan.suffix)
    }

    let generated = ""
    let streamError: unknown = null

    try {
      for await (const token of generationServiceRef.current.streamMessage(
        messages,
        {
          model: selectedModel,
          temperature: settings.temperature,
          maxTokens: settings.max_tokens,
          topP: settings.top_p,
          frequencyPenalty: settings.frequency_penalty,
          presencePenalty: settings.presence_penalty,
          systemPrompt: chatMode
            ? undefined
            : plan.mode === "fill"
              ? FILL_SYSTEM_PROMPT
              : PREDICT_SYSTEM_PROMPT,
          extraBody
        }
      )) {
        if (generationCancelledRef.current) break
        generated += token
        setEditorText(plan.prefix + generated + plan.suffix)
      }
    } catch (error) {
      streamError = error
    }

    const aborted = generationCancelledRef.current || isAbortError(streamError)
    const finalText =
      generated.length > 0 ? plan.prefix + generated + plan.suffix : beforeText
    if (activeSessionDetail.id === generationSessionIdRef.current) {
      applyHistoryText(finalText)
      pushGenerationHistory(beforeText, finalText)
    }

    generationSessionIdRef.current = null
    generationCancelledRef.current = false
    setIsGenerating(false)

    if (streamError && !aborted) {
      const detail =
        streamError instanceof Error
          ? streamError.message
          : t("option:error", "Error")
      message.error(
        t(
          "option:writingPlayground.generateError",
          "Generation failed: {{detail}}",
          { detail }
        )
      )
    }
  }, [
    activeSessionDetail,
    applyHistoryText,
    chatMode,
    editorText,
    effectiveTemplate,
    hasChat,
    isGenerating,
    isOnline,
    pushGenerationHistory,
    selectedModel,
    settings,
    supportsAdvancedCompat,
    t
  ])

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isGenerating) {
        handleCancelGeneration()
        return
      }
      if (event.key !== "Enter") return
      if (!event.ctrlKey && !event.metaKey) return
      const editorEl = editorRef.current?.resizableTextArea?.textArea
      if (!editorEl || document.activeElement !== editorEl) return
      event.preventDefault()
      void handleGenerate()
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [handleCancelGeneration, handleGenerate, isGenerating])

  const promptChunkData = React.useMemo(() => {
    if (!editorText) {
      return { chunks: [], total: 0, truncated: false }
    }
    const parts = editorText
      .split(
        new RegExp(
          `(${escapeRegex(PREDICT_PLACEHOLDER)}|${escapeRegex(FILL_PLACEHOLDER)})`,
          "g"
        )
      )
      .filter(Boolean)
    const chunks = parts.map((part, index) => ({
      key: `${index}-${part}`,
      type:
        part === PREDICT_PLACEHOLDER || part === FILL_PLACEHOLDER
          ? "placeholder"
          : "text",
      label: part
    }))
    return {
      chunks: chunks.slice(0, MAX_CHUNKS),
      total: chunks.length,
      truncated: chunks.length > MAX_CHUNKS
    }
  }, [editorText])

  const clearTokenInspector = React.useCallback(() => {
    setTokenCountResult(null)
    setTokenizeResult(null)
    setTokenInspectorError(null)
  }, [])

  const resolveTokenInspectorTarget = React.useCallback(async () => {
    const model = String(selectedModel || "").trim()
    if (!model) {
      throw new Error(
        t(
          "option:writingPlayground.modelMissing",
          "Select a model in Settings to generate."
        )
      )
    }
    const requestedProvider = String(
      requestedCaps?.requested?.provider || ""
    ).trim()
    if (requestedProvider) {
      return { provider: requestedProvider, model }
    }
    const provider = await resolveApiProviderForModel({
      modelId: model,
      explicitProvider: apiProviderOverride
    })
    if (!provider) {
      throw new Error(
        t(
          "option:writingPlayground.tokenInspectorProviderMissing",
          "Unable to resolve a provider for the selected model."
        )
      )
    }
    return { provider, model }
  }, [apiProviderOverride, requestedCaps?.requested?.provider, selectedModel, t])

  const handleCountTokens = React.useCallback(async () => {
    if (!editorText.trim()) {
      message.info(
        t(
          "option:writingPlayground.tokenInspectorEmptyPrompt",
          "Enter text in the editor before counting tokens."
        )
      )
      return
    }
    setIsCountingTokens(true)
    setTokenInspectorError(null)
    try {
      const target = await resolveTokenInspectorTarget()
      const result = await countWritingTokens({
        provider: target.provider,
        model: target.model,
        text: editorText
      })
      setTokenCountResult(result)
    } catch (error) {
      const detail = error instanceof Error ? error.message : t("option:error", "Error")
      setTokenInspectorError(detail)
    } finally {
      setIsCountingTokens(false)
    }
  }, [editorText, resolveTokenInspectorTarget, t])

  const handleTokenizePreview = React.useCallback(async () => {
    if (!editorText.trim()) {
      message.info(
        t(
          "option:writingPlayground.tokenInspectorEmptyPrompt",
          "Enter text in the editor before counting tokens."
        )
      )
      return
    }
    setIsTokenizingText(true)
    setTokenInspectorError(null)
    try {
      const target = await resolveTokenInspectorTarget()
      const result = await tokenizeWritingText({
        provider: target.provider,
        model: target.model,
        text: editorText,
        options: { include_strings: true }
      })
      setTokenizeResult(result)
      setTokenCountResult({
        count: result.meta.token_count,
        meta: result.meta
      })
    } catch (error) {
      const detail = error instanceof Error ? error.message : t("option:error", "Error")
      setTokenInspectorError(detail)
    } finally {
      setIsTokenizingText(false)
    }
  }, [editorText, resolveTokenInspectorTarget, t])

  const applyWordcloudResponse = React.useCallback(
    (response: WritingWordcloudResponse, sequence: number) => {
      if (wordcloudUnmountedRef.current) return
      if (sequence !== wordcloudRequestSeqRef.current) return
      setWordcloudId(response.id || null)
      setWordcloudStatus(response.status || null)
      setWordcloudError(response.error?.trim() || null)
      setWordcloudWords(
        normalizeWordcloudWords(response.result?.words, wordcloudMaxWords)
      )
      setWordcloudMeta(response.result?.meta ?? null)
    },
    [wordcloudMaxWords]
  )

  const clearWordcloud = React.useCallback(() => {
    wordcloudRequestSeqRef.current += 1
    setWordcloudId(null)
    setWordcloudStatus(null)
    setWordcloudWords([])
    setWordcloudMeta(null)
    setWordcloudError(null)
    setIsGeneratingWordcloud(false)
  }, [])

  const handleGenerateWordcloud = React.useCallback(async () => {
    const text = editorText.trim()
    if (!text) {
      message.info(
        t(
          "option:writingPlayground.wordcloudEmptyPrompt",
          "Enter text in the editor before generating a wordcloud."
        )
      )
      return
    }
    const sequence = wordcloudRequestSeqRef.current + 1
    wordcloudRequestSeqRef.current = sequence
    setIsGeneratingWordcloud(true)
    setWordcloudId(null)
    setWordcloudStatus(null)
    setWordcloudWords([])
    setWordcloudMeta(null)
    setWordcloudError(null)
    try {
      const stopwords = parseWordcloudStopwordsInput(wordcloudStopwordsInput)
      const created = await createWritingWordcloud({
        text,
        options: {
          max_words: wordcloudMaxWords,
          min_word_length: wordcloudMinWordLength,
          keep_numbers: wordcloudKeepNumbers,
          stopwords: stopwords.length > 0 ? stopwords : undefined
        }
      })
      applyWordcloudResponse(created, sequence)
      let latest = created
      if (latest.id && (latest.status === "queued" || latest.status === "running")) {
        for (let attempt = 0; attempt < WORDCLOUD_POLL_ATTEMPTS; attempt += 1) {
          if (wordcloudUnmountedRef.current) return
          if (sequence !== wordcloudRequestSeqRef.current) return
          await wait(WORDCLOUD_POLL_DELAY_MS)
          latest = await getWritingWordcloud(latest.id)
          applyWordcloudResponse(latest, sequence)
          if (latest.status === "ready" || latest.status === "failed") {
            break
          }
        }
      }
      if (
        sequence === wordcloudRequestSeqRef.current &&
        latest.status !== "ready" &&
        latest.status !== "failed"
      ) {
        setWordcloudError(
          t(
            "option:writingPlayground.wordcloudTimeout",
            "Wordcloud generation is taking longer than expected. Try again in a moment."
          )
        )
      }
    } catch (error) {
      if (wordcloudUnmountedRef.current) return
      if (sequence !== wordcloudRequestSeqRef.current) return
      const detail = error instanceof Error ? error.message : t("option:error", "Error")
      setWordcloudError(detail)
    } finally {
      if (wordcloudUnmountedRef.current) return
      if (sequence !== wordcloudRequestSeqRef.current) return
      setIsGeneratingWordcloud(false)
    }
  }, [
    applyWordcloudResponse,
    editorText,
    wordcloudKeepNumbers,
    wordcloudMaxWords,
    wordcloudMinWordLength,
    wordcloudStopwordsInput,
    t
  ])

  const handlePromptChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      applyPromptValue(event.target.value)
    },
    [applyPromptValue]
  )

  const canGenerate =
    Boolean(activeSessionDetail) &&
    Boolean(selectedModel) &&
    hasChat &&
    !isGenerating
  const settingsDisabled = isGenerating
  const serverSupportsTokenize = writingCaps?.server?.tokenize === true
  const serverSupportsTokenCount = writingCaps?.server?.token_count === true
  const serverSupportsWordclouds = writingCaps?.server?.wordclouds === true
  const showTokenInspectorPanel =
    serverSupportsTokenCount || serverSupportsTokenize
  const showWordcloudPanel = serverSupportsWordclouds
  const requestedTokenizerAvailable =
    requestedCaps?.requested?.tokenizer_available === true
  const requestedTokenizerError =
    requestedCaps?.requested?.tokenization_error?.trim() || null
  const tokenizerName =
    tokenCountResult?.meta.tokenizer ||
    tokenizeResult?.meta.tokenizer ||
    requestedCaps?.requested?.tokenizer ||
    null
  const tokenPreviewRows = React.useMemo(
    () => buildTokenPreviewRows(tokenizeResult?.ids ?? [], tokenizeResult?.strings, 200),
    [tokenizeResult]
  )
  const tokenPreviewTotal = tokenizeResult?.ids.length ?? 0
  const tokenPreviewTruncated = tokenPreviewTotal > tokenPreviewRows.length
  const tokenInspectorUnavailableReason = React.useMemo(() => {
    if (!selectedModel) {
      return t(
        "option:writingPlayground.tokenInspectorModelMissing",
        "Select a model to use token inspection."
      )
    }
    if (requestedCapsLoading) {
      return t(
        "option:writingPlayground.tokenInspectorChecking",
        "Checking tokenizer support for this model..."
      )
    }
    if (requestedTokenizerError) {
      return requestedTokenizerError
    }
    if (!requestedTokenizerAvailable) {
      return t(
        "option:writingPlayground.tokenInspectorUnavailable",
        "Tokenizer unavailable for this provider/model."
      )
    }
    return null
  }, [
    requestedCapsLoading,
    requestedTokenizerAvailable,
    requestedTokenizerError,
    selectedModel,
    t
  ])
  const tokenInspectorBusy = isCountingTokens || isTokenizingText
  const canCountTokens =
    !settingsDisabled &&
    !tokenInspectorBusy &&
    serverSupportsTokenCount &&
    !tokenInspectorUnavailableReason
  const canTokenizePreview =
    !settingsDisabled &&
    !tokenInspectorBusy &&
    serverSupportsTokenize &&
    !tokenInspectorUnavailableReason
  const canGenerateWordcloud =
    !settingsDisabled &&
    !isGeneratingWordcloud &&
    serverSupportsWordclouds &&
    editorText.trim().length > 0
  const wordcloudTopWeight = wordcloudWords[0]?.weight ?? 0
  const wordcloudStatusColor =
    wordcloudStatus === "ready"
      ? "green"
      : wordcloudStatus === "failed"
        ? "red"
        : wordcloudStatus
          ? "blue"
          : "default"
  const advancedExtraBodyUnknownKeys = React.useMemo(
    () =>
      Object.keys(advancedExtraBody || {}).filter(
        (key) =>
          knownExtraBodyParamSet.size > 0 && !knownExtraBodyParamSet.has(key)
      ),
    [advancedExtraBody, knownExtraBodyParamSet]
  )
  const hasAdvancedSettingsValues =
    Object.keys(advancedExtraBody || {}).length > 0
  const showAdvancedSamplerControls =
    knownExtraBodyParams.length > 0 || hasAdvancedSettingsValues
  const templateSelectDisabled =
    settingsDisabled || !hasTemplates || templatesLoading || Boolean(templatesError)
  const templateSaveLoading =
    createTemplateMutation.isPending || updateTemplateMutation.isPending
  const templateSaveDisabled =
    templateSaveLoading || !templateForm.name.trim()
  const templateExportDisabled = !editingTemplate
  const templateDeleteDisabled =
    !editingTemplate || deleteTemplateMutation.isPending
  const templateFormDisabled =
    templateSaveLoading || deleteTemplateMutation.isPending
  const themeSelectDisabled =
    settingsDisabled || !hasThemes || themesLoading || Boolean(themesError)
  const themeSaveLoading =
    createThemeMutation.isPending || updateThemeMutation.isPending
  const themeSaveDisabled = themeSaveLoading || !themeForm.name.trim()
  const themeExportDisabled = !editingTheme
  const themeDeleteDisabled =
    !editingTheme || deleteThemeMutation.isPending
  const themeFormDisabled = themeSaveLoading || deleteThemeMutation.isPending
  const canCreateSession = newSessionName.trim().length > 0
  const sessionImportDisabled =
    !hasWriting || sessionsLoading || sessionImporting
  const canRenameSession =
    renameSessionName.trim().length > 0 &&
    renameTarget != null &&
    renameSessionName.trim() !== renameTarget.name
  const saveStatusLabel = React.useMemo(() => {
    if (!activeSessionId) return null
    if (isGenerating) {
      return t("option:writingPlayground.generatingLabel", "Generating...")
    }
    if (
      saveSessionMutation.isPending &&
      savingSessionIdRef.current === activeSessionId
    ) {
      return t("option:writingPlayground.savingLabel", "Saving...")
    }
    if (isDirty) {
      return t("option:writingPlayground.unsavedLabel", "Unsaved changes")
    }
    if (lastSavedAt) {
      return t("option:writingPlayground.savedLabel", "Saved {{time}}", {
        time: formatRelativeTime(new Date(lastSavedAt).toISOString(), t)
      })
    }
    return null
  }, [
    activeSessionId,
    isDirty,
    isGenerating,
    lastSavedAt,
    saveSessionMutation.isPending,
    t
  ])

  return (
    <div
      className={cn(
        "writing-playground flex flex-col gap-6",
        activeThemeClassName
      )}>
      {activeThemeCss ? <style>{activeThemeCss}</style> : null}
      <div>
        <Title level={2}>
          {t("option:writingPlayground.title", "Writing Playground")}
        </Title>
        <Paragraph type="secondary">
          {t(
            "option:writingPlayground.subtitle",
            "Draft long-form prompts, manage sessions, and generate with your tldw server."
          )}
        </Paragraph>
      </div>

      {showOffline && (
        <Alert
          type="warning"
          showIcon
          title={t("option:writingPlayground.offlineTitle", "Server required")}
          description={t(
            "option:writingPlayground.offlineBody",
            "Connect to your tldw server to load writing sessions and generate."
          )}
        />
      )}

      {showUnsupported && (
        <Alert
          type="info"
          showIcon
          title={t(
            "option:writingPlayground.unavailableTitle",
            "Playground unavailable"
          )}
          description={t(
            "option:writingPlayground.unavailableBody",
            "This server does not advertise writing playground support yet."
          )}
        />
      )}

      {!showOffline && !showUnsupported && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <Card
            title={t("option:writingPlayground.sessionsTitle", "Sessions")}
            extra={
              <div className="flex items-center gap-2">
                <Button type="primary" onClick={() => setCreateModalOpen(true)}>
                  {t("option:writingPlayground.newSession", "New session")}
                </Button>
                <Button
                  size="small"
                  onClick={() => sessionFileInputRef.current?.click()}
                  loading={sessionImporting}
                  disabled={sessionImportDisabled}>
                  {t("option:writingPlayground.importSession", "Import")}
                </Button>
              </div>
            }>
            {sessionsLoading ? (
              <Skeleton active />
            ) : sessionsError ? (
              <Alert
                type="error"
                showIcon
                title={t(
                  "option:writingPlayground.sessionsError",
                  "Unable to load sessions."
                )}
              />
            ) : sortedSessions.length === 0 ? (
              <Empty
                description={t(
                  "option:writingPlayground.sessionsEmpty",
                  "Create your first session to start writing."
                )}
              />
            ) : (
              <List
                dataSource={sortedSessions}
                rowKey={(item) => item.session.id}
                renderItem={({ session, lastUsedAt }) => {
                  const isActive = activeSessionId === session.id
                  const lastUsedLabel = lastUsedAt
                    ? t(
                        "option:writingPlayground.lastOpenedLabel",
                        "Last opened {{time}}",
                        {
                          time: formatRelativeTime(
                            new Date(lastUsedAt).toISOString(),
                            t
                          )
                        }
                      )
                    : t(
                        "option:writingPlayground.notOpened",
                        "Not opened yet"
                      )
                  const menuItems: MenuProps["items"] = [
                    {
                      key: "rename",
                      icon: <Pencil className="h-4 w-4" />,
                      label: t(
                        "option:writingPlayground.renameSession",
                        "Rename session"
                      ),
                      onClick: () => openRenameModal(session)
                    },
                    {
                      key: "clone",
                      icon: <Copy className="h-4 w-4" />,
                      label: t(
                        "option:writingPlayground.cloneSession",
                        "Clone session"
                      ),
                      onClick: () => cloneSessionMutation.mutate({ session })
                    },
                    {
                      key: "export",
                      icon: <Download className="h-4 w-4" />,
                      label: t(
                        "option:writingPlayground.exportSession",
                        "Export session"
                      ),
                      onClick: () => exportSession(session)
                    },
                    {
                      type: "divider"
                    },
                    {
                      key: "delete",
                      icon: <Trash2 className="h-4 w-4" />,
                      label: t(
                        "option:writingPlayground.deleteSession",
                        "Delete session"
                      ),
                      danger: true,
                      onClick: () => confirmDeleteSession(session)
                    }
                  ]
                  return (
                    <List.Item
                      className={`cursor-pointer rounded-md px-2 py-3 transition ${
                        isActive ? "bg-surface-hover" : "hover:bg-surface-hover/60"
                      }`}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelectSession(session)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault()
                          handleSelectSession(session)
                        }
                      }}>
                      <div className="flex w-full items-center justify-between gap-3">
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-text">
                            {session.name}
                          </span>
                          <span className="text-xs text-text-muted">
                            {lastUsedLabel}
                          </span>
                        </div>
                        <div
                          className="flex items-center gap-2"
                          onClick={(event) => event.stopPropagation()}>
                          {isActive ? (
                            <Tag color="blue">
                              {t("option:writingPlayground.active", "Active")}
                            </Tag>
                          ) : null}
                          <Dropdown menu={{ items: menuItems }} trigger={["click"]}>
                            <Button
                      type="text"
                      size="small"
                      icon={<MoreHorizontal className="h-4 w-4" />}
                      loading={
                        deleteSessionMutation.isPending ||
                        renameSessionMutation.isPending ||
                        cloneSessionMutation.isPending ||
                        sessionImporting
                      }
                    />
                  </Dropdown>
                </div>
              </div>
                    </List.Item>
                  )
                }}
              />
            )}
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <Card>
              {activeSession ? (
                activeSessionLoading ? (
                  <Skeleton active />
                ) : activeSessionError ? (
                  <Alert
                    type="error"
                    showIcon
                    title={t(
                      "option:writingPlayground.editorError",
                      "Unable to load this session."
                    )}
                  />
                ) : (
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <Title level={4} className="!mb-1">
                          {activeSession.name}
                        </Title>
                        <Paragraph type="secondary" className="!mb-0">
                          {t(
                            "option:writingPlayground.editorTitle",
                            "Prompt editor"
                          )}
                        </Paragraph>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {saveStatusLabel ? (
                          <span className="text-xs text-text-muted">
                            {saveStatusLabel}
                          </span>
                        ) : null}
                        <Tooltip
                          title={t(
                            "option:writingPlayground.generateShortcutTooltip",
                            "Ctrl/Cmd+Enter to generate"
                          )}>
                          <Button
                            type="primary"
                            size="small"
                            onClick={handleGenerate}
                            loading={isGenerating}
                            disabled={!canGenerate}>
                            {t(
                              "option:writingPlayground.generateAction",
                              "Generate"
                            )}
                          </Button>
                        </Tooltip>
                        {isGenerating ? (
                          <Tooltip
                            title={t(
                              "option:writingPlayground.stopShortcutTooltip",
                              "Esc to stop"
                            )}>
                            <Button
                              size="small"
                              onClick={handleCancelGeneration}
                              danger>
                              {t(
                                "option:writingPlayground.stopAction",
                                "Stop"
                              )}
                            </Button>
                          </Tooltip>
                        ) : null}
                        <Button
                          size="small"
                          icon={<Undo2 className="h-3.5 w-3.5" />}
                          disabled={isGenerating || !canUndoGeneration}
                          onClick={handleUndoGeneration}>
                          {t("option:writingPlayground.undoGeneration", "Undo")}
                        </Button>
                        <Button
                          size="small"
                          icon={<Redo2 className="h-3.5 w-3.5" />}
                          disabled={isGenerating || !canRedoGeneration}
                          onClick={handleRedoGeneration}>
                          {t("option:writingPlayground.redoGeneration", "Redo")}
                        </Button>
                        <Dropdown
                          menu={{ items: insertMenuItems }}
                          trigger={["click"]}
                          disabled={isGenerating}>
                          <Button size="small">
                            {t(
                              "option:writingPlayground.templateInsertAction",
                              "Insert"
                            )}
                          </Button>
                        </Dropdown>
                        <Segmented
                          size="small"
                          value={editorView}
                          onChange={(value) =>
                            setEditorView(value as EditorViewMode)
                          }
                          options={[
                            {
                              value: "edit",
                              icon: <Edit3 className="h-3.5 w-3.5" />,
                              label: t(
                                "option:writingPlayground.editorModeEdit",
                                "Edit"
                              )
                            },
                            {
                              value: "preview",
                              icon: <Eye className="h-3.5 w-3.5" />,
                              label: t(
                                "option:writingPlayground.editorModePreview",
                                "Preview"
                              )
                            },
                            {
                              value: "split",
                              icon: <Columns2 className="h-3.5 w-3.5" />,
                              label: t(
                                "option:writingPlayground.editorModeSplit",
                                "Split"
                              )
                            }
                          ]}
                        />
                        <Button
                          size="small"
                          icon={
                            searchOpen ? (
                              <X className="h-3.5 w-3.5" />
                            ) : (
                              <Search className="h-3.5 w-3.5" />
                            )
                          }
                          onClick={() => setSearchOpen((open) => !open)}>
                          {searchOpen
                            ? t("option:writingPlayground.searchClose", "Close")
                            : t("option:writingPlayground.searchToggle", "Find")}
                        </Button>
                      </div>
                    </div>
                    <div className="text-xs text-text-muted">
                      {t(
                        "option:writingPlayground.shortcutsHint",
                        "Shortcuts: Ctrl/Cmd+Enter to generate, Esc to stop."
                      )}
                    </div>
                    {searchOpen && (
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="flex flex-col gap-3">
                          <div className="flex flex-wrap gap-2">
                            <Input
                              value={searchQuery}
                              allowClear
                              placeholder={t(
                                "option:writingPlayground.searchPlaceholder",
                                "Find text"
                              )}
                              onChange={(event) =>
                                setSearchQuery(event.target.value)
                              }
                              className="min-w-[200px] flex-1"
                            />
                            <Input
                              value={replaceQuery}
                              allowClear
                              placeholder={t(
                                "option:writingPlayground.replacePlaceholder",
                                "Replace with"
                              )}
                              onChange={(event) =>
                                setReplaceQuery(event.target.value)
                              }
                              className="min-w-[200px] flex-1"
                            />
                            <div className="flex items-center gap-2">
                              <Button
                                size="small"
                                onClick={() => navigateMatch("prev")}
                                disabled={!searchMatches.length}>
                                {t(
                                  "option:writingPlayground.searchPrev",
                                  "Prev"
                                )}
                              </Button>
                              <Button
                                size="small"
                                onClick={() => navigateMatch("next")}
                                disabled={!searchMatches.length}>
                                {t(
                                  "option:writingPlayground.searchNext",
                                  "Next"
                                )}
                              </Button>
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-3">
                              <Checkbox
                                checked={matchCase}
                                onChange={(event) =>
                                  setMatchCase(event.target.checked)
                                }>
                                {t(
                                  "option:writingPlayground.searchMatchCase",
                                  "Match case"
                                )}
                              </Checkbox>
                              <Checkbox
                                checked={useRegex}
                                onChange={(event) =>
                                  setUseRegex(event.target.checked)
                                }>
                                {t(
                                  "option:writingPlayground.searchRegex",
                                  "Regex"
                                )}
                              </Checkbox>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                size="small"
                                onClick={replaceCurrent}
                                disabled={!searchMatches.length}>
                                {t(
                                  "option:writingPlayground.searchReplaceAction",
                                  "Replace"
                                )}
                              </Button>
                              <Button
                                size="small"
                                onClick={replaceAll}
                                disabled={!searchQuery.trim()}>
                                {t(
                                  "option:writingPlayground.searchReplaceAll",
                                  "Replace all"
                                )}
                              </Button>
                            </div>
                          </div>
                          <div className="text-xs text-text-muted">
                            {searchError
                              ? searchError
                              : searchQuery.trim()
                              ? searchMatches.length
                                ? t(
                                    "option:writingPlayground.searchMatchCount",
                                    "{{current}} of {{total}} matches",
                                    {
                                      current: Math.min(
                                        activeMatchIndex + 1,
                                        searchMatches.length
                                      ),
                                      total: searchMatches.length
                                    }
                                  )
                                : t(
                                    "option:writingPlayground.searchNoMatches",
                                    "No matches"
                                  )
                              : t(
                                  "option:writingPlayground.searchHint",
                                  "Enter text to search"
                                )}
                          </div>
                        </div>
                      </div>
                    )}
                  {editorView === "edit" && (
                    <Dropdown
                      menu={{ items: editorMenuItems }}
                      trigger={["contextMenu"]}>
                      <div>
                          <Input.TextArea
                            ref={editorRef}
                            value={editorText}
                            onChange={handlePromptChange}
                            onScroll={() => syncScroll("editor")}
                            placeholder={t(
                              "option:writingPlayground.editorPlaceholder",
                              "Start writing your prompt..."
                            )}
                            rows={18}
                            disabled={isGenerating}
                            className="min-h-[320px]"
                          />
                      </div>
                    </Dropdown>
                  )}
                    {editorView === "preview" && (
                      <div
                        ref={previewRef}
                        className="min-h-[320px] max-h-[600px] overflow-y-auto rounded-md border border-border bg-surface p-4"
                        onScroll={() => syncScroll("preview")}>
                        {editorText.trim() ? (
                          <MarkdownPreview content={editorText} size="sm" />
                        ) : (
                          <Paragraph type="secondary" className="!mb-0 italic">
                            {t(
                              "option:writingPlayground.editorEmptyPreview",
                              "Nothing to preview yet."
                            )}
                          </Paragraph>
                        )}
                      </div>
                    )}
                    {editorView === "split" && (
                      <div className="flex flex-col gap-4 lg:flex-row">
                        <div className="flex-1">
                          <Dropdown
                            menu={{ items: editorMenuItems }}
                            trigger={["contextMenu"]}>
                            <div>
                              <Input.TextArea
                                ref={editorRef}
                                value={editorText}
                                onChange={handlePromptChange}
                                onScroll={() => syncScroll("editor")}
                                placeholder={t(
                                  "option:writingPlayground.editorPlaceholder",
                                  "Start writing your prompt..."
                                )}
                                rows={18}
                                disabled={isGenerating}
                                className="min-h-[320px]"
                              />
                            </div>
                          </Dropdown>
                        </div>
                        <div
                          ref={previewRef}
                          className="flex-1 min-h-[320px] max-h-[600px] overflow-y-auto rounded-md border border-border bg-surface p-4"
                          onScroll={() => syncScroll("preview")}>
                          {editorText.trim() ? (
                            <MarkdownPreview content={editorText} size="sm" />
                          ) : (
                            <Paragraph type="secondary" className="!mb-0 italic">
                              {t(
                                "option:writingPlayground.editorEmptyPreview",
                                "Nothing to preview yet."
                              )}
                            </Paragraph>
                          )}
                        </div>
                      </div>
                    )}
                    <Collapse
                      ghost
                      size="small"
                      defaultActiveKey={["chunks"]}
                      items={[
                        {
                          key: "chunks",
                          label: t(
                            "option:writingPlayground.promptChunksTitle",
                            "Prompt chunks ({{count}})",
                            { count: promptChunkData.total }
                          ),
                          children:
                            promptChunkData.total === 0 ? (
                              <Paragraph type="secondary" className="!mb-0">
                                {t(
                                  "option:writingPlayground.promptChunksEmpty",
                                  "No chunks yet."
                                )}
                              </Paragraph>
                            ) : (
                              <div className="flex flex-col gap-2">
                                <div className="max-h-48 overflow-y-auto rounded-md border border-border bg-surface px-3 py-2">
                                  <div className="flex flex-col gap-2">
                                    {promptChunkData.chunks.map((chunk, index) => (
                                      <div
                                        key={chunk.key}
                                        className="flex items-start gap-2 text-xs">
                                        <Tag
                                          color={
                                            chunk.type === "placeholder"
                                              ? "blue"
                                              : "default"
                                          }>
                                          {chunk.type === "placeholder"
                                            ? t(
                                                "option:writingPlayground.chunkPlaceholder",
                                                "Placeholder"
                                              )
                                            : t(
                                                "option:writingPlayground.chunkText",
                                                "Text"
                                              )}
                                        </Tag>
                                        <span className="text-text-muted">
                                          {index + 1}.
                                        </span>
                                        <span className="whitespace-pre-wrap text-text">
                                          {chunk.label}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                                {promptChunkData.truncated ? (
                                  <span className="text-xs text-text-muted">
                                    {t(
                                      "option:writingPlayground.promptChunksTruncated",
                                      "Showing first {{count}} chunks.",
                                      { count: promptChunkData.chunks.length }
                                    )}
                                  </span>
                                ) : null}
                              </div>
                            )
                        }
                      ].concat(
                        showTokenInspectorPanel
                          ? [
                              {
                                key: "token-inspector",
                                label: t(
                                  "option:writingPlayground.tokenInspectorTitle",
                                  "Token inspector"
                                ),
                                children: (
                                  <div className="flex flex-col gap-3">
                                    <div className="flex flex-wrap items-center gap-2">
                                      {serverSupportsTokenCount ? (
                                        <Button
                                          size="small"
                                          disabled={!canCountTokens}
                                          loading={isCountingTokens}
                                          onClick={() => {
                                            void handleCountTokens()
                                          }}>
                                          {t(
                                            "option:writingPlayground.countTokensAction",
                                            "Count tokens"
                                          )}
                                        </Button>
                                      ) : null}
                                      {serverSupportsTokenize ? (
                                        <Button
                                          size="small"
                                          disabled={!canTokenizePreview}
                                          loading={isTokenizingText}
                                          onClick={() => {
                                            void handleTokenizePreview()
                                          }}>
                                          {t(
                                            "option:writingPlayground.tokenizePreviewAction",
                                            "Tokenize preview"
                                          )}
                                        </Button>
                                      ) : null}
                                      {tokenCountResult ||
                                      tokenizeResult ||
                                      tokenInspectorError ? (
                                        <Button
                                          size="small"
                                          disabled={tokenInspectorBusy}
                                          onClick={clearTokenInspector}>
                                          {t("common:clear", "Clear")}
                                        </Button>
                                      ) : null}
                                    </div>
                                    <span className="text-xs text-text-muted">
                                      {tokenizerName
                                        ? t(
                                            "option:writingPlayground.tokenInspectorTokenizer",
                                            "Tokenizer: {{tokenizer}}",
                                            { tokenizer: tokenizerName }
                                          )
                                        : t(
                                            "option:writingPlayground.tokenInspectorHint",
                                            "Inspect token count and tokenization output for the selected model."
                                          )}
                                    </span>
                                    {tokenInspectorUnavailableReason ? (
                                      <Alert
                                        type="info"
                                        showIcon
                                        message={tokenInspectorUnavailableReason}
                                      />
                                    ) : null}
                                    {tokenInspectorError ? (
                                      <Alert
                                        type="error"
                                        showIcon
                                        message={tokenInspectorError}
                                      />
                                    ) : null}
                                    {tokenCountResult ? (
                                      <div className="rounded-md border border-border bg-surface p-3">
                                        <div className="flex flex-wrap items-center gap-3 text-xs">
                                          <Tag color="blue">
                                            {t(
                                              "option:writingPlayground.tokenInspectorCountLabel",
                                              "{{count}} tokens",
                                              {
                                                count: tokenCountResult.count
                                              }
                                            )}
                                          </Tag>
                                          <span className="text-text-muted">
                                            {t(
                                              "option:writingPlayground.tokenInspectorCharsLabel",
                                              "{{count}} chars",
                                              {
                                                count: tokenCountResult.meta.input_chars
                                              }
                                            )}
                                          </span>
                                        </div>
                                      </div>
                                    ) : null}
                                    {tokenizeResult ? (
                                      <div className="flex flex-col gap-2">
                                        <div className="max-h-56 overflow-y-auto rounded-md border border-border bg-surface">
                                          <div className="grid grid-cols-[auto_auto_1fr] gap-x-3 gap-y-1 px-3 py-2 text-xs">
                                            <span className="font-medium text-text-muted">
                                              #
                                            </span>
                                            <span className="font-medium text-text-muted">
                                              ID
                                            </span>
                                            <span className="font-medium text-text-muted">
                                              {t(
                                                "option:writingPlayground.tokenInspectorTextLabel",
                                                "Text"
                                              )}
                                            </span>
                                            {tokenPreviewRows.map((row) => (
                                              <React.Fragment
                                                key={`${row.index}-${row.id}`}>
                                                <span className="text-text-muted">
                                                  {row.index + 1}
                                                </span>
                                                <span className="text-text">
                                                  {row.id}
                                                </span>
                                                <span className="whitespace-pre-wrap text-text">
                                                  {row.text}
                                                </span>
                                              </React.Fragment>
                                            ))}
                                          </div>
                                        </div>
                                        {tokenPreviewTruncated ? (
                                          <span className="text-xs text-text-muted">
                                            {t(
                                              "option:writingPlayground.tokenInspectorTruncated",
                                              "Showing first {{count}} of {{total}} tokens.",
                                              {
                                                count: tokenPreviewRows.length,
                                                total: tokenPreviewTotal
                                              }
                                            )}
                                          </span>
                                        ) : null}
                                      </div>
                                    ) : null}
                                  </div>
                                )
                              }
                            ]
                          : []
                      )
                      .concat(
                        showWordcloudPanel
                          ? [
                              {
                                key: "wordcloud",
                                label: t(
                                  "option:writingPlayground.wordcloudTitle",
                                  "Wordcloud"
                                ),
                                children: (
                                  <div className="flex flex-col gap-3">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Button
                                        size="small"
                                        disabled={!canGenerateWordcloud}
                                        loading={isGeneratingWordcloud}
                                        onClick={() => {
                                          void handleGenerateWordcloud()
                                        }}>
                                        {t(
                                          "option:writingPlayground.wordcloudGenerateAction",
                                          "Generate wordcloud"
                                        )}
                                      </Button>
                                      {wordcloudStatus || wordcloudError ? (
                                        <Button
                                          size="small"
                                          disabled={isGeneratingWordcloud}
                                          onClick={clearWordcloud}>
                                          {t("common:clear", "Clear")}
                                        </Button>
                                      ) : null}
                                      {wordcloudStatus ? (
                                        <Tag color={wordcloudStatusColor}>
                                          {wordcloudStatus}
                                        </Tag>
                                      ) : null}
                                    </div>
                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                      <div className="flex flex-col gap-1">
                                        <span className="text-xs text-text-muted">
                                          {t(
                                            "option:writingPlayground.wordcloudMaxWordsLabel",
                                            "Max words"
                                          )}
                                        </span>
                                        <InputNumber
                                          size="small"
                                          min={1}
                                          max={MAX_WORDCLOUD_WORDS}
                                          step={1}
                                          value={wordcloudMaxWords}
                                          disabled={isGeneratingWordcloud}
                                          onChange={(value) =>
                                            setWordcloudMaxWords(
                                              value == null
                                                ? 100
                                                : Math.max(
                                                    1,
                                                    Math.min(
                                                      MAX_WORDCLOUD_WORDS,
                                                      Math.floor(value)
                                                    )
                                                  )
                                            )
                                          }
                                          className="w-full"
                                        />
                                      </div>
                                      <div className="flex flex-col gap-1">
                                        <span className="text-xs text-text-muted">
                                          {t(
                                            "option:writingPlayground.wordcloudMinLengthLabel",
                                            "Min word length"
                                          )}
                                        </span>
                                        <InputNumber
                                          size="small"
                                          min={1}
                                          max={64}
                                          step={1}
                                          value={wordcloudMinWordLength}
                                          disabled={isGeneratingWordcloud}
                                          onChange={(value) =>
                                            setWordcloudMinWordLength(
                                              value == null
                                                ? 3
                                                : Math.max(
                                                    1,
                                                    Math.min(64, Math.floor(value))
                                                  )
                                            )
                                          }
                                          className="w-full"
                                        />
                                      </div>
                                    </div>
                                    <Checkbox
                                      checked={wordcloudKeepNumbers}
                                      disabled={isGeneratingWordcloud}
                                      onChange={(event) =>
                                        setWordcloudKeepNumbers(
                                          event.target.checked
                                        )
                                      }>
                                      {t(
                                        "option:writingPlayground.wordcloudKeepNumbers",
                                        "Include numeric tokens"
                                      )}
                                    </Checkbox>
                                    <div className="flex flex-col gap-1">
                                      <span className="text-xs text-text-muted">
                                        {t(
                                          "option:writingPlayground.wordcloudStopwordsLabel",
                                          "Custom stopwords (comma or newline separated)"
                                        )}
                                      </span>
                                      <Input.TextArea
                                        value={wordcloudStopwordsInput}
                                        rows={3}
                                        disabled={isGeneratingWordcloud}
                                        onChange={(event) =>
                                          setWordcloudStopwordsInput(
                                            event.target.value
                                          )
                                        }
                                        placeholder={t(
                                          "option:writingPlayground.wordcloudStopwordsHint",
                                          "Leave empty to use server defaults."
                                        )}
                                      />
                                    </div>
                                    {wordcloudError ? (
                                      <Alert
                                        type="error"
                                        showIcon
                                        message={wordcloudError}
                                      />
                                    ) : null}
                                    {wordcloudMeta ? (
                                      <div className="rounded-md border border-border bg-surface p-3">
                                        <div className="flex flex-wrap items-center gap-3 text-xs">
                                          <Tag color="blue">
                                            {t(
                                              "option:writingPlayground.wordcloudTopWords",
                                              "{{count}} words",
                                              { count: wordcloudMeta.top_n }
                                            )}
                                          </Tag>
                                          <span className="text-text-muted">
                                            {t(
                                              "option:writingPlayground.wordcloudInputChars",
                                              "{{count}} chars",
                                              { count: wordcloudMeta.input_chars }
                                            )}
                                          </span>
                                          <span className="text-text-muted">
                                            {t(
                                              "option:writingPlayground.wordcloudTotalTokens",
                                              "{{count}} tokens",
                                              { count: wordcloudMeta.total_tokens }
                                            )}
                                          </span>
                                        </div>
                                      </div>
                                    ) : null}
                                    {wordcloudWords.length > 0 ? (
                                      <div className="max-h-56 overflow-y-auto rounded-md border border-border bg-surface px-3 py-2">
                                        <div className="flex flex-col gap-2">
                                          {wordcloudWords.map((word) => (
                                            <div
                                              key={`${word.text}-${word.weight}`}
                                              className="grid grid-cols-[1fr_auto] gap-2 text-xs">
                                              <div className="flex flex-col gap-1">
                                                <span className="text-text">
                                                  {word.text}
                                                </span>
                                                <div className="h-1.5 rounded bg-background">
                                                  <div
                                                    className="h-1.5 rounded bg-primary"
                                                    style={{
                                                      width: `${wordcloudTopWeight > 0 ? (word.weight / wordcloudTopWeight) * 100 : 0}%`
                                                    }}
                                                  />
                                                </div>
                                              </div>
                                              <span className="text-text-muted">
                                                {word.weight}
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ) : wordcloudStatus === "ready" ? (
                                      <Paragraph type="secondary" className="!mb-0">
                                        {t(
                                          "option:writingPlayground.wordcloudEmpty",
                                          "No words matched the current filters."
                                        )}
                                      </Paragraph>
                                    ) : null}
                                    {wordcloudId ? (
                                      <span className="text-xs text-text-muted">
                                        {t(
                                          "option:writingPlayground.wordcloudJobId",
                                          "Job ID: {{id}}",
                                          { id: wordcloudId }
                                        )}
                                      </span>
                                    ) : null}
                                  </div>
                                )
                              }
                            ]
                          : []
                      )}
                    />
                  </div>
                )
              ) : (
                <Empty
                  description={t(
                    "option:writingPlayground.selectSession",
                    "Select a session to begin."
                  )}
                />
              )}
            </Card>

            <Card
              title={t("option:writingPlayground.settingsTitle", "Settings")}
              extra={
                <div className="flex items-center gap-2">
                  <Button
                    size="small"
                    onClick={handleOpenTemplatesModal}
                    disabled={templateSelectDisabled}>
                    {t(
                      "option:writingPlayground.manageTemplates",
                      "Manage templates"
                    )}
                  </Button>
                  <Button
                    size="small"
                    onClick={handleOpenThemesModal}
                    disabled={themeSelectDisabled}>
                    {t(
                      "option:writingPlayground.manageThemes",
                      "Manage themes"
                    )}
                  </Button>
                </div>
              }>
              {activeSession ? (
                activeSessionLoading ? (
                  <Skeleton active />
                ) : activeSessionError ? (
                  <Alert
                    type="error"
                    showIcon
                    title={t(
                      "option:writingPlayground.settingsError",
                      "Unable to load session settings."
                    )}
                  />
                ) : (
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-3">
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.templateLabel",
                            "Template"
                          )}
                        </span>
                        <Select
                          allowClear
                          size="small"
                          options={templateOptions}
                          loading={templatesLoading}
                          value={selectedTemplateName ?? undefined}
                          disabled={templateSelectDisabled}
                          placeholder={t(
                            "option:writingPlayground.templatePlaceholder",
                            "Server default"
                          )}
                          onChange={(value) =>
                            handleTemplateChange(value ? String(value) : null)
                          }
                        />
                        <span className="text-xs text-text-muted">
                          {templatesError
                            ? t(
                                "option:writingPlayground.templateError",
                                "Unable to load templates."
                              )
                            : !hasTemplates
                              ? t(
                                  "option:writingPlayground.templateUnavailable",
                                  "Templates unavailable."
                                )
                              : t(
                                  "option:writingPlayground.templateHint",
                                  "Choose an instruct template for chat parsing and FIM."
                                )}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t("option:writingPlayground.themeLabel", "Theme")}
                        </span>
                        <Select
                          allowClear
                          size="small"
                          options={themeOptions}
                          loading={themesLoading}
                          value={selectedThemeName ?? undefined}
                          disabled={themeSelectDisabled}
                          placeholder={t(
                            "option:writingPlayground.themePlaceholder",
                            "Server default"
                          )}
                          onChange={(value) =>
                            handleThemeChange(value ? String(value) : null)
                          }
                        />
                        <span className="text-xs text-text-muted">
                          {themesError
                            ? t(
                                "option:writingPlayground.themeError",
                                "Unable to load themes."
                              )
                            : !hasThemes
                              ? t(
                                  "option:writingPlayground.themeUnavailable",
                                  "Themes unavailable."
                                )
                              : t(
                                  "option:writingPlayground.themeHint",
                                  "Apply a theme to style the editor."
                                )}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <Checkbox
                          checked={chatMode}
                          disabled={settingsDisabled}
                          onChange={(event) =>
                            handleChatModeChange(event.target.checked)
                          }>
                          {t(
                            "option:writingPlayground.chatModeLabel",
                            "Chat mode"
                          )}
                        </Checkbox>
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.chatModeHint",
                            "Parse prompt text into messages using the selected template."
                          )}
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.temperatureLabel",
                            "Temperature"
                          )}
                        </span>
                        <InputNumber
                          size="small"
                          min={0}
                          max={2}
                          step={0.01}
                          value={settings.temperature}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              temperature:
                                value == null
                                  ? DEFAULT_SETTINGS.temperature
                                  : value
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t("option:writingPlayground.topPLabel", "Top P")}
                        </span>
                        <InputNumber
                          size="small"
                          min={0}
                          max={1}
                          step={0.01}
                          value={settings.top_p}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              top_p:
                                value == null ? DEFAULT_SETTINGS.top_p : value
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t("option:writingPlayground.topKLabel", "Top K")}
                        </span>
                        <InputNumber
                          size="small"
                          min={0}
                          max={2048}
                          step={1}
                          value={settings.top_k}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              top_k:
                                value == null ? DEFAULT_SETTINGS.top_k : value
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.maxTokensLabel",
                            "Max tokens"
                          )}
                        </span>
                        <InputNumber
                          size="small"
                          min={1}
                          max={8192}
                          step={1}
                          value={settings.max_tokens}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              max_tokens:
                                value == null
                                  ? DEFAULT_SETTINGS.max_tokens
                                  : Math.max(1, Math.round(value))
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.presencePenaltyLabel",
                            "Presence penalty"
                          )}
                        </span>
                        <InputNumber
                          size="small"
                          min={-2}
                          max={2}
                          step={0.1}
                          value={settings.presence_penalty}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              presence_penalty:
                                value == null
                                  ? DEFAULT_SETTINGS.presence_penalty
                                  : value
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-text-muted">
                          {t(
                            "option:writingPlayground.frequencyPenaltyLabel",
                            "Frequency penalty"
                          )}
                        </span>
                        <InputNumber
                          size="small"
                          min={-2}
                          max={2}
                          step={0.1}
                          value={settings.frequency_penalty}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              frequency_penalty:
                                value == null
                                  ? DEFAULT_SETTINGS.frequency_penalty
                                  : value
                            })
                          }
                          className="w-full"
                        />
                      </div>
                      <div className="flex flex-col gap-1 sm:col-span-2">
                        <span className="text-xs text-text-muted">
                          {t("option:writingPlayground.seedLabel", "Seed")}
                        </span>
                        <InputNumber
                          size="small"
                          min={0}
                          step={1}
                          value={settings.seed ?? null}
                          disabled={settingsDisabled}
                          onChange={(value) =>
                            updateSetting({
                              seed:
                                value == null ? null : Math.max(0, Math.floor(value))
                            })
                          }
                          className="w-full"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-text-muted">
                        {t(
                          "option:writingPlayground.stopStringsLabel",
                          "Stop strings"
                        )}
                      </span>
                      <Input.TextArea
                        value={stopStringsInput}
                        disabled={settingsDisabled}
                        onChange={(event) => {
                          const nextInput = event.target.value
                          updateSetting(
                            { stop: normalizeStopStrings(nextInput) },
                            nextInput
                          )
                        }}
                        placeholder={t(
                          "option:writingPlayground.stopStringsPlaceholder",
                          "One per line"
                        )}
                        rows={4}
                      />
                    </div>
                    <Collapse
                      ghost
                      size="small"
                      defaultActiveKey={[]}
                      items={[
                        {
                          key: "context-controls",
                          label: t(
                            "option:writingPlayground.contextControlsLabel",
                            "Context controls"
                          ),
                          children: (
                            <div className="flex flex-col gap-4">
                              <div className="rounded-md border border-border bg-surface p-3">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-xs font-medium text-text">
                                    {t(
                                      "option:writingPlayground.memoryBlockLabel",
                                      "Memory block"
                                    )}
                                  </span>
                                  <Checkbox
                                    checked={memoryBlock.enabled}
                                    disabled={settingsDisabled}
                                    onChange={(event) =>
                                      updateMemoryBlock({
                                        enabled: event.target.checked
                                      })
                                    }>
                                    {t("common:enabled", "Enabled")}
                                  </Checkbox>
                                </div>
                                <div className="mt-3 grid grid-cols-1 gap-3">
                                  <Input
                                    value={memoryBlock.prefix}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.prefixLabel",
                                      "Prefix"
                                    )}
                                    onChange={(event) =>
                                      updateMemoryBlock({
                                        prefix: event.target.value
                                      })
                                    }
                                  />
                                  <Input.TextArea
                                    value={memoryBlock.text}
                                    rows={3}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.memoryTextPlaceholder",
                                      "Facts and reminders to keep consistent."
                                    )}
                                    onChange={(event) =>
                                      updateMemoryBlock({
                                        text: event.target.value
                                      })
                                    }
                                  />
                                  <Input
                                    value={memoryBlock.suffix}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.suffixLabel",
                                      "Suffix"
                                    )}
                                    onChange={(event) =>
                                      updateMemoryBlock({
                                        suffix: event.target.value
                                      })
                                    }
                                  />
                                </div>
                              </div>
                              <div className="rounded-md border border-border bg-surface p-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="text-xs font-medium text-text">
                                    {t(
                                      "option:writingPlayground.authorNoteLabel",
                                      "Author note"
                                    )}
                                  </span>
                                  <div className="flex items-center gap-3">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.authorDepthLabel",
                                        "Depth"
                                      )}
                                    </span>
                                    <InputNumber
                                      size="small"
                                      min={1}
                                      step={1}
                                      value={authorNote.insertion_depth}
                                      disabled={settingsDisabled}
                                      onChange={(value) =>
                                        updateAuthorNote({
                                          insertion_depth:
                                            value == null
                                              ? 1
                                              : Math.max(1, Math.floor(value))
                                        })
                                      }
                                    />
                                    <Checkbox
                                      checked={authorNote.enabled}
                                      disabled={settingsDisabled}
                                      onChange={(event) =>
                                        updateAuthorNote({
                                          enabled: event.target.checked
                                        })
                                      }>
                                      {t("common:enabled", "Enabled")}
                                    </Checkbox>
                                  </div>
                                </div>
                                <div className="mt-3 grid grid-cols-1 gap-3">
                                  <Input
                                    value={authorNote.prefix}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.prefixLabel",
                                      "Prefix"
                                    )}
                                    onChange={(event) =>
                                      updateAuthorNote({
                                        prefix: event.target.value
                                      })
                                    }
                                  />
                                  <Input.TextArea
                                    value={authorNote.text}
                                    rows={3}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.authorNotePlaceholder",
                                      "Guidance to inject during generation."
                                    )}
                                    onChange={(event) =>
                                      updateAuthorNote({
                                        text: event.target.value
                                      })
                                    }
                                  />
                                  <Input
                                    value={authorNote.suffix}
                                    disabled={settingsDisabled}
                                    placeholder={t(
                                      "option:writingPlayground.suffixLabel",
                                      "Suffix"
                                    )}
                                    onChange={(event) =>
                                      updateAuthorNote({
                                        suffix: event.target.value
                                      })
                                    }
                                  />
                                </div>
                              </div>
                              <div className="rounded-md border border-border bg-surface p-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="text-xs font-medium text-text">
                                    {t(
                                      "option:writingPlayground.worldInfoLabel",
                                      "World info"
                                    )}
                                  </span>
                                  <div className="flex items-center gap-2">
                                    <Checkbox
                                      checked={worldInfo.enabled}
                                      disabled={settingsDisabled}
                                      onChange={(event) =>
                                        updateWorldInfo({
                                          enabled: event.target.checked
                                        })
                                      }>
                                      {t("common:enabled", "Enabled")}
                                    </Checkbox>
                                    <Button
                                      size="small"
                                      disabled={settingsDisabled}
                                      onClick={addWorldInfoEntry}>
                                      {t(
                                        "option:writingPlayground.addWorldInfo",
                                        "Add entry"
                                      )}
                                    </Button>
                                  </div>
                                </div>
                                <div className="mt-3 flex flex-col gap-3">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.worldInfoSearchRange",
                                        "Search range (chars)"
                                      )}
                                    </span>
                                    <InputNumber
                                      size="small"
                                      min={0}
                                      step={100}
                                      value={worldInfo.search_range}
                                      disabled={settingsDisabled}
                                      onChange={(value) =>
                                        updateWorldInfo({
                                          search_range:
                                            value == null
                                              ? 0
                                              : Math.max(0, Math.floor(value))
                                        })
                                      }
                                    />
                                  </div>
                                  {worldInfoEntries.length === 0 ? (
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.worldInfoEmpty",
                                        "No world info entries yet."
                                      )}
                                    </span>
                                  ) : (
                                    <div className="flex flex-col gap-3">
                                      {worldInfoEntries.map((entry, index) => (
                                        <div
                                          key={entry.id}
                                          className="rounded-md border border-border bg-background p-3">
                                          <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-medium text-text">
                                              {t(
                                                "option:writingPlayground.worldInfoEntryLabel",
                                                "Entry {{index}}",
                                                { index: index + 1 }
                                              )}
                                            </span>
                                            <Button
                                              size="small"
                                              danger
                                              disabled={settingsDisabled}
                                              onClick={() =>
                                                removeWorldInfoEntry(entry.id)
                                              }>
                                              {t("common:delete", "Delete")}
                                            </Button>
                                          </div>
                                          <div className="mt-3 flex flex-col gap-3">
                                            <div className="flex flex-wrap items-center gap-3">
                                              <Checkbox
                                                checked={entry.enabled}
                                                disabled={settingsDisabled}
                                                onChange={(event) =>
                                                  updateWorldInfoEntry(entry.id, {
                                                    enabled: event.target.checked
                                                  })
                                                }>
                                                {t("common:enabled", "Enabled")}
                                              </Checkbox>
                                              <Checkbox
                                                checked={entry.use_regex}
                                                disabled={settingsDisabled}
                                                onChange={(event) =>
                                                  updateWorldInfoEntry(entry.id, {
                                                    use_regex:
                                                      event.target.checked
                                                  })
                                                }>
                                                {t(
                                                  "option:writingPlayground.worldInfoRegex",
                                                  "Regex"
                                                )}
                                              </Checkbox>
                                              <Checkbox
                                                checked={entry.case_sensitive}
                                                disabled={settingsDisabled}
                                                onChange={(event) =>
                                                  updateWorldInfoEntry(entry.id, {
                                                    case_sensitive:
                                                      event.target.checked
                                                  })
                                                }>
                                                {t(
                                                  "option:writingPlayground.worldInfoCaseSensitive",
                                                  "Case sensitive"
                                                )}
                                              </Checkbox>
                                            </div>
                                            <Input.TextArea
                                              value={entry.keys.join("\n")}
                                              rows={2}
                                              disabled={settingsDisabled}
                                              placeholder={t(
                                                "option:writingPlayground.worldInfoKeysPlaceholder",
                                                "Trigger keys (comma or newline separated)"
                                              )}
                                              onChange={(event) =>
                                                updateWorldInfoEntry(entry.id, {
                                                  keys: parseWorldInfoKeysInput(
                                                    event.target.value
                                                  )
                                                })
                                              }
                                            />
                                            <Input.TextArea
                                              value={entry.content}
                                              rows={3}
                                              disabled={settingsDisabled}
                                              placeholder={t(
                                                "option:writingPlayground.worldInfoContentPlaceholder",
                                                "Context to inject when triggered."
                                              )}
                                              onChange={(event) =>
                                                updateWorldInfoEntry(entry.id, {
                                                  content: event.target.value
                                                })
                                              }
                                            />
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          )
                        }
                      ]}
                    />
                    {showAdvancedSamplerControls && (
                      <Collapse
                        ghost
                        size="small"
                        defaultActiveKey={
                          supportsAdvancedCompat ? [] : ["advanced-extra-body"]
                        }
                        items={[
                          {
                            key: "advanced-extra-body",
                            label: t(
                              "option:writingPlayground.advancedSamplerLabel",
                              "Advanced sampler controls (extra_body)"
                            ),
                            children: (
                              <div className="flex flex-col gap-3">
                                {extraBodyCompat ? (
                                  <span className="text-xs text-text-muted">
                                    {extraBodyCompat.notes ||
                                      t(
                                        "option:writingPlayground.advancedSamplerHint",
                                        "Advanced controls are sent through extra_body for provider compatibility."
                                      )}
                                  </span>
                                ) : null}
                                {!supportsAdvancedCompat ? (
                                  <Alert
                                    type="info"
                                    showIcon
                                    message={
                                      extraBodyCompat?.effective_reason ||
                                      t(
                                        "option:writingPlayground.advancedUnsupported",
                                        "Advanced sampler controls are disabled by runtime configuration."
                                      )
                                    }
                                  />
                                ) : null}
                                <div className="flex flex-wrap items-center gap-2">
                                  <Button
                                    size="small"
                                    disabled={
                                      settingsDisabled || !supportsAdvancedCompat
                                    }
                                    onClick={openExtraBodyJsonEditor}>
                                    {t(
                                      "option:writingPlayground.extraBodyJsonEditorLabel",
                                      "Edit raw extra_body JSON"
                                    )}
                                  </Button>
                                  {hasAdvancedSettingsValues ? (
                                    <Button
                                      size="small"
                                      disabled={settingsDisabled}
                                      onClick={() => {
                                        updateSetting({
                                          advanced_extra_body: {}
                                        })
                                        setBannedTokensInput("")
                                        setDrySequenceBreakersInput("")
                                      }}>
                                      {t(
                                        "option:writingPlayground.clearAdvancedSettings",
                                        "Clear advanced values"
                                      )}
                                    </Button>
                                  ) : null}
                                </div>
                                {knownExtraBodyParams.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {knownExtraBodyParams.map((param) => (
                                      <Tag key={param}>{param}</Tag>
                                    ))}
                                  </div>
                                ) : null}
                                {advancedExtraBodyUnknownKeys.length > 0 ? (
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.extraBodyCustomKeys",
                                        "Custom keys from raw JSON:"
                                      )}
                                    </span>
                                    <div className="flex flex-wrap gap-1">
                                      {advancedExtraBodyUnknownKeys.map((key) => (
                                        <Tag key={key}>{key}</Tag>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                  {ADVANCED_NUMBER_PARAMS.filter((param) =>
                                    shouldShowAdvancedParam(param.key)
                                  ).map((param) => (
                                    <div
                                      key={param.key}
                                      className="flex flex-col gap-1">
                                      <span className="text-xs text-text-muted">
                                        {param.label}
                                      </span>
                                      <InputNumber
                                        size="small"
                                        min={param.min}
                                        max={param.max}
                                        step={param.step}
                                        value={getAdvancedNumberValue(param.key)}
                                        disabled={
                                          settingsDisabled || !supportsAdvancedCompat
                                        }
                                        onChange={(value) => {
                                          const parsed =
                                            value == null
                                              ? null
                                              : param.step === 1
                                                ? Math.round(value)
                                                : value
                                          updateAdvancedExtraBodyField(
                                            param.key,
                                            parsed
                                          )
                                        }}
                                        className="w-full"
                                      />
                                    </div>
                                  ))}
                                </div>
                                {shouldShowAdvancedParam("ignore_eos") && (
                                  <Checkbox
                                    checked={Boolean(advancedExtraBody.ignore_eos)}
                                    disabled={
                                      settingsDisabled || !supportsAdvancedCompat
                                    }
                                    onChange={(event) =>
                                      updateAdvancedExtraBodyField(
                                        "ignore_eos",
                                        event.target.checked ? true : null
                                      )
                                    }>
                                    {t(
                                      "option:writingPlayground.ignoreEosLabel",
                                      "Ignore EOS"
                                    )}
                                  </Checkbox>
                                )}
                                {shouldShowAdvancedParam("banned_tokens") && (
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.bannedTokensLabel",
                                        "Banned tokens (comma or newline separated)"
                                      )}
                                    </span>
                                    <Input.TextArea
                                      value={bannedTokensInput}
                                      rows={3}
                                      disabled={
                                        settingsDisabled || !supportsAdvancedCompat
                                      }
                                      onChange={(event) => {
                                        const nextInput = event.target.value
                                        setBannedTokensInput(nextInput)
                                        updateAdvancedExtraBodyField(
                                          "banned_tokens",
                                          parseStringListInput(nextInput)
                                        )
                                      }}
                                    />
                                  </div>
                                )}
                                {shouldShowAdvancedParam("dry_sequence_breakers") && (
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.drySequenceBreakersLabel",
                                        "DRY sequence breakers (comma or newline separated)"
                                      )}
                                    </span>
                                    <Input.TextArea
                                      value={drySequenceBreakersInput}
                                      rows={3}
                                      disabled={
                                        settingsDisabled || !supportsAdvancedCompat
                                      }
                                      onChange={(event) => {
                                        const nextInput = event.target.value
                                        setDrySequenceBreakersInput(nextInput)
                                        updateAdvancedExtraBodyField(
                                          "dry_sequence_breakers",
                                          parseStringListInput(nextInput)
                                        )
                                      }}
                                    />
                                  </div>
                                )}
                                {shouldShowAdvancedParam("grammar") && (
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs text-text-muted">
                                      {t(
                                        "option:writingPlayground.grammarLabel",
                                        "Grammar"
                                      )}
                                    </span>
                                    <Input.TextArea
                                      value={
                                        typeof advancedExtraBody.grammar === "string"
                                          ? advancedExtraBody.grammar
                                          : ""
                                      }
                                      rows={4}
                                      disabled={
                                        settingsDisabled || !supportsAdvancedCompat
                                      }
                                      onChange={(event) =>
                                        updateAdvancedExtraBodyField(
                                          "grammar",
                                          event.target.value
                                        )
                                      }
                                    />
                                  </div>
                                )}
                              </div>
                            )
                          }
                        ]}
                      />
                    )}
                  </div>
                )
              ) : (
                <Empty
                  description={t(
                    "option:writingPlayground.settingsEmpty",
                    "Select a session to edit settings."
                  )}
                />
              )}
            </Card>
          </div>
        </div>
      )}

      <Modal
        title={t(
          "option:writingPlayground.extraBodyJsonModalTitle",
          "Edit extra_body JSON"
        )}
        open={extraBodyJsonModalOpen}
        onCancel={() => {
          setExtraBodyJsonModalOpen(false)
          setExtraBodyJsonError(null)
        }}
        onOk={applyExtraBodyJsonDraft}
        okText={t("common:apply", "Apply")}
        cancelText={t("common:cancel", "Cancel")}
        okButtonProps={{ disabled: settingsDisabled || !supportsAdvancedCompat }}
        width={760}>
        <div className="flex flex-col gap-3">
          <span className="text-xs text-text-muted">
            {t(
              "option:writingPlayground.extraBodyJsonModalHint",
              "Provide a JSON object to merge advanced provider-specific parameters."
            )}
          </span>
          {extraBodyJsonError ? (
            <Alert type="error" showIcon message={extraBodyJsonError} />
          ) : null}
          <Input.TextArea
            value={extraBodyJsonDraft}
            rows={14}
            disabled={settingsDisabled || !supportsAdvancedCompat}
            onChange={(event) => {
              setExtraBodyJsonDraft(event.target.value)
              if (extraBodyJsonError) {
                setExtraBodyJsonError(null)
              }
            }}
          />
        </div>
      </Modal>

      <Modal
        title={t(
          "option:writingPlayground.templatesModalTitle",
          "Manage templates"
        )}
        open={templatesModalOpen}
        onCancel={() => setTemplatesModalOpen(false)}
        footer={null}
        width={900}>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-text-muted">
              {t(
                "option:writingPlayground.templateImportHint",
                "Import JSON to add or update templates."
              )}
            </span>
            <div className="flex items-center gap-2">
              <Button size="small" onClick={handleTemplateNew}>
                {t("option:writingPlayground.templateNewAction", "New")}
              </Button>
              <Button
                size="small"
                onClick={() => templateFileInputRef.current?.click()}
                loading={templateImporting}>
                {t("option:writingPlayground.templateImportAction", "Import")}
              </Button>
              <Button
                size="small"
                disabled={templateExportDisabled}
                onClick={() => {
                  if (editingTemplate) exportTemplate(editingTemplate)
                }}>
                {t("option:writingPlayground.templateExportAction", "Export")}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
            <div className="flex flex-col gap-2">
              <span className="text-xs text-text-muted">
                {t("option:writingPlayground.templateListTitle", "Templates")}
              </span>
              {templatesLoading ? (
                <Skeleton active />
              ) : templatesError ? (
                <Alert
                  type="error"
                  showIcon
                  title={t(
                    "option:writingPlayground.templateError",
                    "Unable to load templates."
                  )}
                />
              ) : templates.length === 0 ? (
                <Empty
                  description={t(
                    "option:writingPlayground.templateListEmpty",
                    "No templates yet."
                  )}
                />
              ) : (
                <List
                  dataSource={templates}
                  rowKey={(template) => template.name}
                  renderItem={(template) => {
                    const isSelected = editingTemplate?.name === template.name
                    return (
                      <List.Item
                        className={`cursor-pointer rounded-md px-2 py-2 transition ${
                          isSelected
                            ? "bg-surface-hover"
                            : "hover:bg-surface-hover/60"
                        }`}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleTemplateSelect(template)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            handleTemplateSelect(template)
                          }
                        }}>
                        <div className="flex w-full items-center justify-between gap-2">
                          <span className="text-sm font-medium text-text">
                            {template.name}
                          </span>
                          {template.is_default ? (
                            <Tag color="blue">
                              {t(
                                "option:writingPlayground.templateDefaultTag",
                                "Default"
                              )}
                            </Tag>
                          ) : null}
                        </div>
                      </List.Item>
                    )
                  }}
                />
              )}
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t(
                    "option:writingPlayground.templateNameLabel",
                    "Template name"
                  )}
                </span>
                <Input
                  value={templateForm.name}
                  disabled={templateFormDisabled}
                  onChange={(event) =>
                    updateTemplateForm({ name: event.target.value })
                  }
                />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateSystemPrefixLabel",
                      "System prefix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.systemPrefix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ systemPrefix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateSystemSuffixLabel",
                      "System suffix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.systemSuffix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ systemSuffix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateUserPrefixLabel",
                      "User prefix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.userPrefix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ userPrefix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateUserSuffixLabel",
                      "User suffix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.userSuffix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ userSuffix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateAssistantPrefixLabel",
                      "Assistant prefix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.assistantPrefix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ assistantPrefix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-text-muted">
                    {t(
                      "option:writingPlayground.templateAssistantSuffixLabel",
                      "Assistant suffix"
                    )}
                  </span>
                  <Input.TextArea
                    value={templateForm.assistantSuffix}
                    disabled={templateFormDisabled}
                    onChange={(event) =>
                      updateTemplateForm({ assistantSuffix: event.target.value })
                    }
                    rows={2}
                    className="font-mono text-xs"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t(
                    "option:writingPlayground.templateFimTemplateLabel",
                    "FIM template"
                  )}
                </span>
                <Input.TextArea
                  value={templateForm.fimTemplate}
                  disabled={templateFormDisabled}
                  onChange={(event) =>
                    updateTemplateForm({ fimTemplate: event.target.value })
                  }
                  rows={3}
                  className="font-mono text-xs"
                />
                <span className="text-xs text-text-muted">
                  {t(
                    "option:writingPlayground.templateFimTemplateHint",
                    "Use {{prefix}} and {{suffix}} placeholders."
                  )}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <Checkbox
                  checked={templateForm.isDefault}
                  disabled={templateFormDisabled}
                  onChange={(event) =>
                    updateTemplateForm({ isDefault: event.target.checked })
                  }>
                  {t(
                    "option:writingPlayground.templateDefaultLabel",
                    "Default template"
                  )}
                </Checkbox>
                <div className="flex items-center gap-2">
                  <Button
                    type="primary"
                    size="small"
                    onClick={handleTemplateSave}
                    loading={templateSaveLoading}
                    disabled={templateSaveDisabled}>
                    {editingTemplate
                      ? t("common:save", "Save")
                      : t(
                          "option:writingPlayground.templateCreateAction",
                          "Create"
                        )}
                  </Button>
                  <Button
                    size="small"
                    danger
                    disabled={templateDeleteDisabled}
                    loading={deleteTemplateMutation.isPending}
                    onClick={() => {
                      if (editingTemplate) {
                        confirmDeleteTemplate(editingTemplate)
                      }
                    }}>
                    {t("common:delete", "Delete")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <input
          ref={templateFileInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleTemplateImport}
          data-testid="writing-template-import"
          className="hidden"
        />
      </Modal>

      <Modal
        title={t("option:writingPlayground.themesModalTitle", "Manage themes")}
        open={themesModalOpen}
        onCancel={() => setThemesModalOpen(false)}
        footer={null}
        width={900}>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-text-muted">
              {t(
                "option:writingPlayground.themeImportHint",
                "Import JSON to add or update themes."
              )}
            </span>
            <div className="flex items-center gap-2">
              <Button size="small" onClick={handleThemeNew}>
                {t("option:writingPlayground.themeNewAction", "New")}
              </Button>
              <Button
                size="small"
                onClick={() => themeFileInputRef.current?.click()}
                loading={themeImporting}>
                {t("option:writingPlayground.themeImportAction", "Import")}
              </Button>
              <Button
                size="small"
                disabled={themeExportDisabled}
                onClick={() => {
                  if (editingTheme) exportTheme(editingTheme)
                }}>
                {t("option:writingPlayground.themeExportAction", "Export")}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
            <div className="flex flex-col gap-2">
              <span className="text-xs text-text-muted">
                {t("option:writingPlayground.themeListTitle", "Themes")}
              </span>
              {themesLoading ? (
                <Skeleton active />
              ) : themesError ? (
                <Alert
                  type="error"
                  showIcon
                  title={t(
                    "option:writingPlayground.themeError",
                    "Unable to load themes."
                  )}
                />
              ) : themes.length === 0 ? (
                <Empty
                  description={t(
                    "option:writingPlayground.themeListEmpty",
                    "No themes yet."
                  )}
                />
              ) : (
                <List
                  dataSource={themes}
                  rowKey={(theme) => theme.name}
                  renderItem={(theme) => {
                    const isSelected = editingTheme?.name === theme.name
                    return (
                      <List.Item
                        className={`cursor-pointer rounded-md px-2 py-2 transition ${
                          isSelected
                            ? "bg-surface-hover"
                            : "hover:bg-surface-hover/60"
                        }`}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleThemeSelect(theme)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            handleThemeSelect(theme)
                          }
                        }}>
                        <div className="flex w-full items-center justify-between gap-2">
                          <span className="text-sm font-medium text-text">
                            {theme.name}
                          </span>
                          {theme.is_default ? (
                            <Tag color="blue">
                              {t(
                                "option:writingPlayground.themeDefaultTag",
                                "Default"
                              )}
                            </Tag>
                          ) : null}
                        </div>
                      </List.Item>
                    )
                  }}
                />
              )}
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t("option:writingPlayground.themeNameLabel", "Theme name")}
                </span>
                <Input
                  value={themeForm.name}
                  disabled={themeFormDisabled}
                  onChange={(event) =>
                    updateThemeForm({ name: event.target.value })
                  }
                />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t(
                    "option:writingPlayground.themeClassLabel",
                    "Theme class"
                  )}
                </span>
                <Input
                  value={themeForm.className}
                  disabled={themeFormDisabled}
                  onChange={(event) =>
                    updateThemeForm({ className: event.target.value })
                  }
                  placeholder={t(
                    "option:writingPlayground.themeClassPlaceholder",
                    "e.g. miku-dream"
                  )}
                />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t("option:writingPlayground.themeCssLabel", "Theme CSS")}
                </span>
                <Input.TextArea
                  value={themeForm.css}
                  disabled={themeFormDisabled}
                  onChange={(event) =>
                    updateThemeForm({ css: event.target.value })
                  }
                  rows={6}
                  className="font-mono text-xs"
                />
                <span className="text-xs text-text-muted">
                  {t(
                    "option:writingPlayground.themeCssHint",
                    "CSS is scoped to .writing-playground; @import and url() are stripped."
                  )}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-muted">
                  {t("option:writingPlayground.themeOrderLabel", "Order")}
                </span>
                <InputNumber
                  value={themeForm.order}
                  disabled={themeFormDisabled}
                  onChange={(value) =>
                    updateThemeForm({
                      order: typeof value === "number" ? value : 0
                    })
                  }
                  className="w-full"
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <Checkbox
                  checked={themeForm.isDefault}
                  disabled={themeFormDisabled}
                  onChange={(event) =>
                    updateThemeForm({ isDefault: event.target.checked })
                  }>
                  {t(
                    "option:writingPlayground.themeDefaultLabel",
                    "Default theme"
                  )}
                </Checkbox>
                <div className="flex items-center gap-2">
                  <Button
                    type="primary"
                    size="small"
                    onClick={handleThemeSave}
                    loading={themeSaveLoading}
                    disabled={themeSaveDisabled}>
                    {editingTheme
                      ? t("common:save", "Save")
                      : t("option:writingPlayground.themeCreateAction", "Create")}
                  </Button>
                  <Button
                    size="small"
                    danger
                    disabled={themeDeleteDisabled}
                    loading={deleteThemeMutation.isPending}
                    onClick={() => {
                      if (editingTheme) {
                        confirmDeleteTheme(editingTheme)
                      }
                    }}>
                    {t("common:delete", "Delete")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <input
          ref={themeFileInputRef}
          type="file"
          accept=".json,application/json"
          onChange={handleThemeImport}
          data-testid="writing-theme-import"
          className="hidden"
        />
      </Modal>

      <Modal
        title={t("option:writingPlayground.createSessionTitle", "New session")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createSessionMutation.mutate(newSessionName.trim())}
        okButtonProps={{
          disabled: !canCreateSession,
          loading: createSessionMutation.isPending
        }}>
        <div className="flex flex-col gap-2">
          <span className="text-sm text-text-muted">
            {t(
              "option:writingPlayground.createSessionLabel",
              "Session name"
            )}
          </span>
          <Input
            value={newSessionName}
            onChange={(event) => setNewSessionName(event.target.value)}
            placeholder={t(
              "option:writingPlayground.createSessionPlaceholder",
              "e.g. Draft ideas"
            )}
            onPressEnter={() => {
              if (canCreateSession && !createSessionMutation.isPending) {
                createSessionMutation.mutate(newSessionName.trim())
              }
            }}
          />
        </div>
      </Modal>

      <Modal
        title={t("option:writingPlayground.renameSessionTitle", "Rename session")}
        open={renameModalOpen}
        onCancel={() => {
          setRenameModalOpen(false)
          setRenameTarget(null)
          setRenameSessionName("")
        }}
        onOk={() => {
          if (renameTarget) {
            renameSessionMutation.mutate({
              session: renameTarget,
              name: renameSessionName.trim()
            })
          }
        }}
        okButtonProps={{
          disabled: !canRenameSession,
          loading: renameSessionMutation.isPending
        }}>
        <div className="flex flex-col gap-2">
          <span className="text-sm text-text-muted">
            {t("option:writingPlayground.renameSessionLabel", "Session name")}
          </span>
          <Input
            value={renameSessionName}
            onChange={(event) => setRenameSessionName(event.target.value)}
            placeholder={t(
              "option:writingPlayground.renameSessionPlaceholder",
              "e.g. Revised draft"
            )}
            onPressEnter={() => {
              if (canRenameSession && renameTarget && !renameSessionMutation.isPending) {
                renameSessionMutation.mutate({
                  session: renameTarget,
                  name: renameSessionName.trim()
                })
              }
            }}
          />
        </div>
      </Modal>
      <input
        ref={sessionFileInputRef}
        type="file"
        accept=".json,application/json"
        onChange={handleSessionImport}
        data-testid="writing-session-import"
        className="hidden"
      />
    </div>
  )
}
