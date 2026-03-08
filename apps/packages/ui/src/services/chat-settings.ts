import { createSafeStorage } from "@/utils/safe-storage"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  CHAT_SETTINGS_SCHEMA_VERSION,
  ChatSettingsRecord,
  CharacterMemoryEntry
} from "@/types/chat-session-settings"

const storage = createSafeStorage()

export const getChatSettingsStorageKey = (chatKey: string) =>
  `chatSettings:${chatKey}`

export const resolveChatSettingsKey = (params: {
  historyId: string | null
  serverChatId: string | null
}): string => {
  const { historyId, serverChatId } = params
  if (serverChatId) return `server:${serverChatId}`
  if (historyId) return `local:${historyId}`
  return "scratch"
}

const coerceSettings = (raw: any): ChatSettingsRecord | null => {
  if (!raw || typeof raw !== "object") return null
  const schemaVersion =
    typeof raw.schemaVersion === "number"
      ? raw.schemaVersion
      : CHAT_SETTINGS_SCHEMA_VERSION
  const updatedAt =
    typeof raw.updatedAt === "string"
      ? raw.updatedAt
      : new Date().toISOString()
  return {
    ...raw,
    schemaVersion,
    updatedAt
  } as ChatSettingsRecord
}

export const normalizeChatSettingsRecord = (
  raw: any
): ChatSettingsRecord | null => coerceSettings(raw)

const toEpoch = (value: string | undefined): number => {
  if (!value) return 0
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

const normalizeComparableChatSettingsValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeComparableChatSettingsValue(entry))
  }
  if (!value || typeof value !== "object") {
    return value
  }

  const normalizedEntries = Object.entries(value as Record<string, unknown>)
    .filter(([key, entryValue]) => key !== "updatedAt" && entryValue !== undefined)
    .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
    .map(([key, entryValue]) => [
      key,
      normalizeComparableChatSettingsValue(entryValue)
    ])

  return Object.fromEntries(normalizedEntries)
}

export const areEquivalentChatSettings = (
  left: ChatSettingsRecord | null,
  right: ChatSettingsRecord | null
): boolean => {
  if (!left || !right) return left === right
  return (
    JSON.stringify(normalizeComparableChatSettingsValue(left)) ===
    JSON.stringify(normalizeComparableChatSettingsValue(right))
  )
}

const mergeEntry = (
  left: CharacterMemoryEntry | undefined,
  right: CharacterMemoryEntry | undefined
): CharacterMemoryEntry | undefined => {
  if (!left) return right
  if (!right) return left
  const leftTime = toEpoch(left.updatedAt)
  const rightTime = toEpoch(right.updatedAt)
  return rightTime >= leftTime ? right : left
}

export const mergeChatSettings = (
  local: ChatSettingsRecord | null,
  remote: ChatSettingsRecord | null
): ChatSettingsRecord | null => {
  if (!local) return remote
  if (!remote) return local

  const localTime = toEpoch(local.updatedAt)
  const remoteTime = toEpoch(remote.updatedAt)
  const base = localTime >= remoteTime ? local : remote
  const other = base === local ? remote : local

  const merged: ChatSettingsRecord = {
    ...other,
    ...base,
    updatedAt: base.updatedAt
  }

  const baseMemory = base.characterMemoryById
  const otherMemory = other.characterMemoryById
  if (baseMemory || otherMemory) {
    const mergedMap: Record<string, CharacterMemoryEntry> = {}
    const keys = new Set([
      ...Object.keys(baseMemory || {}),
      ...Object.keys(otherMemory || {})
    ])
    for (const key of keys) {
      mergedMap[key] = mergeEntry(otherMemory?.[key], baseMemory?.[key]) || {
        note: "",
        updatedAt: base.updatedAt
      }
    }
    merged.characterMemoryById = mergedMap
  }

  return merged
}

export const getChatSettingsForKey = async (
  chatKey: string
): Promise<ChatSettingsRecord | null> => {
  try {
    const key = getChatSettingsStorageKey(chatKey)
    const stored = await storage.get<ChatSettingsRecord | undefined>(key)
    return coerceSettings(stored)
  } catch (error) {
    console.error("Failed to load chat settings", error)
    return null
  }
}

