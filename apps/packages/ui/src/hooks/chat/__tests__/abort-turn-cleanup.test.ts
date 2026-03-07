import { describe, expect, it, vi } from "vitest"

import type { ChatHistory, Message } from "@/store/option"
import { discardAbortedTurnIfRequested } from "../abort-turn-cleanup"

const createAbortError = () => {
  const error = new Error("AbortError")
  error.name = "AbortError"
  return error
}

describe("discardAbortedTurnIfRequested", () => {
  it("restores the previous transcript snapshots when discard is requested for an abort", () => {
    const previousMessages: Message[] = [
      {
        id: "user-1",
        isBot: false,
        name: "You",
        message: "Existing turn",
        sources: []
      }
    ]
    const previousHistory: ChatHistory = [
      {
        role: "user",
        content: "Existing turn"
      }
    ]
    const setMessages = vi.fn()
    const setHistory = vi.fn()

    const handled = discardAbortedTurnIfRequested({
      discardRequested: true,
      error: createAbortError(),
      previousMessages,
      previousHistory,
      setMessages,
      setHistory
    })

    expect(handled).toBe(true)
    expect(setMessages).toHaveBeenCalledWith(previousMessages)
    expect(setHistory).toHaveBeenCalledWith(previousHistory)
  })

  it("does not restore snapshots when discard was not requested", () => {
    const setMessages = vi.fn()
    const setHistory = vi.fn()

    const handled = discardAbortedTurnIfRequested({
      discardRequested: false,
      error: createAbortError(),
      previousMessages: [],
      previousHistory: [],
      setMessages,
      setHistory
    })

    expect(handled).toBe(false)
    expect(setMessages).not.toHaveBeenCalled()
    expect(setHistory).not.toHaveBeenCalled()
  })
})
