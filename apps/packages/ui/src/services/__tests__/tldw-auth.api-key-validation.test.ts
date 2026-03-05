import { beforeEach, describe, expect, it, vi } from "vitest"

import { TldwAuthService } from "../tldw/TldwAuth"

const mocks = vi.hoisted(() => ({
  getConfig: vi.fn(),
  updateConfig: vi.fn(),
  bgRequest: vi.fn(),
  emitSplashAfterLoginSuccess: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: mocks.getConfig,
    updateConfig: mocks.updateConfig
  }
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock("@/services/splash-events", () => ({
  emitSplashAfterLoginSuccess: mocks.emitSplashAfterLoginSuccess
}))

describe("TldwAuthService.testApiKey", () => {
  beforeEach(() => {
    mocks.getConfig.mockReset()
    mocks.updateConfig.mockReset()
    mocks.bgRequest.mockReset()
    mocks.emitSplashAfterLoginSuccess.mockReset()
  })

  it("uses a relative profile path so absolute URL policy does not block API key validation", async () => {
    const auth = new TldwAuthService()

    mocks.bgRequest.mockImplementation(async ({ path, method, headers, noAuth }) => {
      if (typeof path === "string" && /^https?:/i.test(path)) {
        throw new Error(
          "Absolute URL requests are blocked unless the request origin is explicitly allowlisted."
        )
      }

      expect(path).toBe("/api/v1/users/me/profile")
      expect(method).toBe("GET")
      expect(noAuth).toBe(true)
      expect(headers).toMatchObject({ "X-API-KEY": "real-api-key" })
      return { id: 1 }
    })

    const ok = await auth.testApiKey("https://example.com", "real-api-key")

    expect(ok).toBe(true)
    expect(mocks.bgRequest).toHaveBeenCalledTimes(1)
  })

  it("returns false for invalid API key responses", async () => {
    const auth = new TldwAuthService()
    const unauthorized = Object.assign(new Error("Unauthorized"), { status: 401 })

    mocks.bgRequest.mockRejectedValueOnce(unauthorized)

    const ok = await auth.testApiKey("https://example.com", "bad-api-key")

    expect(ok).toBe(false)
  })

  it("throws a connection-style error when the request is aborted", async () => {
    const auth = new TldwAuthService()
    const aborted = Object.assign(new Error("The operation was aborted."), {
      status: 0,
      name: "AbortError"
    })

    mocks.bgRequest.mockRejectedValueOnce(aborted)

    await expect(
      auth.testApiKey("https://example.com", "real-api-key")
    ).rejects.toThrow(/timed out|aborted/i)
  })
})
