import { beforeEach, describe, expect, it, vi } from "vitest"
import { ACPRestClient } from "@/services/acp/client"

describe("ACPRestClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  const createClient = () =>
    new ACPRestClient({
      serverUrl: "http://localhost:8000",
      getAuthHeaders: async () => ({ "X-API-KEY": "test-key" }),
      getAuthParams: async () => ({ api_key: "test-key" }),
    })

  it("lists sessions with query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sessions: [], total: 0 }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const client = createClient()
    await client.listSessions({ status: "active", limit: 25, offset: 10 })

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/acp/sessions?status=active&limit=25&offset=10",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-API-KEY": "test-key",
        }),
      })
    )
  })

  it("loads detail and usage endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "sess-1", messages: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "sess-1", usage: { total_tokens: 42 } }),
      })
    vi.stubGlobal("fetch", fetchMock)

    const client = createClient()
    await client.getSessionDetail("sess-1")
    await client.getSessionUsage("sess-1")

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/acp/sessions/sess-1/detail",
      expect.any(Object)
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/acp/sessions/sess-1/usage",
      expect.any(Object)
    )
  })

  it("forks sessions using message_index payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        session_id: "fork-1",
        name: "Forked",
        forked_from: "sess-1",
        message_count: 4,
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const client = createClient()
    await client.forkSession("sess-1", { message_index: 3, name: "Forked" })

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/acp/sessions/sess-1/fork",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message_index: 3, name: "Forked" }),
      })
    )
  })
})
