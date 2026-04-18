import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: (...args: unknown[]) => mocks.bgStream(...args)
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

import {
  TldwApiClient,
  TldwApiClientBase
} from "@/services/tldw/TldwApiClient"

describe("TldwApiClient Wave 5 boundary slices", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("keeps listAdminUsers on the mixed admin domain path after class cleanup", async () => {
    mocks.bgRequest.mockResolvedValue({
      users: [],
      total: 0,
      page: 1,
      limit: 20,
      pages: 0
    })

    const client = new TldwApiClient()
    await client.listAdminUsers({ limit: 20 })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/admin/users?limit=20",
        method: "GET"
      })
    )
    expect(Object.getOwnPropertyNames(TldwApiClientBase.prototype)).not.toContain(
      "listAdminUsers"
    )
  })

  it("keeps listSkills on the mixed workspace-api domain path after class cleanup", async () => {
    mocks.bgRequest.mockResolvedValue({
      skills: [],
      count: 0,
      total: 0,
      limit: 10,
      offset: 0
    })

    const client = new TldwApiClient()
    client.resolveApiPath = vi
      .fn(async () => "/api/v1/skills") as typeof client.resolveApiPath

    await client.listSkills({ limit: 10 })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/skills?limit=10",
        method: "GET"
      })
    )
    expect(Object.getOwnPropertyNames(TldwApiClientBase.prototype)).not.toContain(
      "listSkills"
    )
  })
})
