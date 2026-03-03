import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient reading saved searches and note links", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("creates and lists reading saved searches", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        id: 12,
        name: "Daily",
        query: { q: "ai" },
        sort: "updated_desc",
        created_at: "2026-03-02T00:00:00Z",
        updated_at: "2026-03-02T00:00:00Z"
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 12,
            name: "Daily",
            query: { q: "ai" },
            sort: "updated_desc",
            created_at: "2026-03-02T00:00:00Z",
            updated_at: "2026-03-02T00:00:00Z"
          }
        ],
        total: 1,
        limit: 20,
        offset: 5
      })

    const client = new TldwApiClient()
    const created = await client.createReadingSavedSearch({
      name: "Daily",
      query: { q: "ai" },
      sort: "updated_desc"
    })
    const listed = await client.listReadingSavedSearches({ limit: 20, offset: 5 })

    expect(created).toEqual({
      id: "12",
      name: "Daily",
      query: { q: "ai" },
      sort: "updated_desc",
      created_at: "2026-03-02T00:00:00Z",
      updated_at: "2026-03-02T00:00:00Z"
    })
    expect(listed).toEqual({
      items: [
        {
          id: "12",
          name: "Daily",
          query: { q: "ai" },
          sort: "updated_desc",
          created_at: "2026-03-02T00:00:00Z",
          updated_at: "2026-03-02T00:00:00Z"
        }
      ],
      total: 1,
      limit: 20,
      offset: 5
    })
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/reading/saved-searches",
        method: "POST",
        body: {
          name: "Daily",
          query: { q: "ai" },
          sort: "updated_desc"
        }
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/reading/saved-searches?limit=20&offset=5",
        method: "GET"
      })
    )
  })

  it("updates and deletes a reading saved search", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        id: 12,
        name: "Daily AI",
        query: { q: "llm" },
        sort: "updated_asc"
      })
      .mockResolvedValueOnce({ ok: true })

    const client = new TldwApiClient()
    const updated = await client.updateReadingSavedSearch("12", {
      name: "Daily AI",
      query: { q: "llm" },
      sort: "updated_asc"
    })
    const removed = await client.deleteReadingSavedSearch("12")

    expect(updated).toEqual({
      id: "12",
      name: "Daily AI",
      query: { q: "llm" },
      sort: "updated_asc",
      created_at: undefined,
      updated_at: undefined
    })
    expect(removed).toEqual({ ok: true })
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/reading/saved-searches/12",
        method: "PATCH",
        body: {
          name: "Daily AI",
          query: { q: "llm" },
          sort: "updated_asc"
        }
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/reading/saved-searches/12",
        method: "DELETE"
      })
    )
  })

  it("links, lists, and unlinks note associations for a reading item", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        item_id: 77,
        note_id: "note-1",
        created_at: "2026-03-02T01:00:00Z"
      })
      .mockResolvedValueOnce({
        item_id: 77,
        links: [
          {
            item_id: 77,
            note_id: "note-1",
            created_at: "2026-03-02T01:00:00Z"
          }
        ]
      })
      .mockResolvedValueOnce({ ok: true })

    const client = new TldwApiClient()
    const linked = await client.linkReadingItemToNote("77", "note-1")
    const links = await client.listReadingItemNoteLinks("77")
    const unlinked = await client.unlinkReadingItemNote("77", "note-1")

    expect(linked).toEqual({
      item_id: "77",
      note_id: "note-1",
      created_at: "2026-03-02T01:00:00Z"
    })
    expect(links).toEqual([
      {
        item_id: "77",
        note_id: "note-1",
        created_at: "2026-03-02T01:00:00Z"
      }
    ])
    expect(unlinked).toEqual({ ok: true })
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/reading/items/77/links/note",
        method: "POST",
        body: { note_id: "note-1" }
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/reading/items/77/links",
        method: "GET"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        path: "/api/v1/reading/items/77/links/note/note-1",
        method: "DELETE"
      })
    )
  })
})