export const saveChatSettingsForKey = async (
  chatKey: string,
  settings: ChatSettingsRecord
): Promise<boolean> => {
  try {
    const key = getChatSettingsStorageKey(chatKey)
    const payload: ChatSettingsRecord = {
      ...settings,
      schemaVersion: CHAT_SETTINGS_SCHEMA_VERSION,
      updatedAt: settings.updatedAt || new Date().toISOString()
    }
    await storage.set(key, payload)
    return true
  } catch (error) {
    console.error("Failed to save chat settings", error)
    return false
  }
}

export const getChatSettingsForChat = async (params: {
  historyId: string | null
  serverChatId: string | null
}): Promise<ChatSettingsRecord | null> => {
  const chatKey = resolveChatSettingsKey(params)
  return await getChatSettingsForKey(chatKey)
}

export const saveChatSettingsForChat = async (params: {
  historyId: string | null
  serverChatId: string | null
  settings: ChatSettingsRecord
}): Promise<boolean> => {
  const chatKey = resolveChatSettingsKey(params)
  return await saveChatSettingsForKey(chatKey, params.settings)
}

export const syncChatSettingsForServerChat = async (params: {
  historyId: string | null
  serverChatId: string | null
}): Promise<ChatSettingsRecord | null> => {
  const { historyId, serverChatId } = params
  if (!serverChatId) return null

  const serverKey = resolveChatSettingsKey({ historyId: null, serverChatId })
  const localKey = resolveChatSettingsKey({ historyId, serverChatId: null })

  const localForServer = await getChatSettingsForKey(serverKey)
  const localFromHistory = historyId ? await getChatSettingsForKey(localKey) : null
  const localSettings = localForServer || localFromHistory

  await tldwClient.initialize().catch(() => null)

  let remoteSettings: ChatSettingsRecord | null = null
  try {
    const res = await tldwClient.getChatSettings(serverChatId)
    remoteSettings = coerceSettings(res.settings)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error || "")
    if (!message.includes("404")) {
      console.warn("Failed to fetch server chat settings", error)
    }
  }

  if (!remoteSettings && localSettings) {
    try {
      const res = await tldwClient.updateChatSettings(serverChatId, localSettings)
      const synced = coerceSettings(res.settings) || localSettings
      await saveChatSettingsForKey(serverKey, synced)
      return synced
    } catch (error) {
      console.warn("Failed to push local chat settings", error)
      return localSettings
    }
  }

  if (remoteSettings && !localSettings) {
    await saveChatSettingsForKey(serverKey, remoteSettings)
    return remoteSettings
  }

  const merged = mergeChatSettings(localSettings, remoteSettings)
  if (!merged) return null

  if (remoteSettings && areEquivalentChatSettings(merged, remoteSettings)) {
    await saveChatSettingsForKey(serverKey, merged)
    return merged
  }

  const mergedTime = toEpoch(merged.updatedAt)
  const remoteTime = toEpoch(remoteSettings?.updatedAt)

  if (mergedTime >= remoteTime) {
    try {
      await tldwClient.updateChatSettings(serverChatId, merged)
    } catch (error) {
      console.warn("Failed to reconcile chat settings to server", error)
    }
  }

  await saveChatSettingsForKey(serverKey, merged)
  return merged
}

export const applyChatSettingsPatch = async (params: {
  historyId: string | null
  serverChatId: string | null
  patch: Partial<ChatSettingsRecord>
}): Promise<ChatSettingsRecord | null> => {
  const { historyId, serverChatId, patch } = params
  const chatKey = resolveChatSettingsKey({ historyId, serverChatId })
  const existing = await getChatSettingsForKey(chatKey)
  const next: ChatSettingsRecord = {
    ...(existing || {
      schemaVersion: CHAT_SETTINGS_SCHEMA_VERSION,
      updatedAt: new Date().toISOString()
    }),
    ...patch,
    schemaVersion: CHAT_SETTINGS_SCHEMA_VERSION,
    updatedAt: new Date().toISOString()
  }

  await saveChatSettingsForKey(chatKey, next)

  if (!serverChatId) {
    return next
  }

  await tldwClient.initialize().catch(() => null)
  try {
    const res = await tldwClient.updateChatSettings(serverChatId, next)
    const synced = normalizeChatSettingsRecord(res.settings) || next
    const serverKey = resolveChatSettingsKey({ historyId: null, serverChatId })
    await saveChatSettingsForKey(serverKey, synced)
    return synced
  } catch (error) {
    console.warn("Failed to update server chat settings", error)
    return next
  }
}
