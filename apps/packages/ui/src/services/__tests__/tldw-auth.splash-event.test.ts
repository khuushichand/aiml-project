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

describe("TldwAuthService splash trigger", () => {
  beforeEach(() => {
    mocks.getConfig.mockReset()
    mocks.updateConfig.mockReset()
    mocks.bgRequest.mockReset()
    mocks.emitSplashAfterLoginSuccess.mockReset()

    mocks.getConfig.mockResolvedValue({ serverUrl: "http://127.0.0.1:8000" })
    mocks.updateConfig.mockResolvedValue(undefined)
    mocks.bgRequest.mockImplementation(async ({ path, method }) => {
      if (path === "/api/v1/auth/login" && method === "POST") {
        return {
          access_token: "access-token",
          refresh_token: "refresh-token",
          token_type: "bearer"
        }
      }

      if (path === "/api/v1/auth/magic-link/verify" && method === "POST") {
        return {
          access_token: "magic-access-token",
          refresh_token: "magic-refresh-token",
          token_type: "bearer"
        }
      }

      if (path === "/api/v1/orgs" && method === "GET") {
        return { items: [{ id: 42 }] }
      }

      return {}
    })
  })

  it("emits splash trigger after successful password login", async () => {
    const auth = new TldwAuthService()

    await auth.login({ username: "user", password: "password" })

    expect(mocks.emitSplashAfterLoginSuccess).toHaveBeenCalledTimes(1)
  })

  it("emits splash trigger after successful magic-link verification", async () => {
    const auth = new TldwAuthService()

    await auth.verifyMagicLink("magic-token")

    expect(mocks.emitSplashAfterLoginSuccess).toHaveBeenCalledTimes(1)
  })
})

