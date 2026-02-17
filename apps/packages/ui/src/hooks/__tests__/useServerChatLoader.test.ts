import { describe, expect, it } from "vitest"
import type { Message } from "@/store/option"
import { shouldPreserveLocalMessagesForServerLoad } from "@/hooks/chat/useServerChatLoader"

const createMessage = (overrides: Partial<Message> = {}): Message => ({
  isBot: false,
  name: "You",
  role: "user",
  message: "hello",
  sources: [],
  ...overrides
})

describe("shouldPreserveLocalMessagesForServerLoad", () => {
  it("preserves local messages while streaming", () => {
    const currentMessages = [createMessage({ message: "draft response" })]
    expect(
      shouldPreserveLocalMessagesForServerLoad({
        currentMessages,
        serverMessages: [],
        isStreaming: true,
        isProcessing: false
      })
    ).toBe(true)
  })

  it("preserves local messages when unsynced content exists", () => {
    const currentMessages = [
      createMessage({
        isBot: true,
        role: "assistant",
        message: "fresh assistant reply",
        serverMessageId: undefined
      })
    ]
    expect(
      shouldPreserveLocalMessagesForServerLoad({
        currentMessages,
        serverMessages: [],
        isStreaming: false,
        isProcessing: false
      })
    ).toBe(true)
  })

  it("preserves local messages when persisted IDs are missing in server snapshot", () => {
    const currentMessages = [
      createMessage({
        isBot: true,
        role: "assistant",
        message: "new persisted reply",
        serverMessageId: "srv-2"
      })
    ]
    const serverMessages = [
      createMessage({
        serverMessageId: "srv-1",
        id: "srv-1"
      })
    ]
    expect(
      shouldPreserveLocalMessagesForServerLoad({
        currentMessages,
        serverMessages,
        isStreaming: false,
        isProcessing: false
      })
    ).toBe(true)
  })

  it("does not preserve when local messages are fully reflected in server snapshot", () => {
    const currentMessages = [
      createMessage({
        isBot: true,
        role: "assistant",
        message: "synced reply",
        serverMessageId: "srv-1"
      })
    ]
    const serverMessages = [
      createMessage({
        isBot: true,
        role: "assistant",
        message: "synced reply",
        serverMessageId: "srv-1",
        id: "srv-1"
      })
    ]
    expect(
      shouldPreserveLocalMessagesForServerLoad({
        currentMessages,
        serverMessages,
        isStreaming: false,
        isProcessing: false
      })
    ).toBe(false)
  })
})
