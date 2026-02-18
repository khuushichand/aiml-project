import type { Character } from "@/types/character"
import { createSafeStorage } from "@/utils/safe-storage"

export const DEFAULT_CHARACTER_STORAGE_KEY = "defaultCharacterSelection"

export const defaultCharacterStorage = createSafeStorage({ area: "local" })

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
