import { browser } from "./wxt-browser"
import { createSafeStorage } from "@/utils/safe-storage"
import type { TldwConfig } from "@/services/tldw/TldwApiClient"
import { FEATURE_FLAGS } from "@/hooks/useFeatureFlags"
import {
  DEFAULT_HEADER_SHORTCUT_SELECTION,
  DEFAULT_SIDEBAR_SHORTCUT_SELECTION,
  HEADER_SHORTCUTS_EXPANDED_SETTING,
  HEADER_SHORTCUT_SELECTION_SETTING,
  SIDEBAR_ACTIVE_TAB_SETTING,
  SIDEBAR_SHORTCUTS_COLLAPSED_SETTING,
  SIDEBAR_SHORTCUT_SELECTION_SETTING,
  THEME_SETTING,
  UI_MODE_SETTING
} from "@/services/settings/ui-settings"

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

const mergeMissingProperties = (
  target: Record<string, unknown>,
  source: Record<string, unknown>
) => {
  Object.entries(source).forEach(([key, sourceValue]) => {
    const targetValue = target[key]

    if (targetValue === undefined || targetValue === null) {
      try {
        target[key] = sourceValue
      } catch {
        // Ignore write failures on non-configurable host objects.
      }
      return
    }

    if (isRecord(targetValue) && isRecord(sourceValue)) {
      mergeMissingProperties(targetValue, sourceValue)
    }
  })
}

if (typeof globalThis !== "undefined") {
  const globalScope = globalThis as typeof globalThis & {
    browser?: typeof browser
    chrome?: typeof browser | Record<string, unknown>
  }

  if (!isRecord(globalScope.browser)) {
    globalScope.browser = browser
  } else {
    mergeMissingProperties(
      globalScope.browser as unknown as Record<string, unknown>,
      browser as unknown as Record<string, unknown>
    )
  }

  if (!isRecord(globalScope.chrome)) {
    globalScope.chrome = browser as unknown as Record<string, unknown>
  } else {
    mergeMissingProperties(
      globalScope.chrome as Record<string, unknown>,
      browser as unknown as Record<string, unknown>
    )
  }
}

const normalizeBaseUrl = (value?: string | null): string | null => {
  const raw = (value || "").trim()
  if (!raw) return null
  return raw.replace(/\/$/, "")
}

const seedTldwConfigFromEnv = async (): Promise<void> => {
  if (typeof window === "undefined") return

  const serverUrl = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_URL)
  const apiKey = (process.env.NEXT_PUBLIC_X_API_KEY || "").trim() || null
  const apiBearer = (process.env.NEXT_PUBLIC_API_BEARER || "").trim() || null

  if (!serverUrl && !apiKey && !apiBearer) return

  try {
    const storage = createSafeStorage()
    const existing = (await storage.get<TldwConfig>("tldwConfig").catch(() => null)) || null

    const next: TldwConfig = {
      ...(existing || {}),
      authMode: existing?.authMode || "single-user",
      serverUrl: existing?.serverUrl || ""
    }

    let changed = false

    if (!next.serverUrl && serverUrl) {
      next.serverUrl = serverUrl
      changed = true
    }

    if (!next.apiKey && !next.accessToken) {
      if (apiKey) {
        next.authMode = "single-user"
        next.apiKey = apiKey
        changed = true
      } else if (apiBearer) {
        next.authMode = "multi-user"
        next.accessToken = apiBearer
        changed = true
      }
    }

    if (changed) {
      await storage.set("tldwConfig", next)
      if (next.serverUrl) {
        await storage.set("tldwServerUrl", next.serverUrl)
      }
    }
  } catch {
    // Best-effort only; ignore storage failures in web contexts.
  }
}

void seedTldwConfigFromEnv()

const WEB_DEFAULTS_MIRRORED_KEY = "tldw:web-defaults:mirrored"
const WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY =
  "tldw:web-defaults:header-shortcuts-document-workspace:v1"

const isWebRuntime = () => {
  if (typeof window === "undefined") return false
  const protocol = window.location.protocol
  return protocol !== "chrome-extension:" && protocol !== "moz-extension:"
}

