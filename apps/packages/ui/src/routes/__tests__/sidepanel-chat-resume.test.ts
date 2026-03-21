import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  storageGet: vi.fn<(key: string) => Promise<unknown>>(),
  copilotResumeLastChat: vi.fn<() => Promise<boolean>>(),
  getRecentChatFromCopilot: vi.fn<() => Promise<unknown>>(),
  sendMessage: vi.fn<(message: { type: string }) => Promise<{ tabId?: unknown }>>()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (key: string) => mocks.storageGet(key)
  })
}))

vi.mock("@/services/app", () => ({
  copilotResumeLastChat: () => mocks.copilotResumeLastChat()
}))

vi.mock("@/db/dexie/helpers", () => ({
  getRecentChatFromCopilot: () => mocks.getRecentChatFromCopilot()
}))

import { hasResumableSidepanelChat } from "../sidepanel-chat-resume"

describe("hasResumableSidepanelChat", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.copilotResumeLastChat.mockResolvedValue(false)
    mocks.getRecentChatFromCopilot.mockResolvedValue(null)
    mocks.sendMessage.mockResolvedValue({ tabId: 7 })
    Object.assign(globalThis, {
      browser: {
        runtime: {
          sendMessage: mocks.sendMessage
        }
      }
    })
  })

  it("treats a stored tabs snapshot with real chat state as resumable", async () => {
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "sidepanelChatTabsState:tab-7") {
        return {
          tabs: [{ id: "tab-1" }],
          activeTabId: "tab-1",
          snapshotsById: {
            "tab-1": {
              history: [
                {
                  role: "user",
                  content: "hello"
                }
              ],
              messages: [],
              chatMode: "normal",
              historyId: null,
              webSearch: false,
              toolChoice: "none",
              selectedModel: null,
              selectedSystemPrompt: null,
              selectedQuickPrompt: null,
              temporaryChat: false,
              useOCR: false,
              serverChatId: null,
              serverChatState: null,
              serverChatTopic: null,
              serverChatClusterId: null,
              serverChatSource: null,
              serverChatExternalRef: null,
              queuedMessages: [],
              modelSettings: {}
            }
          }
        }
      }
      return null
    })

    await expect(hasResumableSidepanelChat()).resolves.toBe(true)
  })

  it("does not treat a blank persisted tab scaffold as resumable", async () => {
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "sidepanelChatTabsState:tab-7") {
        return {
          tabs: [{ id: "tab-1" }],
          activeTabId: "tab-1",
          snapshotsById: {
            "tab-1": {
              history: [],
              messages: [],
              chatMode: "normal",
              historyId: null,
              webSearch: false,
              toolChoice: "none",
              selectedModel: null,
              selectedSystemPrompt: null,
              selectedQuickPrompt: null,
              temporaryChat: false,
              useOCR: false,
              serverChatId: null,
              serverChatState: null,
              serverChatTopic: null,
              serverChatClusterId: null,
              serverChatSource: null,
              serverChatExternalRef: null,
              queuedMessages: [],
              modelSettings: {}
            }
          }
        }
      }
      return null
    })

    await expect(hasResumableSidepanelChat()).resolves.toBe(false)
  })

  it("treats a legacy snapshot with an empty messages array as resumable", async () => {
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "sidepanelChatState:tab-7") {
        return {
          history: [],
          messages: [],
          chatMode: "normal",
          historyId: null
        }
      }
      return null
    })

    await expect(hasResumableSidepanelChat()).resolves.toBe(true)
  })

  it("returns false when there is no stored state and copilot resume is disabled", async () => {
    mocks.storageGet.mockResolvedValue(null)

    await expect(hasResumableSidepanelChat()).resolves.toBe(false)
  })
})
