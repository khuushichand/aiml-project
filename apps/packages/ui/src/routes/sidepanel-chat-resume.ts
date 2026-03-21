import {
  getRecentChatFromCopilot
} from "@/db/dexie/helpers"
import { copilotResumeLastChat } from "@/services/app"
import type { SidepanelChatSnapshot, SidepanelChatTab } from "@/store/sidepanel-chat-tabs"
import { createSafeStorage } from "@/utils/safe-storage"
import type { ChatHistory, Message as ChatMessage } from "~/store/option"

export type LegacySidepanelChatSnapshot = {
  history: ChatHistory
  messages: ChatMessage[]
  chatMode: "normal" | "rag" | "vision"
  historyId: string | null
}

type SidepanelTabsState = {
  tabs: SidepanelChatTab[]
  activeTabId: string | null
  snapshotsById: Record<string, SidepanelChatSnapshot>
}

export const getTabsStorageKey = (id: number | null | undefined) =>
  id != null ? `sidepanelChatTabsState:tab-${id}` : "sidepanelChatTabsState"

export const getLegacyStorageKey = (id: number | null | undefined) =>
  id != null ? `sidepanelChatState:tab-${id}` : "sidepanelChatState"

export const readSidepanelRuntimeTabId = async (): Promise<number | null> => {
  try {
    const runtime = (
      globalThis as typeof globalThis & {
        browser?: {
          runtime?: {
            sendMessage?: (message: { type: string }) => Promise<{ tabId?: unknown }>
          }
        }
      }
    ).browser?.runtime

    if (!runtime?.sendMessage) {
      return null
    }

    const resp = await runtime.sendMessage({
      type: "tldw:get-tab-id"
    })

    return typeof resp?.tabId === "number" ? resp.tabId : null
  } catch {
    return null
  }
}

const hasRestorableSnapshot = (
  snapshot: SidepanelChatSnapshot | undefined,
  tab: SidepanelChatTab | undefined
): boolean => {
  if (tab?.historyId || tab?.serverChatId || tab?.serverChatTopic) {
    return true
  }

  if (!snapshot) {
    return false
  }

  return Boolean(
    snapshot.history.length > 0 ||
      snapshot.messages.length > 0 ||
      snapshot.historyId ||
      snapshot.serverChatId ||
      snapshot.serverChatTopic ||
      snapshot.serverChatClusterId ||
      snapshot.serverChatExternalRef ||
      snapshot.queuedMessages.length > 0
  )
}

export const hasResumableSidepanelChat = async (): Promise<boolean> => {
  try {
    const tabId = await readSidepanelRuntimeTabId()
    const storage = createSafeStorage({
      area: "local"
    })

    const keysToTry: string[] = [getTabsStorageKey(tabId)]
    if (tabId != null) {
      keysToTry.push(getTabsStorageKey(null))
    }

    for (const key of keysToTry) {
      // eslint-disable-next-line no-await-in-loop
      const candidate = (await storage.get(key)) as SidepanelTabsState | null
      if (
        candidate &&
        Array.isArray(candidate.tabs) &&
        candidate.tabs.some((tab) =>
          hasRestorableSnapshot(candidate.snapshotsById?.[tab.id], tab)
        )
      ) {
        return true
      }
    }

    const legacyKeysToTry: string[] = [getLegacyStorageKey(tabId)]
    if (tabId != null) {
      legacyKeysToTry.push(getLegacyStorageKey(null))
    }

    for (const key of legacyKeysToTry) {
      // eslint-disable-next-line no-await-in-loop
      const candidate = (await storage.get(key)) as
        | LegacySidepanelChatSnapshot
        | null
      if (candidate && Array.isArray(candidate.messages)) {
        return true
      }
    }

    const isEnabled = await copilotResumeLastChat()
    if (!isEnabled) return false

    const recentChat = await getRecentChatFromCopilot()
    return Boolean(recentChat)
  } catch {
    return false
  }
}
