import { describe, expect, it } from "vitest"
import { resolveStartupSelectedModel } from "../model-startup-selection"

describe("resolveStartupSelectedModel", () => {
  it("does not auto-select while current model is hydrating", () => {
    expect(
      resolveStartupSelectedModel({
        currentModel: null,
        models: [{ model: "gpt-4o-mini" }],
        isCurrentModelHydrating: true
      })
    ).toBeNull()
  })

  it("does not auto-select while model preferences are hydrating", () => {
    expect(
      resolveStartupSelectedModel({
        currentModel: null,
        models: [{ model: "gpt-4o-mini" }],
        preferredModelIds: ["gpt-4o-mini"],
        arePreferencesHydrating: true
      })
    ).toBeNull()
  })

  it("does not overwrite an already selected model", () => {
    expect(
      resolveStartupSelectedModel({
        currentModel: "claude-3-5-sonnet",
        models: [{ model: "gpt-4o-mini" }]
      })
    ).toBeNull()
  })

  it("prefers first available favorite model in catalog order", () => {
    expect(
      resolveStartupSelectedModel({
        currentModel: null,
        models: [
          { model: "gpt-4o-mini" },
          { model: "claude-3-5-sonnet" },
          { model: "llama-3.1-70b" }
        ],
        preferredModelIds: ["claude-3-5-sonnet", "llama-3.1-70b"]
      })
    ).toBe("claude-3-5-sonnet")
  })

  it("falls back to first available model when no favorite matches", () => {
    expect(
      resolveStartupSelectedModel({
        currentModel: null,
        models: [{ model: "gpt-4o-mini" }, { model: "claude-3-5-sonnet" }],
        preferredModelIds: ["missing-model"]
      })
    ).toBe("gpt-4o-mini")
  })
})
