import { describe, expect, it, vi } from "vitest"
import type { ChatHistory, Message } from "@/store/option"

const mockTldwClient = vi.hoisted(() => ({
  initialize: vi.fn(),
  getChat: vi.fn(),
  createChat: vi.fn(),
  addChatMessage: vi.fn()
}))

vi.mock("@/db/dexie/helpers", () => ({
  deleteChatForEdit: vi.fn(),
  formatToChatHistory: vi.fn((messages: unknown) => messages),
  formatToMessage: vi.fn((messages: unknown) => messages),
  saveHistory: vi.fn(),
  saveMessage: vi.fn(),
  updateMessageByIndex: vi.fn()
}))

vi.mock("@/db/dexie/branch", () => ({
  generateBranchMessage: vi.fn()
}))

vi.mock("@/db", () => ({
  getPromptById: vi.fn(),
  getSessionFiles: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: mockTldwClient
}))

vi.mock("@/utils/conversation-state", () => ({
  normalizeConversationState: (value?: string | null) => {
    if (value === "resolved" || value === "backlog" || value === "non-viable") {
      return value
    }
    return "in-progress"
  }
}))

import { createBranchMessage } from "../messageHandlers"

describe("createBranchMessage", () => {
  it("prefers the parent server chat character_id when local characterId is stale", async () => {
    mockTldwClient.initialize.mockResolvedValue(undefined)
    mockTldwClient.getChat.mockResolvedValue({
      id: "parent-chat-id",
      title: "Parent Chat",
      character_id: 2,
      state: "in-progress"
    })
    mockTldwClient.createChat.mockImplementation(async (payload: any) => {
      if (payload.character_id !== 2) {
        throw new Error(`unexpected character_id: ${String(payload.character_id)}`)
      }
      return {
        id: "new-branch-chat-id",
        character_id: 2,
        state: "in-progress",
        title: payload.title
      }
    })
    mockTldwClient.addChatMessage.mockResolvedValue({
      id: "msg-1"
    })

    const notification = {
      error: vi.fn(),
      warning: vi.fn()
    } as any

    const setMessages = vi.fn()
    const setHistory = vi.fn()
    const setHistoryId = vi.fn()
    const setServerChatId = vi.fn()
    const setServerChatState = vi.fn()
    const setServerChatVersion = vi.fn()
    const setServerChatTitle = vi.fn()
    const setServerChatCharacterId = vi.fn()
    const setServerChatMetaLoaded = vi.fn()
    const setServerChatTopic = vi.fn()
    const setServerChatClusterId = vi.fn()
    const setServerChatSource = vi.fn()
    const setServerChatExternalRef = vi.fn()

    const messages = [
      {
        isBot: false,
        name: "You",
        message: "hello",
        sources: []
      }
    ] as Message[]

    const history = [
      {
        role: "user",
        content: "hello"
      }
    ] as ChatHistory

    const branchMessage = createBranchMessage({
      notification,
      setMessages,
      setHistory,
      historyId: "local-history-id",
      setHistoryId,
      serverChatId: "parent-chat-id",
      setServerChatId,
      setServerChatState,
      setServerChatVersion,
      setServerChatTitle,
      setServerChatCharacterId,
      setServerChatMetaLoaded,
      setServerChatTopic,
      setServerChatClusterId,
      setServerChatSource,
      setServerChatExternalRef,
      characterId: "stale-local-character-id",
      chatTitle: "local title",
      serverChatState: "in-progress",
      messages,
      history,
      serverOnly: true
    })

    const result = await branchMessage(0)

    expect(result).toBe("new-branch-chat-id")
    expect(mockTldwClient.getChat).toHaveBeenCalledWith("parent-chat-id")
    expect(mockTldwClient.createChat).toHaveBeenCalledWith(
      expect.objectContaining({
        parent_conversation_id: "parent-chat-id",
        character_id: 2,
        state: "in-progress"
      })
    )
    expect(notification.error).not.toHaveBeenCalled()
  })
})
