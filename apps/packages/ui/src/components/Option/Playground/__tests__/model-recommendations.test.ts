import { describe, expect, it } from "vitest"
import { buildModelRecommendations } from "../model-recommendations"
import type { SessionInsights } from "../session-insights"

const emptyInsights: SessionInsights = {
  totals: {
    generatedMessages: 0,
    totalTokens: 0,
    estimatedCostUsd: null
  },
  models: [],
  providers: [],
  topics: []
}

describe("model-recommendations", () => {
  it("recommends switching when image input is used without vision capability", () => {
    const recommendations = buildModelRecommendations({
      draftText: "Please analyze this image.",
      selectedModel: "gpt-4o-mini",
      modelCapabilities: ["tools", "streaming"],
      webSearch: false,
      jsonMode: false,
      hasImageAttachment: true,
      tokenBudgetRiskLevel: "low",
      sessionInsights: emptyInsights
    })

    expect(recommendations.some((rec) => rec.id === "vision-mismatch")).toBe(
      true
    )
    expect(
      recommendations.find((rec) => rec.id === "vision-mismatch")?.reason
    ).toContain("image attachment")
  })

  it("recommends JSON mode for structured output prompts", () => {
    const recommendations = buildModelRecommendations({
      draftText: "Return JSON object with fields name, risk, owner.",
      selectedModel: "gpt-4o-mini",
      modelCapabilities: ["tools", "streaming", "vision"],
      webSearch: false,
      jsonMode: false,
      hasImageAttachment: false,
      tokenBudgetRiskLevel: "low",
      sessionInsights: emptyInsights
    })

    expect(
      recommendations.some((rec) => rec.id === "structured-json-mode")
    ).toBe(true)
  })

  it("recommends stronger reasoning models for coding on small-tier models", () => {
    const recommendations = buildModelRecommendations({
      draftText: "Debug this TypeScript function and add tests.",
      selectedModel: "qwen2.5-7b-instruct",
      modelCapabilities: ["tools", "streaming"],
      webSearch: false,
      jsonMode: false,
      hasImageAttachment: false,
      tokenBudgetRiskLevel: "low",
      sessionInsights: emptyInsights
    })

    expect(
      recommendations.some((rec) => rec.id === "coding-reasoning-tier")
    ).toBe(true)
  })

  it("recommends cost review when high-tier model drives expensive sessions", () => {
    const recommendations = buildModelRecommendations({
      draftText: "Continue.",
      selectedModel: "gpt-4.1-pro",
      modelCapabilities: ["tools", "streaming", "vision"],
      webSearch: false,
      jsonMode: true,
      hasImageAttachment: false,
      tokenBudgetRiskLevel: "low",
      sessionInsights: {
        ...emptyInsights,
        totals: {
          generatedMessages: 12,
          totalTokens: 120000,
          estimatedCostUsd: 2.5
        }
      }
    })

    expect(recommendations.some((rec) => rec.id === "session-cost")).toBe(true)
  })
})
