import {
  coerceBoolean,
  coerceOptionalString,
  coerceNumber,
  coerceString,
  defineSetting
} from "@/services/settings/registry"

const THEME_VALUES = ["system", "dark", "light"] as const
export type ThemeValue = (typeof THEME_VALUES)[number]

const resolveSystemTheme = (): "dark" | "light" => {
  if (typeof window === "undefined") return "light"
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
    ? "dark"
    : "light"
}

const normalizeThemeValue = (value: unknown, fallback: ThemeValue) => {
  const normalized = String(value || "").toLowerCase()
  return THEME_VALUES.includes(normalized as ThemeValue)
    ? (normalized as ThemeValue)
    : fallback
}

export const THEME_SETTING = defineSetting(
  "theme",
  "system" as ThemeValue,
  (value) => normalizeThemeValue(value, "system"),
  {
    area: "local",
    validate: (value) => THEME_VALUES.includes(value),
    localStorageKey: "theme",
    mirrorToLocalStorage: true,
    localStorageSerialize: (value) =>
      value === "system" ? resolveSystemTheme() : value
  }
)

export const I18N_LANGUAGE_SETTING = defineSetting(
  "i18nextLng",
  "en",
  (value) => coerceString(value, "en"),
  {
    area: "local",
    localStorageKey: "i18nextLng",
    mirrorToLocalStorage: true
  }
)

export const CHAT_BACKGROUND_IMAGE_SETTING = defineSetting(
  "chatBackgroundImage",
  undefined as string | undefined,
  coerceOptionalString
)

export const CONTEXT_FILE_SIZE_MB_SETTING = defineSetting(
  "tldw:contextFileMaxSizeMb",
  10,
  (value) => coerceNumber(value, 10),
  {
    area: "local",
    validate: (value) => Number.isFinite(value) && value > 0
  }
)

const UI_MODE_VALUES = ["sidePanel", "webui"] as const
export type UiModeValue = (typeof UI_MODE_VALUES)[number]

const normalizeUiModeValue = (value: unknown, fallback: UiModeValue) => {
  const normalized = String(value || "")
  return UI_MODE_VALUES.includes(normalized as UiModeValue)
    ? (normalized as UiModeValue)
    : fallback
}

export const UI_MODE_SETTING = defineSetting(
  "uiMode",
  "sidePanel" as UiModeValue,
  (value) => normalizeUiModeValue(value, "sidePanel"),
  {
    validate: (value) => UI_MODE_VALUES.includes(value)
  }
)

const SIDEBAR_TAB_VALUES = ["server", "folders"] as const
type SidebarTabValue = (typeof SIDEBAR_TAB_VALUES)[number]

export const SIDEBAR_ACTIVE_TAB_SETTING = defineSetting(
  "tldw:sidebar:activeTab",
  "server" as SidebarTabValue,
  (value) => {
    const normalized = String(value || "").toLowerCase()
    return SIDEBAR_TAB_VALUES.includes(normalized as SidebarTabValue)
      ? (normalized as SidebarTabValue)
      : "server"
  },
  {
    area: "local",
    validate: (value) => SIDEBAR_TAB_VALUES.includes(value)
  }
)

export const SIDEBAR_SHORTCUTS_COLLAPSED_SETTING = defineSetting(
  "tldw:sidebar:shortcutsCollapsed",
  false,
  (value) => coerceBoolean(value, false),
  {
    area: "local"
  }
)

export const SIDEBAR_SHORTCUT_MAX_COUNT = 10

export const HEADER_SHORTCUT_IDS = [
  "chat",
  "prompts",
  "characters",
  "chat-dictionaries",
  "world-books",
  "knowledge-qa",
  "media",
  "multi-item-review",
  "flashcards",
  "notes",
  "watchlists",
  "collections",
  "model-playground",
  "workspace-playground",
  "writing-playground",
  "quizzes",
  "evaluations",
  "stt-playground",
  "tts-playground",
  "chunking-playground",
  "kanban-playground",
  "data-tables",
  "prompt-studio",
  "audiobook-studio",
  "admin-server",
  "documentation",
  "chatbooks-playground",
  "moderation-playground",
  "admin-llamacpp",
  "admin-mlx",
  "settings"
] as const
export type HeaderShortcutId = (typeof HEADER_SHORTCUT_IDS)[number]

export const DEFAULT_HEADER_SHORTCUT_SELECTION = [
  ...HEADER_SHORTCUT_IDS
] as HeaderShortcutId[]

const coerceHeaderShortcutSelection = (
  value: unknown,
  fallback: HeaderShortcutId[]
): HeaderShortcutId[] => {
  if (!Array.isArray(value)) return fallback
  const allowed = new Set<HeaderShortcutId>(HEADER_SHORTCUT_IDS)
  const unique = new Set<HeaderShortcutId>()
  for (const entry of value) {
    if (typeof entry !== "string") continue
    if (allowed.has(entry as HeaderShortcutId)) {
      unique.add(entry as HeaderShortcutId)
    }
  }
  return HEADER_SHORTCUT_IDS.filter((id) => unique.has(id))
}

