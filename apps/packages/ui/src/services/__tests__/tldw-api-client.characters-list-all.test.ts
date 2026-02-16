import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
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

describe("TldwApiClient listAllCharacters", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches all paginated character pages", async () => {
    const allCharacters = Array.from({ length: 2305 }, (_, index) => ({
      id: index + 1,
      name: `Character ${index + 1}`
    }))

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      if (request.method !== "GET" || typeof request.path !== "string") return []
      if (!request.path.startsWith("/api/v1/characters")) return []

      const [, rawQuery = ""] = request.path.split("?")
      const query = new URLSearchParams(rawQuery)
      const limit = Number(query.get("limit") || "100")
      const offset = Number(query.get("offset") || "0")
      return allCharacters.slice(offset, offset + limit)
    })

    const client = new TldwApiClient()
    const list = await client.listAllCharacters()

    expect(list).toHaveLength(2305)
    expect(list[0]).toMatchObject({ id: 1 })
    expect(list[list.length - 1]).toMatchObject({ id: 2305 })

    const listCalls = mocks.bgRequest.mock.calls
      .map(([request]) => request as { path?: string; method?: string })
      .filter(
        (request) =>
          request.method === "GET" &&
          typeof request.path === "string" &&
          request.path.startsWith("/api/v1/characters")
      )
      .map((request) => request.path)

    expect(listCalls).toEqual([
      "/api/v1/characters?limit=1000&offset=0",
      "/api/v1/characters?limit=1000&offset=1000",
      "/api/v1/characters?limit=1000&offset=2000"
    ])
  })

  it("stops when a page contains no new character identities", async () => {
    const repeatedPage = [
      { id: "a", name: "Alpha" },
      { id: "b", name: "Bravo" },
      { id: "c", name: "Charlie" }
    ]

    mocks.bgRequest.mockResolvedValue(repeatedPage)

    const client = new TldwApiClient()
    const list = await client.listAllCharacters({ pageSize: 3, maxPages: 10 })

    expect(list).toEqual(repeatedPage)

    const listCalls = mocks.bgRequest.mock.calls
      .map(([request]) => request as { path?: string; method?: string })
      .filter(
        (request) =>
          request.method === "GET" &&
          typeof request.path === "string" &&
          request.path.startsWith("/api/v1/characters")
      )
      .map((request) => request.path)

    expect(listCalls).toEqual([
      "/api/v1/characters?limit=3&offset=0",
      "/api/v1/characters?limit=3&offset=3"
    ])
  })
})
