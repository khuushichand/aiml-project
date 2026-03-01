import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn(),
  storedConfig: null as
    | {
        serverUrl: string
        authMode: "single-user" | "multi-user"
        apiKey?: string
        accessToken?: string
      }
    | null
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async (key?: string) => {
      if (key === "tldwConfig") {
        return mocks.storedConfig
      }
      return null
    }),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient OpenAI OAuth methods", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.storedConfig = {
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "test-api-key"
    }
  })

  it("starts OpenAI OAuth authorize flow", async () => {
    mocks.bgRequest.mockResolvedValue({
      provider: "openai",
      auth_url: "https://oauth.example.com/authorize?state=test",
      auth_session_id: "session-123",
      expires_at: "2026-02-22T12:00:00Z"
    })

    const client = new TldwApiClient()
    const response = await client.startOpenAIOAuthAuthorize({
      return_path: "/settings/model"
    })

    expect(response.auth_session_id).toBe("session-123")

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
      body?: Record<string, unknown>
    }
    expect(request.path).toBe("/api/v1/users/keys/openai/oauth/authorize")
    expect(request.method).toBe("POST")
    expect(request.body?.return_path).toBe("/settings/model")
  })

  it("fetches OpenAI OAuth status", async () => {
    mocks.bgRequest.mockResolvedValue({
      provider: "openai",
      connected: true,
      auth_source: "oauth",
      expires_at: "2026-02-22T13:00:00Z"
    })

    const client = new TldwApiClient()
    const response = await client.getOpenAIOAuthStatus()

    expect(response.connected).toBe(true)
    expect(response.auth_source).toBe("oauth")

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(request.path).toBe("/api/v1/users/keys/openai/oauth/status")
    expect(request.method).toBe("GET")
  })

  it("refreshes OpenAI OAuth token", async () => {
    mocks.bgRequest.mockResolvedValue({
      provider: "openai",
      status: "refreshed",
      expires_at: "2026-02-22T13:30:00Z"
    })

    const client = new TldwApiClient()
    const response = await client.refreshOpenAIOAuth()

    expect(response.status).toBe("refreshed")

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(request.path).toBe("/api/v1/users/keys/openai/oauth/refresh")
    expect(request.method).toBe("POST")
  })

  it("disconnects OpenAI OAuth credential", async () => {
    mocks.bgRequest.mockResolvedValue(undefined)

    const client = new TldwApiClient()
    await client.disconnectOpenAIOAuth()

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(request.path).toBe("/api/v1/users/keys/openai/oauth")
    expect(request.method).toBe("DELETE")
  })

  it("switches OpenAI credential source", async () => {
    mocks.bgRequest.mockResolvedValue({
      provider: "openai",
      auth_source: "api_key"
    })

    const client = new TldwApiClient()
    const response = await client.switchOpenAICredentialSource("api_key")

    expect(response.auth_source).toBe("api_key")

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
      body?: Record<string, unknown>
    }
    expect(request.path).toBe("/api/v1/users/keys/openai/source")
    expect(request.method).toBe("POST")
    expect(request.body?.auth_source).toBe("api_key")
  })
})
