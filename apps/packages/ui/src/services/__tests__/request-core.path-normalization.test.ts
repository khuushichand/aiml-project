import { describe, expect, it, vi } from "vitest"

import { deriveRequestTimeout, tldwRequest } from "@/services/tldw/request-core"

describe("request-core media path normalization", () => {
  it("normalizes media listing path with trailing slash before query", async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: {
          "content-type": "application/json"
        }
      })
    )

    const response = await tldwRequest(
      {
        path: "/api/v1/media/?page=1&results_per_page=20&include_keywords=true",
        method: "GET"
      },
      {
        getConfig: async () => ({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }),
        fetchFn
      }
    )

    expect(fetchFn).toHaveBeenCalledTimes(1)
    expect(fetchFn.mock.calls[0]?.[0]).toBe(
      "http://127.0.0.1:8000/api/v1/media?page=1&results_per_page=20&include_keywords=true"
    )
    expect(response.ok).toBe(true)
  })

  it("applies media timeout to normalized media listing paths", () => {
    const cfg = {
      mediaRequestTimeoutMs: 25000,
      requestTimeoutMs: 10000
    }

    expect(deriveRequestTimeout(cfg, "/api/v1/media/?page=1")).toBe(25000)
    expect(deriveRequestTimeout(cfg, "/api/v1/media?page=1")).toBe(25000)
  })
})

describe("request-core absolute URL policy", () => {
  it("rejects absolute URLs by default when no allowlist is configured", async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    )

    const response = await tldwRequest(
      {
        path: "https://example.com/api/v1/health",
        method: "GET"
      },
      {
        getConfig: async () => ({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }),
        fetchFn
      }
    )

    expect(response.ok).toBe(false)
    expect(response.status).toBe(400)
    expect(String(response.error || "")).toContain("allowlist")
    expect(fetchFn).not.toHaveBeenCalled()
  })

  it("allows absolute URLs when the request origin is explicitly allowlisted", async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ healthy: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    )

    const response = await tldwRequest(
      {
        path: "https://example.com/api/v1/health",
        method: "GET"
      },
      {
        getConfig: async () => ({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder",
          absoluteUrlAllowlist: ["https://example.com"]
        }),
        fetchFn
      }
    )

    expect(response.ok).toBe(true)
    expect(fetchFn).toHaveBeenCalledTimes(1)
    expect(fetchFn.mock.calls[0]?.[0]).toBe("https://example.com/api/v1/health")
  })

  it("does not inject auth headers for allowlisted absolute URLs", async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ healthy: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    )

    const response = await tldwRequest(
      {
        path: "https://example.com/api/v1/health",
        method: "GET"
      },
      {
        getConfig: async () => ({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "multi-user",
          accessToken: "secret-access-token",
          absoluteUrlAllowlist: ["https://example.com"]
        }),
        fetchFn
      }
    )

    const requestInit = fetchFn.mock.calls[0]?.[1] as RequestInit | undefined
    const headerEntries = Object.entries((requestInit?.headers || {}) as Record<string, string>)
    const authHeader = headerEntries.find(([key]) => key.toLowerCase() === "authorization")

    expect(response.ok).toBe(true)
    expect(authHeader).toBeUndefined()
  })

  it("allows absolute URLs that match configured server origin", async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    )

    const response = await tldwRequest(
      {
        path: "http://127.0.0.1:8000/openapi.json",
        method: "GET"
      },
      {
        getConfig: async () => ({
          serverUrl: "http://127.0.0.1:8000",
          authMode: "single-user",
          apiKey: "test-key-not-placeholder"
        }),
        fetchFn
      }
    )

    expect(response.ok).toBe(true)
    expect(fetchFn).toHaveBeenCalledTimes(1)
    expect(fetchFn.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8000/openapi.json")
  })
})
