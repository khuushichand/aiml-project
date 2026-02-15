import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  initialize: vi.fn(async () => undefined),
  createChatCompletion: vi.fn(),
  streamChatCompletion: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: mocks.initialize,
    createChatCompletion: mocks.createChatCompletion,
    streamChatCompletion: mocks.streamChatCompletion
  }
}))

import {
  TldwChatService,
  getLastChatCompletionDebugSnapshot
} from "@/services/tldw/TldwChat"
import type { ChatMessage } from "@/services/tldw/TldwApiClient"

const makeDefaultResponse = () =>
  new Response(
    JSON.stringify({
      choices: [{ message: { content: "ok" } }]
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" }
    }
  )

describe("TldwChatService message sanitization", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createChatCompletion.mockResolvedValue(makeDefaultResponse())
    mocks.streamChatCompletion.mockImplementation(async function* () {
      yield {
        choices: [{ index: 0, delta: { content: "hello" }, finish_reason: null }]
      }
    })
  })

  it("falls back to system prompt when request messages are empty (send)", async () => {
    const service = new TldwChatService()

    await service.sendMessage([], {
      model: "gpt-test",
      systemPrompt: "  Be concise.  "
    })

    const request = mocks.createChatCompletion.mock.calls[0][0] as {
      messages: ChatMessage[]
    }
    expect(request.messages).toEqual([
      { role: "system", content: "Be concise." }
    ])
  })

  it("fails locally when no usable messages or system prompt exist", async () => {
    const service = new TldwChatService()

    await expect(
      service.sendMessage(
        [{ role: "user", content: "   " }],
        { model: "gpt-test" }
      )
    ).rejects.toMatchObject({
      message: "Chat completion failed",
      cause: expect.objectContaining({
        message: expect.stringContaining("Cannot send chat request without any messages")
      })
    })
    expect(mocks.createChatCompletion).not.toHaveBeenCalled()
  })

  it("falls back to system prompt when request messages are empty (stream)", async () => {
    const service = new TldwChatService()
    const tokens: string[] = []

    for await (const token of service.streamMessage([], {
      model: "gpt-test",
      systemPrompt: "System prompt"
    })) {
      tokens.push(token)
    }

    const request = mocks.streamChatCompletion.mock.calls[0][0] as {
      messages: ChatMessage[]
    }
    expect(request.messages).toEqual([
      { role: "system", content: "System prompt" }
    ])
    expect(tokens).toEqual(["hello"])
  })

  it("preserves image-only user turns while pruning empty text parts", async () => {
    const service = new TldwChatService()
    const messages: ChatMessage[] = [
      {
        role: "user",
        content: [
          { type: "text", text: "   " },
          {
            type: "image_url",
            image_url: {
              url: "https://example.com/image.png"
            }
          }
        ]
      }
    ]

    await service.sendMessage(messages, { model: "gpt-test" })

    const request = mocks.createChatCompletion.mock.calls[0][0] as {
      messages: ChatMessage[]
    }
    expect(request.messages).toEqual([
      {
        role: "user",
        content: [
          {
            type: "image_url",
            image_url: {
              url: "https://example.com/image.png"
            }
          }
        ]
      }
    ])
  })

  it("captures the last non-stream payload for debugging", async () => {
    const service = new TldwChatService()
    await service.sendMessage([{ role: "user", content: "hello there" }], {
      model: "gpt-test"
    })

    const snapshot = getLastChatCompletionDebugSnapshot()
    expect(snapshot).toMatchObject({
      endpoint: "/api/v1/chat/completions",
      mode: "non-stream",
      request: expect.objectContaining({
        model: "gpt-test",
        stream: false
      })
    })
    expect(snapshot?.request.messages).toEqual([
      { role: "user", content: "hello there" }
    ])
  })

  it("captures the last stream payload for debugging", async () => {
    const service = new TldwChatService()
    for await (const _ of service.streamMessage(
      [{ role: "user", content: "stream hello" }],
      { model: "gpt-test" }
    )) {
      break
    }

    const snapshot = getLastChatCompletionDebugSnapshot()
    expect(snapshot).toMatchObject({
      endpoint: "/api/v1/chat/completions",
      mode: "stream",
      request: expect.objectContaining({
        model: "gpt-test",
        stream: true
      })
    })
    expect(snapshot?.request.messages).toEqual([
      { role: "user", content: "stream hello" }
    ])
  })
})
