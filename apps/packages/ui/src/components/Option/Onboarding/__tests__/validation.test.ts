import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  testApiKey: vi.fn(),
  login: vi.fn(),
  verifyMagicLink: vi.fn()
}))

vi.mock("@/services/tldw/TldwAuth", () => ({
  tldwAuth: {
    testApiKey: mocks.testApiKey,
    login: mocks.login,
    verifyMagicLink: mocks.verifyMagicLink
  }
}))

import { categorizeConnectionError, validateApiKey } from "../validation"

describe("onboarding validation error classification", () => {
  beforeEach(() => {
    mocks.testApiKey.mockReset()
    mocks.login.mockReset()
    mocks.verifyMagicLink.mockReset()
  })

  it("classifies browser fetch network errors as cors/network blocked", () => {
    const kind = categorizeConnectionError(
      0,
      "NetworkError when attempting to fetch resource. (GET /api/v1/users/me/profile)"
    )

    expect(kind).toBe("cors_blocked")
  })

  it("returns cors_blocked for API key validation network failures", async () => {
    mocks.testApiKey.mockRejectedValueOnce(
      new Error("NetworkError when attempting to fetch resource. (GET /api/v1/users/me/profile)")
    )

    const result = await validateApiKey(
      "http://192.168.5.186:8000",
      "real-key",
      ((key: string, fallback: string) => fallback || key) as any
    )

    expect(result.success).toBe(false)
    expect(result.errorKind).toBe("cors_blocked")
  })

  it("keeps invalid key classification for explicit auth failures", async () => {
    mocks.testApiKey.mockResolvedValueOnce(false)

    const result = await validateApiKey(
      "http://192.168.5.186:8000",
      "bad-key",
      ((key: string, fallback: string) => fallback || key) as any
    )

    expect(result.success).toBe(false)
    expect(result.errorKind).toBe("auth_invalid")
  })
})
