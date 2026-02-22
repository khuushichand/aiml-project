import { describe, expect, it, vi } from "vitest"

import {
  fetchAllServerChatPages,
  filterServerChatHistoryItems,
  isRecoverableServerChatHistoryError,
  mapServerChatHistoryItems
} from "@/hooks/useServerChatHistory"
import type { ServerChatSummary } from "@/services/tldw/TldwApiClient"

const createChat = (
  id: number,
  overrides: Partial<ServerChatSummary> = {}
): ServerChatSummary => ({
  id: `chat-${id}`,
  title: `Chat ${id}`,
  created_at: `2026-01-${String(id).padStart(2, "0")}T00:00:00Z`,
  updated_at: `2026-01-${String(id).padStart(2, "0")}T01:00:00Z`,
  ...overrides
})

describe("fetchAllServerChatPages", () => {
  it("fetches pages until the reported total is reached", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ chats: [createChat(1), createChat(2)], total: 5 })
      .mockResolvedValueOnce({ chats: [createChat(3), createChat(4)], total: 5 })
      .mockResolvedValueOnce({ chats: [createChat(5)], total: 5 })

    const result = await fetchAllServerChatPages(fetchPage, {
      limit: 2,
      maxPages: 10
    })

    expect(result.map((chat) => chat.id)).toEqual([
      "chat-1",
      "chat-2",
      "chat-3",
      "chat-4",
      "chat-5"
    ])
    expect(fetchPage).toHaveBeenCalledTimes(3)
    expect(fetchPage).toHaveBeenNthCalledWith(1, { limit: 2, offset: 0, signal: undefined })
    expect(fetchPage).toHaveBeenNthCalledWith(2, { limit: 2, offset: 2, signal: undefined })
    expect(fetchPage).toHaveBeenNthCalledWith(3, { limit: 2, offset: 4, signal: undefined })
  })

  it("stops when maxPages is reached", async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      chats: [createChat(1), createChat(2)],
      total: 999
    })

    const result = await fetchAllServerChatPages(fetchPage, {
      limit: 2,
      maxPages: 2
    })

    expect(result).toHaveLength(4)
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })

  it("returns already-fetched chats when a later page is rate-limited", async () => {
    const rateLimitedError = new Error("rate_limited (GET /api/v1/chats/)")
    ;(rateLimitedError as Error & { status?: number }).status = 429
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({ chats: [createChat(1), createChat(2)], total: 6 })
      .mockRejectedValueOnce(rateLimitedError)

    const result = await fetchAllServerChatPages(fetchPage, {
      limit: 2,
      maxPages: 10
    })

    expect(result.map((chat) => chat.id)).toEqual(["chat-1", "chat-2"])
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })
})

describe("filterServerChatHistoryItems", () => {
  it("filters case-insensitively by title, topic, and state", () => {
    const mapped = mapServerChatHistoryItems([
      createChat(1, { title: "Roadmap Review", topic_label: "planning", state: "resolved" }),
      createChat(2, { title: "Standup", topic_label: "status", state: "in-progress" }),
      createChat(3, { title: "Architecture", topic_label: "Design", state: "backlog" })
    ])

    expect(filterServerChatHistoryItems(mapped, "review").map((item) => item.id)).toEqual([
      "chat-1"
    ])
    expect(filterServerChatHistoryItems(mapped, "DESIGN").map((item) => item.id)).toEqual([
      "chat-3"
    ])
    expect(filterServerChatHistoryItems(mapped, "in-progress").map((item) => item.id)).toEqual(
      ["chat-2"]
    )
  })
})

describe("isRecoverableServerChatHistoryError", () => {
  it("returns true for auth status errors", () => {
    expect(
      isRecoverableServerChatHistoryError({
        message: "Invalid API key (GET /api/v1/chats/)",
        status: 401
      })
    ).toBe(true)

    expect(
      isRecoverableServerChatHistoryError({
        message: "Forbidden (GET /api/v1/chats/)",
        status: 403
      })
    ).toBe(true)
  })

  it("returns true for auth/config messages without explicit status", () => {
    expect(
      isRecoverableServerChatHistoryError(
        new Error("server not configured (GET /api/v1/chats/)")
      )
    ).toBe(true)

    expect(
      isRecoverableServerChatHistoryError(
        new Error("Unauthorized (GET /api/v1/chats/)")
      )
    ).toBe(true)

    expect(
      isRecoverableServerChatHistoryError(
        new Error("The operation was aborted. (GET /api/v1/chats/)")
      )
    ).toBe(true)

    expect(
      isRecoverableServerChatHistoryError(
        new Error("rate_limited (GET /api/v1/chats/)")
      )
    ).toBe(true)
  })

  it("returns true for HTTP 429 rate-limit status", () => {
    expect(
      isRecoverableServerChatHistoryError({
        message: "Too Many Requests (GET /api/v1/chats/)",
        status: 429
      })
    ).toBe(true)
  })

  it("returns false for non-auth server failures", () => {
    expect(
      isRecoverableServerChatHistoryError(
        new Error("Internal server error (GET /api/v1/chats/)")
      )
    ).toBe(false)
  })
})
