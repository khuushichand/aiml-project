import { describe, expect, it } from "vitest"
import type { Message } from "@/store/option"
import type { ServerChatMessage } from "@/services/tldw/TldwApiClient"
import {
  fetchAllServerChatMessages,
  mapServerChatMessagesToPlaygroundMessages,
  shouldPreserveLocalMessagesForServerLoad
} from "@/hooks/chat/useServerChatLoader"
import {
  buildImageGenerationEventMirrorContent,
  IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
} from "@/utils/image-generation-chat"

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

  it("does not preserve when the only unsynced local content is a synthetic character greeting", () => {
    const currentMessages = [
      createMessage({
        isBot: true,
        role: "assistant",
        message: "Greetings, traveler.",
        messageType: "character:greeting",
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
    ).toBe(false)
  })
})

const createServerMessage = (
  overrides: Partial<ServerChatMessage> = {}
): ServerChatMessage => ({
  id: "msg-1",
  role: "assistant",
  content: "hello",
  created_at: "2026-02-20T00:00:00.000Z",
  ...overrides
})

describe("fetchAllServerChatMessages", () => {
  it("fetches all pages so later-page greeting messages are included", async () => {
    const greeting = createServerMessage({
      id: "msg-2",
      role: "assistant",
      content: "Greetings, traveler.",
      created_at: "2026-02-20T00:00:02.000Z",
      metadata_extra: { message_type: "character:greeting" }
    })
    const userMessage = createServerMessage({
      id: "msg-1",
      role: "user",
      content: "Hello there",
      created_at: "2026-02-20T00:00:01.000Z"
    })
    const assistantReply = createServerMessage({
      id: "msg-3",
      role: "assistant",
      content: "How can I help?",
      created_at: "2026-02-20T00:00:03.000Z"
    })

    const pages = new Map<number, ServerChatMessage[]>([
      [0, [userMessage]],
      [1, [greeting, assistantReply]],
      [3, []]
    ])

    const messages = await fetchAllServerChatMessages(
      async ({ limit, offset }) => {
        expect(limit).toBe(1)
        return pages.get(offset) ?? []
      },
      {
        limit: 1,
        maxPages: 10
      }
    )

    expect(messages.map((message) => message.id)).toEqual([
      "msg-1",
      "msg-2",
      "msg-3"
    ])
    expect(messages.some((message) => message.content.includes("Greetings"))).toBe(
      true
    )
  })

  it("deduplicates repeated message ids across paginated responses", async () => {
    const first = createServerMessage({ id: "msg-1" })
    const second = createServerMessage({ id: "msg-2" })
    const duplicateSecond = createServerMessage({ id: "msg-2" })
    const third = createServerMessage({ id: "msg-3" })

    const pages = new Map<number, ServerChatMessage[]>([
      [0, [first, second]],
      [2, [duplicateSecond, third]],
      [4, []]
    ])

    const messages = await fetchAllServerChatMessages(
      async ({ limit, offset }) => {
        expect(limit).toBe(2)
        return pages.get(offset) ?? []
      },
      {
        limit: 2,
        maxPages: 10
      }
    )

    expect(messages.map((message) => message.id)).toEqual([
      "msg-1",
      "msg-2",
      "msg-3"
    ])
  })
})

describe("mapServerChatMessagesToPlaygroundMessages", () => {
  it("maps mirrored image event messages into assistant image event cards", () => {
    const mirroredContent = buildImageGenerationEventMirrorContent({
      kind: "image_generation_event",
      version: 1,
      eventId: "evt-1",
      request: {
        prompt: "portrait of Lana, cinematic lighting",
        backend: "flux-test-backend",
        width: 768,
        height: 1024
      },
      source: "generate-modal",
      imageDataUrl: "data:image/png;base64,abc123"
    })
    const mapped = mapServerChatMessagesToPlaygroundMessages({
      serverMessages: [
        createServerMessage({
          id: "srv-img-1",
          role: "assistant",
          content: mirroredContent,
          created_at: "2026-02-20T00:00:02.000Z"
        })
      ],
      assistantName: "Lana",
      characterId: 42
    })

    expect(mapped).toHaveLength(1)
    expect(mapped[0].messageType).toBe(IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE)
    expect(mapped[0].message).toBe("")
    expect(mapped[0].images).toEqual(["data:image/png;base64,abc123"])
    expect(mapped[0].generationInfo?.image_generation?.request?.backend).toBe(
      "flux-test-backend"
    )
    expect(mapped[0].generationInfo?.image_generation?.sync?.status).toBe("synced")
  })
})
