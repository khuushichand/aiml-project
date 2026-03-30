import { describe, expect, it, vi, beforeEach } from "vitest"

const fetcherMock = vi.hoisted(() => vi.fn())
const getAuthHeadersMock = vi.hoisted(() => vi.fn())

vi.mock("@/libs/fetcher", () => ({
  default: fetcherMock
}))

vi.mock("@/services/tldw/TldwAuth", () => ({
  tldwAuth: {
    getAuthHeaders: getAuthHeadersMock
  }
}))

import { fetchWithTldwAuth } from "@/services/tldw/auth-fetch"

describe("fetchWithTldwAuth", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetcherMock.mockResolvedValue(new Response(null, { status: 204 }))
  })

  it("merges authenticated headers into outgoing tldw fetches", async () => {
    getAuthHeadersMock.mockResolvedValue({
      "X-API-KEY": "real-key",
      "X-TLDW-Org-Id": "7"
    })

    await fetchWithTldwAuth("http://127.0.0.1:8000/api/v1/sharing/shared-with-me", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-KEY": "stale-key"
      },
      body: "{}"
    })

    expect(fetcherMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/sharing/shared-with-me",
      expect.objectContaining({
        method: "POST",
        body: "{}",
        headers: expect.objectContaining({
          "content-type": "application/json",
          "x-api-key": "real-key",
          "x-tldw-org-id": "7"
        })
      })
    )
  })
})