export const HEADER_SHORTCUT_SELECTION_SETTING = defineSetting(
  "tldw:headerShortcuts:selection",
  DEFAULT_HEADER_SHORTCUT_SELECTION,
  (value) =>
    coerceHeaderShortcutSelection(value, DEFAULT_HEADER_SHORTCUT_SELECTION),
  {
    area: "local"
  }
)

export const SIDEBAR_SHORTCUT_IDS = [
  "quick-ingest",
  ...HEADER_SHORTCUT_IDS
] as const
export type SidebarShortcutId = (typeof SIDEBAR_SHORTCUT_IDS)[number]

export const DEFAULT_SIDEBAR_SHORTCUT_SELECTION = SIDEBAR_SHORTCUT_IDS.slice(
  0,
  SIDEBAR_SHORTCUT_MAX_COUNT
) as SidebarShortcutId[]

const coerceSidebarShortcutSelection = (
  value: unknown,
  fallback: SidebarShortcutId[]
): SidebarShortcutId[] => {
  if (!Array.isArray(value)) return fallback
  const allowed = new Set<SidebarShortcutId>(SIDEBAR_SHORTCUT_IDS)
  const legacyMap: Record<string, SidebarShortcutId> = {
    knowledge: "knowledge-qa",
    "multi-item": "multi-item-review"
  }
  const unique = new Set<SidebarShortcutId>()
  for (const entry of value) {
    if (typeof entry !== "string") continue
    const mapped = legacyMap[entry] ?? entry
    if (allowed.has(mapped as SidebarShortcutId)) {
      unique.add(mapped as SidebarShortcutId)
    }
  }
  const normalized = SIDEBAR_SHORTCUT_IDS.filter((id) => unique.has(id)).slice(
    0,
    SIDEBAR_SHORTCUT_MAX_COUNT
  )
  if (normalized.length === 0 && value.length > 0) {
    return fallback
  }
  return normalized
}

export const SIDEBAR_SHORTCUT_SELECTION_SETTING = defineSetting(
  "tldw:sidebar:shortcutSelection",
  DEFAULT_SIDEBAR_SHORTCUT_SELECTION,
  (value) =>
    coerceSidebarShortcutSelection(value, DEFAULT_SIDEBAR_SHORTCUT_SELECTION),
  {
    area: "local"
  }
)

const VOICE_CHAT_TTS_MODE_VALUES = ["stream", "full"] as const
export type VoiceChatTtsMode = (typeof VOICE_CHAT_TTS_MODE_VALUES)[number]

const coerceStringArray = (
  value: unknown,
  fallback: string[] = []
): string[] => {
  if (Array.isArray(value)) {
    return value
      .filter((entry) => typeof entry === "string")
      .map((entry) => entry.trim())
      .filter(Boolean)
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
  }
  return fallback
}

const coerceVoiceChatTtsMode = (
  value: unknown,
  fallback: VoiceChatTtsMode
): VoiceChatTtsMode => {
  const normalized = String(value || "").toLowerCase()
  return VOICE_CHAT_TTS_MODE_VALUES.includes(normalized as VoiceChatTtsMode)
    ? (normalized as VoiceChatTtsMode)
    : fallback
}

export const VOICE_CHAT_ENABLED_SETTING = defineSetting(
  "voiceChatEnabled",
  false,
  (value) => coerceBoolean(value, false),
  { area: "local" }
)

export const VOICE_CHAT_MODEL_SETTING = defineSetting(
  "voiceChatModel",
  "",
  (value) => coerceString(value, ""),
  { area: "local" }
)

export const VOICE_CHAT_PAUSE_MS_SETTING = defineSetting(
  "voiceChatPauseMs",
  900,
  (value) => coerceNumber(value, 900),
  {
    area: "local",
    validate: (value) => Number.isFinite(value) && value > 0
  }
)

export const VOICE_CHAT_TRIGGER_PHRASES_SETTING = defineSetting(
  "voiceChatTriggerPhrases",
  [] as string[],
  (value) => coerceStringArray(value, []),
  { area: "local" }
)

export const VOICE_CHAT_AUTO_RESUME_SETTING = defineSetting(
  "voiceChatAutoResume",
  true,
  (value) => coerceBoolean(value, true),
  { area: "local" }
)

export const VOICE_CHAT_BARGE_IN_SETTING = defineSetting(
  "voiceChatBargeIn",
  false,
  (value) => coerceBoolean(value, false),
  { area: "local" }
)

export const VOICE_CHAT_TTS_MODE_SETTING = defineSetting(
  "voiceChatTtsMode",
  "stream" as VoiceChatTtsMode,
  (value) => coerceVoiceChatTtsMode(value, "stream"),
  { area: "local" }
)

export const HEADER_SHORTCUTS_EXPANDED_SETTING = defineSetting(
  "headerShortcutsExpanded",
  false,
  (value) => coerceBoolean(value, false),
  {
    area: "local"
  }
)

