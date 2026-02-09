import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  healthCheck: vi.fn(),
  getOpenAPISpec: vi.fn(),
  bgRequest: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    healthCheck: (...args: unknown[]) => mocks.healthCheck(...args),
    getOpenAPISpec: (...args: unknown[]) => mocks.getOpenAPISpec(...args)
  }
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

const importCapabilitiesModule = async () =>
  import("@/services/tldw/server-capabilities")

describe("server capabilities docs-info merge", () => {
  beforeEach(() => {
    vi.resetModules()
    mocks.healthCheck.mockReset()
    mocks.getOpenAPISpec.mockReset()
    mocks.bgRequest.mockReset()
  })

  it("requires both persona route support and docs-info persona feature flag", async () => {
    mocks.healthCheck.mockResolvedValue(true)
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/persona/catalog": {},
        "/api/v1/persona/session": {},
        "/api/v1/personalization/profile": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({
      capabilities: {
        persona: false,
        personalization: true
      }
    })

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(false)
    expect(capabilities.hasPersonalization).toBe(true)
    expect(capabilities.specVersion).toBe("test-version")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/config/docs-info",
        method: "GET",
        noAuth: true
      })
    )
  })

  it("does not enable persona when docs-info says true but persona routes are missing", async () => {
    mocks.healthCheck.mockResolvedValue(true)
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/chat/completions": {}
      }
    })
    mocks.bgRequest.mockResolvedValue({
      capabilities: {
        persona: true
      }
    })

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(false)
  })

  it("falls back to openapi-only capability detection when docs-info fetch fails", async () => {
    mocks.healthCheck.mockResolvedValue(true)
    mocks.getOpenAPISpec.mockResolvedValue({
      info: { version: "test-version" },
      paths: {
        "/api/v1/persona/catalog": {}
      }
    })
    mocks.bgRequest.mockRejectedValue(new Error("docs-info unavailable"))

    const { getServerCapabilities } = await importCapabilitiesModule()
    const capabilities = await getServerCapabilities()

    expect(capabilities.hasPersona).toBe(true)
  })
})

