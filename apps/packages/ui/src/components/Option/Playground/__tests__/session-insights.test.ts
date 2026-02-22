import { describe, expect, it } from "vitest"
import { buildSessionInsights } from "../session-insights"

describe("session-insights", () => {
  it("aggregates usage by provider/model and totals", () => {
    const insights = buildSessionInsights([
      {
        isBot: true,
        role: "assistant",
        message: "Answer one",
        modelName: "gpt-4o-mini",
        generationInfo: {
          resolved_provider: "openai",
          prompt_eval_count: 100,
          eval_count: 40
        }
      },
      {
        isBot: true,
        role: "assistant",
        message: "Answer two",
        modelName: "claude-3-5-sonnet",
        generationInfo: {
          resolved_provider: "anthropic",
          usage: {
            prompt_tokens: 70,
            completion_tokens: 30,
            total_tokens: 100,
            estimated_cost_usd: 0.02
          }
        }
      },
      {
        isBot: false,
        role: "user",
        message: "Need research citations and source evidence for migration plan"
      }
    ] as any[])

    expect(insights.totals.generatedMessages).toBe(2)
    expect(insights.totals.totalTokens).toBe(240)
    expect(insights.models).toHaveLength(2)
    expect(insights.providers).toHaveLength(2)
    expect(insights.providers[0]?.providerKey).toBe("openai")
    expect(insights.topics.some((topic) => topic.label === "research")).toBe(
      true
    )
  })

  it("skips assistant messages without token usage", () => {
    const insights = buildSessionInsights([
      {
        isBot: true,
        role: "assistant",
        message: "No usage payload",
        generationInfo: {}
      }
    ] as any[])

    expect(insights.totals.generatedMessages).toBe(0)
    expect(insights.models).toEqual([])
    expect(insights.providers).toEqual([])
  })
})
