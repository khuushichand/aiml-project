import { describe, expect, it } from "vitest"
import { renderHook } from "@testing-library/react"
import { useComposerTokens } from "@/hooks/playground/useComposerTokens"
import { IMAGE_GENERATION_USER_MESSAGE_TYPE } from "@/utils/image-generation-chat"

describe("useComposerTokens image-generation filtering", () => {
  it("does not include image-generation messages in conversation token totals", () => {
    const baseMessages = [
      { isBot: false, message: "Hello there" },
      { isBot: true, message: "Hi! How can I help?" }
    ]
    const withImageMessage = [
      ...baseMessages,
      {
        isBot: false,
        message: "Generate an image prompt that should not count",
        messageType: IMAGE_GENERATION_USER_MESSAGE_TYPE
      }
    ]

    const { result: baseResult } = renderHook(() =>
      useComposerTokens({
        message: "",
        messages: baseMessages,
        systemPrompt: "",
        resolvedMaxContext: 4096,
        apiModelLabel: "gpt-4o-mini",
        isSending: false
      })
    )

    const { result: withImageResult } = renderHook(() =>
      useComposerTokens({
        message: "",
        messages: withImageMessage,
        systemPrompt: "",
        resolvedMaxContext: 4096,
        apiModelLabel: "gpt-4o-mini",
        isSending: false
      })
    )

    expect(withImageResult.current.conversationTokenCount).toBe(
      baseResult.current.conversationTokenCount
    )
  })
})

