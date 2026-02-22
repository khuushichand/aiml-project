import { describe, expect, it } from "vitest"
import {
  aggregateSessionUsage,
  projectTokenBudget,
  resolveTokenBudgetRisk,
  resolveGenerationUsage
} from "../usage-metrics"

describe("usage-metrics", () => {
  it("resolves usage fields from mixed generation info payloads", () => {
    expect(
      resolveGenerationUsage({
        prompt_eval_count: 120,
        eval_count: 80,
        usage: { total_tokens: 205 }
      })
    ).toEqual({
      inputTokens: 120,
      outputTokens: 80,
      totalTokens: 205
    })
  })

  it("aggregates session usage from message generation info", () => {
    const summary = aggregateSessionUsage([
      {
        generationInfo: {
          prompt_eval_count: 100,
          eval_count: 40
        }
      },
      {
        generationInfo: {
          usage: {
            prompt_tokens: 60,
            completion_tokens: 20,
            total_tokens: 80
          }
        }
      }
    ])

    expect(summary.inputTokens).toBe(160)
    expect(summary.outputTokens).toBe(60)
    expect(summary.totalTokens).toBe(220)
    expect(summary.estimatedCostUsd).toBeNull()
  })

  it("calculates near-limit and over-limit projections", () => {
    const nearLimit = projectTokenBudget({
      conversationTokens: 3400,
      draftTokens: 300,
      maxTokens: 4096
    })
    expect(nearLimit.isNearLimit).toBe(true)
    expect(nearLimit.isOverLimit).toBe(false)

    const overLimit = projectTokenBudget({
      conversationTokens: 3900,
      draftTokens: 500,
      maxTokens: 4096
    })
    expect(overLimit.isOverLimit).toBe(true)
    expect(overLimit.remainingTokens).toBeLessThan(0)
  })

  it("derives truncation risk labels from projected budget", () => {
    expect(
      resolveTokenBudgetRisk({
        projectedTotalTokens: 1600,
        remainingTokens: 2400,
        utilizationPercent: 40,
        isNearLimit: false,
        isOverLimit: false
      })
    ).toEqual({
      level: "low",
      overflowTokens: 0
    })

    expect(
      resolveTokenBudgetRisk({
        projectedTotalTokens: 3400,
        remainingTokens: 696,
        utilizationPercent: 83,
        isNearLimit: false,
        isOverLimit: false
      })
    ).toEqual({
      level: "medium",
      overflowTokens: 0
    })

    expect(
      resolveTokenBudgetRisk({
        projectedTotalTokens: 4400,
        remainingTokens: -304,
        utilizationPercent: 107,
        isNearLimit: false,
        isOverLimit: true
      })
    ).toEqual({
      level: "critical",
      overflowTokens: 304
    })
  })
})
