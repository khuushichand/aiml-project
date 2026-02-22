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
