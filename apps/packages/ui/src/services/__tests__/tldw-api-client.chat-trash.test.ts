import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient chat trash operations", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("soft deletes chat by default", async () => {
    mocks.bgRequest.mockResolvedValue(undefined)

    const client = new TldwApiClient()
    await client.deleteChat("abc")

    const call = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(call.path).toBe("/api/v1/chats/abc")
    expect(call.method).toBe("DELETE")
  })

  it("passes expected_version and hard_delete for permanent delete", async () => {
    mocks.bgRequest.mockResolvedValue(undefined)

    const client = new TldwApiClient()
    await client.deleteChat("abc", {
      expectedVersion: 4,
      hardDelete: true
    })

    const call = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(call.path).toBe("/api/v1/chats/abc?expected_version=4&hard_delete=true")
    expect(call.method).toBe("DELETE")
  })

  it("restores a chat from trash", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "abc",
      title: "Restored",
      created_at: "2026-02-18T00:00:00Z",
      updated_at: "2026-02-18T00:01:00Z",
      version: 5
    })

    const client = new TldwApiClient()
    const result = await client.restoreChat("abc", { expectedVersion: 4 })

    const call = mocks.bgRequest.mock.calls.at(-1)?.[0] as {
      path?: string
      method?: string
    }
    expect(call.path).toBe("/api/v1/chats/abc/restore?expected_version=4")
    expect(call.method).toBe("POST")
    expect(result.id).toBe("abc")
    expect(result.version).toBe(5)
  })
})
