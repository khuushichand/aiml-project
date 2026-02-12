import { describe, expect, it, vi } from "vitest"

import {
  fetchAllServerChatPages,
  filterServerChatHistoryItems,
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
    expect(fetchPage).toHaveBeenNthCalledWith(1, { limit: 2, offset: 0 })
    expect(fetchPage).toHaveBeenNthCalledWith(2, { limit: 2, offset: 2 })
    expect(fetchPage).toHaveBeenNthCalledWith(3, { limit: 2, offset: 4 })
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
