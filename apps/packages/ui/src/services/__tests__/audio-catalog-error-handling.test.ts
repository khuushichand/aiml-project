import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequestClient: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequestClient: (...args: unknown[]) => mocks.bgRequestClient(...args)
}))

import { fetchTtsProviders } from "@/services/tldw/audio-providers"
import {
  fetchTldwVoices,
  fetchTldwVoiceCatalog
} from "@/services/tldw/audio-voices"

describe("audio catalog service error handling", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("returns null for provider catalog errors by default", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(fetchTtsProviders()).resolves.toBeNull()
  })

  it("rethrows provider catalog errors when throwOnError is enabled", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(
      fetchTtsProviders({ throwOnError: true })
    ).rejects.toThrow("timeout")
  })

  it("returns an empty voice list for voice fetch errors by default", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(fetchTldwVoices()).resolves.toEqual([])
  })

  it("rethrows voice list errors when throwOnError is enabled", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(fetchTldwVoices({ throwOnError: true })).rejects.toThrow(
      "timeout"
    )
  })

  it("returns an empty provider-scoped voice list for catalog errors by default", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(fetchTldwVoiceCatalog("openai")).resolves.toEqual([])
  })

  it("rethrows provider-scoped catalog errors when throwOnError is enabled", async () => {
    mocks.bgRequestClient.mockRejectedValueOnce(new Error("timeout"))

    await expect(
      fetchTldwVoiceCatalog("openai", { throwOnError: true })
    ).rejects.toThrow("timeout")
  })
})
