import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ACPRestClient, ACPWebSocketClient } from "@/services/acp/client"

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

describe("ACPWebSocketClient", () => {
  class MockWebSocket {
    static instances: MockWebSocket[] = []
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3

    readonly url: string
    readyState = MockWebSocket.CONNECTING
    onopen: (() => void) | null = null
    onclose: ((event: CloseEvent) => void) | null = null
    onerror: ((event: Event) => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null

    constructor(url: string) {
      this.url = url
      MockWebSocket.instances.push(this)
    }

    close(): void {
      this.readyState = MockWebSocket.CLOSED
    }

    send(): void {}

    open(): void {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.()
    }

    closeWith(code: number, reason = ""): void {
      this.readyState = MockWebSocket.CLOSED
      this.onclose?.({ code, reason } as CloseEvent)
    }
  }

  const createClient = () =>
    new ACPWebSocketClient({
      serverUrl: "http://localhost:8000",
      getAuthHeaders: async () => ({ "X-API-KEY": "test-key" }),
      getAuthParams: async () => ({ api_key: "test-key" }),
    })

  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket)
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it.each([4401, 4404, 4429])("does not reconnect for fatal close code %s", async (code) => {
    const client = createClient()

    await client.connect("sess-1")
    expect(MockWebSocket.instances).toHaveLength(1)

    const ws = MockWebSocket.instances[0]
    ws.open()
    ws.closeWith(code)

    await vi.advanceTimersByTimeAsync(60000)

    expect(MockWebSocket.instances).toHaveLength(1)
  })
})
