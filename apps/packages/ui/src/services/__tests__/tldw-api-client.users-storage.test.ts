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

describe("TldwApiClient current user storage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.storedConfig = {
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "test-api-key"
    }
  })

  it("requests account storage quota from /api/v1/users/storage", async () => {
    mocks.bgRequest.mockResolvedValue({
      user_id: 42,
      storage_used_mb: 128.5,
      storage_quota_mb: 5120,
      available_mb: 4991.5,
      usage_percentage: 2.5
    })

    const client = new TldwApiClient()
    const response = await client.getCurrentUserStorageQuota()

    expect(response).toMatchObject({
      user_id: 42,
      storage_used_mb: 128.5,
      storage_quota_mb: 5120,
      available_mb: 4991.5,
      usage_percentage: 2.5
    })

    const request = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(request.path).toBe("/api/v1/users/storage")
    expect(request.method).toBe("GET")
  })
})
