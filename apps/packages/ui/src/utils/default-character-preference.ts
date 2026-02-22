import type { Character } from "@/types/character"
import { createSafeStorage } from "@/utils/safe-storage"

export const DEFAULT_CHARACTER_STORAGE_KEY = "defaultCharacterSelection"
export const DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY =
  "preferences.chat.default_character_id"

export const defaultCharacterStorage = createSafeStorage({ area: "local" })

export const normalizeDefaultCharacterPreferenceId = (
  value: unknown
): string | null => {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value)
  }
  return null
}

export const extractDefaultCharacterPreferenceId = (payload: unknown): string | null => {
  if (!payload || typeof payload !== "object") return null
  const preferences = (payload as { preferences?: unknown }).preferences
  if (!preferences || typeof preferences !== "object" || Array.isArray(preferences)) {
    return null
  }

  const rawPreference = (preferences as Record<string, unknown>)[
    DEFAULT_CHARACTER_PROFILE_PREFERENCE_KEY
  ]
  if (
    rawPreference &&
    typeof rawPreference === "object" &&
    !Array.isArray(rawPreference) &&
    "value" in rawPreference
  ) {
    return normalizeDefaultCharacterPreferenceId(
      (rawPreference as { value?: unknown }).value
    )
  }
  return normalizeDefaultCharacterPreferenceId(rawPreference)
}

export const resolveCharacterSelectionId = (
  value: Pick<Character, "id"> | null | undefined
): string | null => {
  if (!value) return null
  const id = value.id
  if (typeof id === "string") {
    const trimmed = id.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (typeof id === "number" && Number.isFinite(id)) {
    return String(id)
  }
  return null
}

export const isFreshChatState = (
  serverChatId: string | null | undefined,
  messageCount: number
): boolean => {
  const hasServerChat =
    typeof serverChatId === "string" ? serverChatId.trim().length > 0 : Boolean(serverChatId)
  return !hasServerChat && messageCount === 0
}

type ShouldApplyDefaultCharacterParams = {
  defaultCharacterId: string | null
  selectedCharacterId: string | null
  isFreshChat: boolean
  hasAppliedInSession: boolean
}

export const shouldApplyDefaultCharacter = ({
  defaultCharacterId,
  selectedCharacterId,
  isFreshChat,
  hasAppliedInSession
}: ShouldApplyDefaultCharacterParams): boolean =>
  Boolean(
    defaultCharacterId &&
      !selectedCharacterId &&
      isFreshChat &&
      !hasAppliedInSession
  )

export const shouldResetDefaultCharacterBootstrap = (
  previousIsFreshChat: boolean,
  nextIsFreshChat: boolean
): boolean => !previousIsFreshChat && nextIsFreshChat
