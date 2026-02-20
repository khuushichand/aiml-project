import { describe, expect, it } from "vitest"
import {
  aggregateSessionUsage,
  projectTokenBudget,
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
})