const writeLocalStorageValue = (key: string, value: unknown) => {
  if (typeof window === "undefined") return
  try {
    const serialized =
      typeof value === "string" ? value : JSON.stringify(value)
    window.localStorage.setItem(key, serialized)
  } catch {
    // ignore storage failures
  }
}

const removeLocalStorageValue = (key: string) => {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(key)
  } catch {
    // ignore storage failures
  }
}

const getLocalStorageValue = (key: string) => {
  if (typeof window === "undefined") return null
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

const setDefault = (key: string, value: unknown, force = false) => {
  const existing = getLocalStorageValue(key)
  if (!force && existing !== null) return
  writeLocalStorageValue(key, value)
}

const mirrorWebDefaultsFromExtension = () => {
  if (!isWebRuntime()) return
  const shouldMirrorDefaults =
    getLocalStorageValue(WEB_DEFAULTS_MIRRORED_KEY) !== "true"

  const legacyTheme = getLocalStorageValue("tldw-theme")
  if (getLocalStorageValue(THEME_SETTING.key) === null && legacyTheme) {
    writeLocalStorageValue(THEME_SETTING.key, legacyTheme)
  }
  if (legacyTheme !== null) {
    removeLocalStorageValue("tldw-theme")
  }

  if (!shouldMirrorDefaults) return

  // Theme + UI mode defaults
  setDefault(THEME_SETTING.key, THEME_SETTING.defaultValue)
  setDefault(UI_MODE_SETTING.key, UI_MODE_SETTING.defaultValue)
  setDefault("tldw-ui-mode", "casual")

  // Feature flags (default true, compare mode default false)
  Object.values(FEATURE_FLAGS).forEach((flag) => {
    const isCompareMode = flag === FEATURE_FLAGS.COMPARE_MODE
    setDefault(flag, isCompareMode ? false : true)
  })

  // Sidebar + header shortcuts defaults
  setDefault(
    SIDEBAR_ACTIVE_TAB_SETTING.key,
    SIDEBAR_ACTIVE_TAB_SETTING.defaultValue
  )
  setDefault(
    SIDEBAR_SHORTCUTS_COLLAPSED_SETTING.key,
    SIDEBAR_SHORTCUTS_COLLAPSED_SETTING.defaultValue
  )
  setDefault(
    SIDEBAR_SHORTCUT_SELECTION_SETTING.key,
    DEFAULT_SIDEBAR_SHORTCUT_SELECTION
  )
  setDefault(
    HEADER_SHORTCUT_SELECTION_SETTING.key,
    DEFAULT_HEADER_SHORTCUT_SELECTION
  )
  setDefault(
    HEADER_SHORTCUTS_EXPANDED_SETTING.key,
    HEADER_SHORTCUTS_EXPANDED_SETTING.defaultValue
  )

  writeLocalStorageValue(WEB_DEFAULTS_MIRRORED_KEY, "true")
}

const backfillDocumentWorkspaceHeaderShortcutForWeb = () => {
  if (!isWebRuntime()) return
  if (getLocalStorageValue(WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY) === "true") {
    return
  }

  const rawSelection = getLocalStorageValue(HEADER_SHORTCUT_SELECTION_SETTING.key)
  if (rawSelection === null) {
    writeLocalStorageValue(WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY, "true")
    return
  }

  let parsedSelection: unknown = null
  try {
    parsedSelection = JSON.parse(rawSelection)
  } catch {
    writeLocalStorageValue(WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY, "true")
    return
  }

  if (!Array.isArray(parsedSelection)) {
    writeLocalStorageValue(WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY, "true")
    return
  }

  const selectedIds = new Set(
    parsedSelection.filter(
      (entry): entry is string => typeof entry === "string"
    )
  )
  selectedIds.add("document-workspace")

  const nextSelection = DEFAULT_HEADER_SHORTCUT_SELECTION.filter((id) =>
    selectedIds.has(id)
  )
  writeLocalStorageValue(HEADER_SHORTCUT_SELECTION_SETTING.key, nextSelection)
  writeLocalStorageValue(WEB_HEADER_SHORTCUT_DOC_WORKSPACE_BACKFILL_KEY, "true")
}

mirrorWebDefaultsFromExtension()
backfillDocumentWorkspaceHeaderShortcutForWeb()