const coerceBooleanRecord = (value: unknown): Record<string, boolean> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {}
  const entries = Object.entries(value as Record<string, unknown>)
  if (entries.length === 0) return value as Record<string, boolean>
  const hasInvalid = entries.some(([, entry]) => typeof entry !== "boolean")
  if (!hasInvalid) return value as Record<string, boolean>
  const normalized: Record<string, boolean> = {}
  for (const [key, entry] of entries) {
    if (typeof entry === "boolean") normalized[key] = entry
  }
  return normalized
}

export const SEEN_HINTS_SETTING = defineSetting(
  "tldw:seenHints",
  {} as Record<string, boolean>,
  (value) => coerceBooleanRecord(value),
  {
    area: "local"
  }
)

export const MEDIA_REVIEW_ORIENTATION_SETTING = defineSetting(
  "media-review-orientation",
  "vertical" as "vertical" | "horizontal",
  (value) => {
    const normalized = String(value || "").toLowerCase()
    return normalized === "horizontal" ? "horizontal" : "vertical"
  },
  {
    area: "local"
  }
)

const VIEW_MODE_VALUES = ["spread", "list", "all"] as const
export type ViewModeValue = (typeof VIEW_MODE_VALUES)[number]

export const MEDIA_REVIEW_VIEW_MODE_SETTING = defineSetting(
  "media-review-view-mode",
  "spread" as ViewModeValue,
  (value) => {
    const normalized = String(value || "").toLowerCase()
    return VIEW_MODE_VALUES.includes(normalized as ViewModeValue)
      ? (normalized as ViewModeValue)
      : "spread"
  },
  {
    area: "local"
  }
)

export const MEDIA_REVIEW_FILTERS_COLLAPSED_SETTING = defineSetting(
  "media-review-filters-collapsed",
  true,
  (value) => coerceBoolean(value, false),
  {
    area: "local"
  }
)

export const MEDIA_REVIEW_AUTO_VIEW_MODE_SETTING = defineSetting(
  "media-review-auto-view-mode",
  true,
  (value) => coerceBoolean(value, true),
  {
    area: "local"
  }
)

const coerceIdArray = (value: unknown): Array<string | number> => {
  if (!Array.isArray(value)) return []
  return value.filter(
    (entry) => typeof entry === "string" || typeof entry === "number"
  )
}

export const MEDIA_REVIEW_SELECTION_SETTING = defineSetting(
  "media-review-selection",
  [] as Array<string | number>,
  coerceIdArray,
  {
    area: "local"
  }
)

export const MEDIA_REVIEW_FOCUSED_ID_SETTING = defineSetting(
  "media-review-focused-id",
  null as string | number | null,
  (value) => {
    if (value === null || value === undefined) return null
    if (typeof value === "string" || typeof value === "number") return value
    return null
  },
  {
    area: "local"
  }
)

export type DiscussMediaPrompt = {
  mediaId?: string
  url?: string
  title?: string
  content?: string
}

const coerceDiscussMediaPrompt = (
  value: unknown
): DiscussMediaPrompt | undefined => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined
  const payload = value as Record<string, unknown>
  const result: DiscussMediaPrompt = {}
  if (typeof payload.mediaId === "string" && payload.mediaId.length > 0) {
    result.mediaId = payload.mediaId
  }
  if (typeof payload.url === "string" && payload.url.length > 0) {
    result.url = payload.url
  }
  if (typeof payload.title === "string" && payload.title.length > 0) {
    result.title = payload.title
  }
  if (typeof payload.content === "string" && payload.content.length > 0) {
    result.content = payload.content
  }
  return Object.keys(result).length > 0 ? result : undefined
}

export const DISCUSS_MEDIA_PROMPT_SETTING = defineSetting(
  "tldw:discussMediaPrompt",
  undefined as DiscussMediaPrompt | undefined,
  (value) => coerceDiscussMediaPrompt(value),
  {
    area: "local",
    localStorageKey: "tldw:discussMediaPrompt",
    mirrorToLocalStorage: true
  }
)

export const LAST_MEDIA_ID_SETTING = defineSetting(
  "tldw:lastMediaId",
  undefined as string | undefined,
  coerceOptionalString,
  {
    area: "local",
    localStorageKey: "tldw:lastMediaId",
    mirrorToLocalStorage: true
  }
)

export const LAST_NOTE_ID_SETTING = defineSetting(
  "tldw:lastNoteId",
  undefined as string | undefined,
  coerceOptionalString,
  {
    area: "local",
    localStorageKey: "tldw:lastNoteId",
    mirrorToLocalStorage: true
  }
)

export const LAST_DECK_ID_SETTING = defineSetting(
  "tldw:lastDeckId",
  undefined as string | undefined,
  coerceOptionalString,
  {
    area: "local",
    localStorageKey: "tldw:lastDeckId",
    mirrorToLocalStorage: true
  }
)

export const DEFAULT_MEDIA_COLLAPSED_SECTIONS: Record<string, boolean> = {
  statistics: false,
  content: false,
  metadata: true,
  analysis: false
}

export const MEDIA_COLLAPSED_SECTIONS_SETTING = defineSetting(
  "tldw:media:collapsedSections",
  DEFAULT_MEDIA_COLLAPSED_SECTIONS,
  (value) => coerceBooleanRecord(value),
  {
    area: "local"
  }
)
