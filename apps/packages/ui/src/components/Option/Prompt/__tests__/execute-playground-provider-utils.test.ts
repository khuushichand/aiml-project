import { describe, expect, it } from "vitest"
import {
  getExecuteDefaultModel,
  getExecuteDefaultProvider,
  getExecuteModelOptions,
  getExecuteProviderOptions,
  isValidExecuteModel,
  isValidExecuteProvider,
  normalizeExecuteProvidersCatalog
} from "../Studio/Prompts/execute-playground-provider-utils"

const providersPayload = {
  default_provider: "openai",
  providers: [
    {
      name: "openai",
      display_name: "OpenAI",
      default_model: "gpt-4o-mini",
      models_info: [{ name: "gpt-4o-mini" }, { id: "gpt-4.1-mini" }]
    },
    {
      name: "anthropic",
      display_name: "Anthropic",
      models: ["claude-3-7-sonnet", "claude-3-5-haiku"]
    }
  ]
}

describe("execute-playground-provider-utils", () => {
  it("normalizes provider catalog and preserves default provider", () => {
    const catalog = normalizeExecuteProvidersCatalog(providersPayload)

    expect(catalog.providers).toHaveLength(2)
    expect(getExecuteDefaultProvider(catalog)).toBe("openai")
    expect(getExecuteProviderOptions(catalog)).toEqual([
      { value: "openai", label: "OpenAI" },
      { value: "anthropic", label: "Anthropic" }
    ])
  })

  it("returns provider-scoped model options and defaults", () => {
    const catalog = normalizeExecuteProvidersCatalog(providersPayload)

    expect(getExecuteModelOptions(catalog, "openai")).toEqual([
      { value: "gpt-4o-mini", label: "gpt-4o-mini" },
      { value: "gpt-4.1-mini", label: "gpt-4.1-mini" }
    ])
    expect(getExecuteDefaultModel(catalog, "openai")).toBe("gpt-4o-mini")
    expect(getExecuteDefaultModel(catalog, "anthropic")).toBe("claude-3-7-sonnet")
  })

  it("validates provider/model selections against available options", () => {
    const catalog = normalizeExecuteProvidersCatalog(providersPayload)

    expect(isValidExecuteProvider(catalog, "openai")).toBe(true)
    expect(isValidExecuteProvider(catalog, "invalid-provider")).toBe(false)
    expect(isValidExecuteModel(catalog, "openai", "gpt-4o-mini")).toBe(true)
    expect(isValidExecuteModel(catalog, "openai", "claude-3-7-sonnet")).toBe(false)
  })
})
