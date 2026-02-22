import { beforeEach, describe, expect, it, vi } from "vitest"
import { tldwModels } from "@/services/tldw"
import { inferProviderFromModel } from "@/utils/provider-registry"
import { resolveApiProviderForModel } from "../resolve-api-provider"

vi.mock("@/services/tldw", () => ({
  tldwModels: {
    getModels: vi.fn()
  }
}))

vi.mock("@/utils/provider-registry", () => ({
  inferProviderFromModel: vi.fn()
}))

describe("resolveApiProviderForModel", () => {
  const getModelsMock = vi.mocked(tldwModels.getModels)
  const inferProviderFromModelMock = vi.mocked(inferProviderFromModel)

  beforeEach(() => {
    getModelsMock.mockReset()
    getModelsMock.mockResolvedValue([])
    inferProviderFromModelMock.mockReset()
    inferProviderFromModelMock.mockReturnValue(null)
  })

  it("uses the explicit provider as the primary selection", async () => {
    await expect(
      resolveApiProviderForModel({
        modelId: "tldw:moonshot-v1",
        explicitProvider: " OpenAI ",
        providerHint: "moonshot"
      })
    ).resolves.toBe("openai")
  })

  it("uses official provider metadata when model exists in the server catalog", async () => {
    getModelsMock.mockResolvedValue([
      {
        id: "deepseek-chat",
        name: "DeepSeek Chat",
        provider: "DeepSeek",
        type: "chat"
      }
    ] as any)

    await expect(
      resolveApiProviderForModel({
        modelId: "tldw:deepseek-chat"
      })
    ).resolves.toBe("deepseek")
  })

  it("falls back to model-prefix inference for stale model ids", async () => {
    await expect(
      resolveApiProviderForModel({
        modelId: "deepseek-chat"
      })
    ).resolves.toBe("deepseek")
  })

  it("returns undefined when the provider cannot be inferred", async () => {
    await expect(
      resolveApiProviderForModel({
        modelId: "custom-random-model-123"
      })
    ).resolves.toBeUndefined()
  })
})
