import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  connect: vi.fn(),
  tldwRequest: vi.fn(),
  storageGet: vi.fn(async () => null),
  storageSet: vi.fn(async () => undefined)
}))

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      id: "test-extension",
      sendMessage: (...args: unknown[]) =>
        (mocks.sendMessage as (...args: unknown[]) => unknown)(...args),
      connect: (...args: unknown[]) =>
        (mocks.connect as (...args: unknown[]) => unknown)(...args)
    }
  }
}))

vi.mock("@/services/tldw/request-core", () => ({
  tldwRequest: (...args: unknown[]) =>
    (mocks.tldwRequest as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (...args: unknown[]) =>
      (mocks.storageGet as (...args: unknown[]) => unknown)(...args),
    set: (...args: unknown[]) =>
      (mocks.storageSet as (...args: unknown[]) => unknown)(...args)
  })
}))

const importProxy = async () => import("@/services/background-proxy")

describe("background proxy fallback safety", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useRealTimers()
    mocks.sendMessage.mockReset()
    mocks.connect.mockReset()
    mocks.tldwRequest.mockReset()
    mocks.storageGet.mockReset()
    mocks.storageSet.mockReset()
    mocks.storageGet.mockResolvedValue(null)
    mocks.storageSet.mockResolvedValue(undefined)
  })

  it("does not fall back to direct request when background returns non-2xx", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: false, status: 500, error: "boom" })
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { fallback: true } })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({ path: "/api/v1/health", method: "GET" })
    ).rejects.toMatchObject({ status: 500 })
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("keeps auth enabled for same-origin absolute URLs in background requests", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true, status: 200, data: { ok: true } })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "https://api.example.com",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({
        path: "https://api.example.com/api/v1/health",
        method: "GET"
      })
    ).resolves.toEqual({ ok: true })

    expect(mocks.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({
          noAuth: false
        })
      })
    )
  })

  it("skips auth for cross-origin absolute URLs in background requests", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true, status: 200, data: { ok: true } })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "https://api.example.com",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({
        path: "https://other.example.com/api/v1/health",
        method: "GET"
      })
    ).resolves.toEqual({ ok: true })

    expect(mocks.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({
          noAuth: true
        })
      })
    )
  })

  it("normalizes legacy media listing paths before forwarding request", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true, status: 200, data: { ok: true } })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({
        path: "/api/v1/media/?page=1&results_per_page=20&include_keywords=true",
        method: "GET"
      })
    ).resolves.toEqual({ ok: true })

    expect(mocks.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({
          path: "/api/v1/media?page=1&results_per_page=20&include_keywords=true"
        })
      })
    )
  })

  it("emits backend-unreachable event when API request fails with network status 0", async () => {
    mocks.sendMessage.mockRejectedValue(
      new Error("Could not establish connection. Receiving end does not exist.")
    )
    mocks.tldwRequest.mockResolvedValue({
      ok: false,
      status: 0,
      error: "NetworkError when attempting to fetch resource."
    })

    const eventSpy = vi.fn()
    const eventName = "tldw:backend-unreachable"
    window.addEventListener(eventName, eventSpy as EventListener)

    try {
      const { bgRequest } = await importProxy()
      await expect(
        bgRequest({
          path: "/api/v1/llm/models/metadata",
          method: "GET"
        })
      ).rejects.toMatchObject({ status: 0 })
    } finally {
      window.removeEventListener(eventName, eventSpy as EventListener)
    }

    expect(eventSpy).toHaveBeenCalledTimes(1)
    const detail = (eventSpy.mock.calls[0]?.[0] as CustomEvent | undefined)
      ?.detail as
      | {
          path?: string
          method?: string
          status?: number
          source?: string
        }
      | undefined
    expect(detail?.path).toBe("/api/v1/llm/models/metadata")
    expect(detail?.method).toBe("GET")
    expect(detail?.status).toBe(0)
    expect(detail?.source).toBe("direct")
  })

  it("classifies aborted direct fallback requests as AbortError", async () => {
    mocks.sendMessage.mockRejectedValue(
      new Error("Could not establish connection. Receiving end does not exist.")
    )
    mocks.tldwRequest.mockResolvedValue({
      ok: false,
      status: 0,
      error: "The operation was aborted."
    })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({
        path: "/api/v1/chats/?limit=200&offset=0&ordering=-updated_at",
        method: "GET"
      })
    ).rejects.toMatchObject({
      name: "AbortError",
      status: 0,
      code: "REQUEST_ABORTED"
    })
  })

  it("falls back to direct request on GET extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { via: "direct" } })

    const { bgRequest } = await importProxy()
    const pending = bgRequest<{ via: string }>({
      path: "/api/v1/health",
      method: "GET"
    })

    await vi.advanceTimersByTimeAsync(3001)

    await expect(pending).resolves.toEqual({ via: "direct" })
    expect(mocks.tldwRequest).toHaveBeenCalledTimes(1)
  })

  it("does not fall back to direct request on POST extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { via: "direct" } })

    const { bgRequest } = await importProxy()
    const pending = bgRequest({
      path: "/api/v1/notes/search/",
      method: "POST",
      body: { q: "hello" }
    })
    const assertion = expect(pending).rejects.toThrow("Extension messaging timeout")

    await vi.advanceTimersByTimeAsync(3001)

    await assertion
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("does not fall back to direct upload when background returns non-2xx", async () => {
    mocks.sendMessage.mockResolvedValue({
      ok: false,
      status: 400,
      error: "bad request",
      data: { detail: "invalid" }
    })

    const { bgUpload } = await importProxy()

    await expect(
      bgUpload({
        path: "/api/v1/media/add",
        method: "POST",
        fields: { title: "example" }
      })
    ).rejects.toMatchObject({ status: 400 })
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("does not fall back to direct upload on POST extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))

    const { bgUpload } = await importProxy()
    const pending = bgUpload({
      path: "/api/v1/media/add",
      method: "POST",
      fields: { title: "example" },
      timeoutMs: 100
    })
    const assertion = expect(pending).rejects.toThrow("Extension messaging timeout")

    await vi.advanceTimersByTimeAsync(5001)

    await assertion
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("falls back to direct stream when port errors before first data chunk", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true })
    const onMessageListeners = new Set<(msg: any) => void>()
    const onDisconnectListeners = new Set<() => void>()
    const port = {
      onMessage: {
        addListener: (listener: (msg: any) => void) => onMessageListeners.add(listener),
        removeListener: (listener: (msg: any) => void) => onMessageListeners.delete(listener)
      },
      onDisconnect: {
        addListener: (listener: () => void) => onDisconnectListeners.add(listener),
        removeListener: (listener: () => void) => onDisconnectListeners.delete(listener)
      },
      postMessage: vi.fn(() => {
        onMessageListeners.forEach((listener) =>
          listener({
            event: "error",
            message: "Could not establish connection. Receiving end does not exist."
          })
        )
      }),
      disconnect: vi.fn(() => {
        onDisconnectListeners.forEach((listener) => listener())
      })
    }
    mocks.connect.mockReturnValue(port as any)
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async () =>
      new Response(
        'data: {"event":"run_started","run_id":"run_1","seq":1,"data":{}}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { "content-type": "text/event-stream" }
        }
      )
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const chunks: string[] = []

    try {
      for await (const chunk of bgStream({
        path: "/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        chunks.push(chunk)
      }
    } finally {
      vi.unstubAllGlobals()
    }

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(mocks.connect).toHaveBeenCalledTimes(1)
    expect(chunks.some((chunk) => chunk.includes('"event":"run_started"'))).toBe(true)
  })

  it("treats post-first-chunk transport disconnect as graceful end", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true })
    const onMessageListeners = new Set<(msg: any) => void>()
    const onDisconnectListeners = new Set<() => void>()
    const port = {
      onMessage: {
        addListener: (listener: (msg: any) => void) => onMessageListeners.add(listener),
        removeListener: (listener: (msg: any) => void) => onMessageListeners.delete(listener)
      },
      onDisconnect: {
        addListener: (listener: () => void) => onDisconnectListeners.add(listener),
        removeListener: (listener: () => void) => onDisconnectListeners.delete(listener)
      },
      postMessage: vi.fn(() => {
        onMessageListeners.forEach((listener) =>
          listener({
            event: "data",
            data: '{"choices":[{"delta":{"content":"H"}}]}'
          })
        )
        onMessageListeners.forEach((listener) =>
          listener({
            event: "error",
            message: "Could not establish connection. Receiving end does not exist."
          })
        )
      }),
      disconnect: vi.fn(() => {
        onDisconnectListeners.forEach((listener) => listener())
      })
    }
    mocks.connect.mockReturnValue(port as any)
    const fetchSpy = vi.fn(async () =>
      new Response("data: [DONE]\n\n", {
        status: 200,
        headers: { "content-type": "text/event-stream" }
      })
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const chunks: string[] = []

    try {
      for await (const chunk of bgStream({
        path: "/api/v1/chats/abc/complete-v2",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true }
      })) {
        chunks.push(chunk)
      }
    } finally {
      vi.unstubAllGlobals()
    }

    expect(chunks).toContain('{"choices":[{"delta":{"content":"H"}}]}')
    expect(
      chunks.some((chunk) =>
        chunk.includes('"event":"stream_transport_interrupted"')
      )
    ).toBe(true)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it("falls back to direct stream when runtime.connect throws", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true })
    mocks.connect.mockImplementation(() => {
      throw new Error("Could not establish connection. Receiving end does not exist.")
    })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async () =>
      new Response(
        'data: {"event":"run_started","run_id":"run_2","seq":1,"data":{}}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { "content-type": "text/event-stream" }
        }
      )
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const chunks: string[] = []
    try {
      for await (const chunk of bgStream({
        path: "/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        chunks.push(chunk)
      }
    } finally {
      vi.unstubAllGlobals()
    }

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(mocks.connect).toHaveBeenCalledTimes(1)
    expect(chunks.some((chunk) => chunk.includes('"event":"run_started"'))).toBe(true)
  })

  it("does not fall back to direct stream on HTTP status errors from port transport", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: true })
    const onMessageListeners = new Set<(msg: any) => void>()
    const onDisconnectListeners = new Set<() => void>()
    const port = {
      onMessage: {
        addListener: (listener: (msg: any) => void) => onMessageListeners.add(listener),
        removeListener: (listener: (msg: any) => void) => onMessageListeners.delete(listener)
      },
      onDisconnect: {
        addListener: (listener: () => void) => onDisconnectListeners.add(listener),
        removeListener: (listener: () => void) => onDisconnectListeners.delete(listener)
      },
      postMessage: vi.fn(() => {
        onMessageListeners.forEach((listener) =>
          listener({
            event: "error",
            status: 401,
            message: "Unauthorized"
          })
        )
      }),
      disconnect: vi.fn(() => {
        onDisconnectListeners.forEach((listener) => listener())
      })
    }
    mocks.connect.mockReturnValue(port as any)
    const fetchSpy = vi.fn(async () =>
      new Response(
        'data: {"event":"run_started","run_id":"run_fallback","seq":1,"data":{}}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { "content-type": "text/event-stream" }
        }
      )
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const consume = async () => {
      for await (const _chunk of bgStream({
        path: "/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        // no-op
      }
    }

    try {
      await expect(consume()).rejects.toMatchObject({
        message: "Unauthorized",
        status: 401
      })
      expect(fetchSpy).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it("blocks unallowlisted absolute URLs in direct stream fallback", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: false })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "https://api.example.com",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async () =>
      new Response("data: [DONE]\n\n", {
        status: 200,
        headers: { "content-type": "text/event-stream" }
      })
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const consume = async () => {
      for await (const _chunk of bgStream({
        path: "https://evil.example.net/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        // no-op
      }
    }

    try {
      await expect(consume()).rejects.toThrow("allowlisted")
      expect(fetchSpy).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it("preserves auth headers for same-origin absolute URLs in direct stream fallback", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: false })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "https://api.example.com",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async () =>
      new Response(
        'data: {"event":"run_started","run_id":"run_auth","seq":1,"data":{}}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { "content-type": "text/event-stream" }
        }
      )
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const chunks: string[] = []

    try {
      for await (const chunk of bgStream({
        path: "https://api.example.com/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        chunks.push(chunk)
      }
    } finally {
      vi.unstubAllGlobals()
    }

    const requestInit = fetchSpy.mock.calls[0]?.[1] as RequestInit | undefined
    const requestHeaders = (requestInit?.headers || {}) as Record<string, string>
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(requestHeaders["X-API-KEY"]).toBe("test-key-not-placeholder")
    expect(chunks.some((chunk) => chunk.includes('"event":"run_started"'))).toBe(true)
  })

  it("does not refresh or re-add auth for cross-origin absolute stream URLs", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: false })
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "https://api.example.com",
          authMode: "multi-user",
          accessToken: "secret-access-token",
          refreshToken: "secret-refresh-token",
          absoluteUrlAllowlist: ["https://other.example.com"]
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes("/api/v1/auth/refresh")) {
        return new Response(JSON.stringify({ access_token: "new-token" }), {
          status: 200,
          headers: { "content-type": "application/json" }
        })
      }
      return new Response("Unauthorized", {
        status: 401,
        headers: { "content-type": "text/plain" }
      })
    })
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const consume = async () => {
      for await (const _chunk of bgStream({
        path: "https://other.example.com/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        // no-op
      }
    }

    try {
      await expect(consume()).rejects.toThrow("Unauthorized")
      expect(fetchSpy).toHaveBeenCalledTimes(1)
      expect(String(fetchSpy.mock.calls[0]?.[0] || "")).toContain(
        "https://other.example.com/api/v1/chat/completions"
      )
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it("falls back directly when runtime ping preflight times out", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.storageGet.mockImplementation(async (key: string) => {
      if (key === "tldwConfig") {
        return {
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }
      }
      return null
    })
    const fetchSpy = vi.fn(async () =>
      new Response(
        'data: {"event":"run_started","run_id":"run_3","seq":1,"data":{}}\n\ndata: [DONE]\n\n',
        {
          status: 200,
          headers: { "content-type": "text/event-stream" }
        }
      )
    )
    vi.stubGlobal("fetch", fetchSpy as any)

    const { bgStream } = await importProxy()
    const chunks: string[] = []
    try {
      for await (const chunk of bgStream({
        path: "/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: { stream: true, messages: [] }
      })) {
        chunks.push(chunk)
      }
    } finally {
      vi.unstubAllGlobals()
    }

    expect(mocks.connect).not.toHaveBeenCalled()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(chunks.some((chunk) => chunk.includes('"event":"run_started"'))).toBe(true)
  })
})
