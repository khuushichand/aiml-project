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

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient getModels normalization", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("prefers model-like name over conflicting id when model field is absent", async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      if (request.path === "/api/v1/llm/models/metadata") {
        return {
          models: [
            {
              id: "z-ai/glm-4.6",
              name: "deepseek/deepseek-r1",
              provider: "openrouter",
              type: "chat"
            }
          ]
        }
      }
      return {}
    })

    const client = new TldwApiClient()
    const models = await client.getModels()

    expect(models).toHaveLength(1)
    expect(models[0]?.id).toBe("deepseek/deepseek-r1")
    expect(models[0]?.name).toBe("deepseek/deepseek-r1")
  })

  it("keeps canonical id and appends friendly label when name is non-model text", async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      if (request.path === "/api/v1/llm/models/metadata") {
        return {
          models: [
            {
              id: "openai/gpt-4o-mini",
              name: "GPT-4o Mini",
              provider: "openai",
              type: "chat"
            }
          ]
        }
      }
      return {}
    })

    const client = new TldwApiClient()
    const models = await client.getModels()

    expect(models).toHaveLength(1)
    expect(models[0]?.id).toBe("openai/gpt-4o-mini")
    expect(models[0]?.name).toBe("GPT-4o Mini (openai/gpt-4o-mini)")
  })
})
