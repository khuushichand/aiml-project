import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { createSafeStorage } from "@/utils/safe-storage"
import {
  applyChatSettingsPatch,
  getChatSettingsStorageKey,
  normalizeChatSettingsRecord,
  resolveChatSettingsKey
} from "@/services/chat-settings"
import type { ChatSettingsRecord } from "@/types/chat-session-settings"

const chatSettingsStorage = createSafeStorage()

type UseChatSettingsRecordParams = {
  historyId: string | null
  serverChatId: string | null
}

export const useChatSettingsRecord = ({
  historyId,
  serverChatId
}: UseChatSettingsRecordParams) => {
  const stableHistoryId =
    historyId && historyId !== "temp" ? historyId : null
  const chatKey = React.useMemo(
    () => resolveChatSettingsKey({ historyId: stableHistoryId, serverChatId }),
    [serverChatId, stableHistoryId]
  )
  const storageKey = React.useMemo(
    () => getChatSettingsStorageKey(chatKey),
    [chatKey]
  )

  const [rawSettings, setRawSettings] = useStorage<
    ChatSettingsRecord | null | undefined
  >({
    key: storageKey,
    instance: chatSettingsStorage
  })
  const settings = React.useMemo(
    () => normalizeChatSettingsRecord(rawSettings),
    [rawSettings]
  )

  const updateSettings = React.useCallback(
    async (patch: Partial<ChatSettingsRecord>) => {
      const next = await applyChatSettingsPatch({
        historyId: stableHistoryId,
        serverChatId,
        patch
      })
      if (next) {
        await setRawSettings(next)
      }
      return next
    },
    [serverChatId, setRawSettings, stableHistoryId]
  )

  return { settings, updateSettings, chatKey }
}
