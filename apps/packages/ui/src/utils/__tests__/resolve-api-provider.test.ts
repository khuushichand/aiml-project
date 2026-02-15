import { describe, expect, it } from "vitest"
import { resolveApiProviderForModel } from "../resolve-api-provider"

describe("resolveApiProviderForModel", () => {
  it("uses the explicit provider as the primary selection", async () => {
    await expect(
      resolveApiProviderForModel({
        modelId: "tldw:moonshot-v1",
        explicitProvider: " OpenAI ",
        providerHint: "moonshot"
      })
    ).resolves.toBe("openai")
  })

  it("falls back to server defaults when no explicit provider is selected", async () => {
    await expect(
      resolveApiProviderForModel({
        modelId: "moonshot-v1",
        providerHint: "moonshot"
      })
    ).resolves.toBeUndefined()
  })
})
