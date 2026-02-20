import { describe, expect, it } from "vitest"
import {
  resolveMessageCostUsd,
  resolveMessageUsage
} from "../message-usage"

describe("message-usage", () => {
  it("resolves prompt/completion/total tokens from mixed generation payloads", () => {
    expect(
      resolveMessageUsage({
        prompt_eval_count: 120,
        eval_count: 55,
        usage: { total_tokens: 180 }
      })
    ).toEqual({
      promptTokens: 120,
      completionTokens: 55,
      totalTokens: 180
    })
  })

  it("falls back to usage fields when top-level values are absent", () => {
    expect(
      resolveMessageUsage({
        usage: {
          prompt_tokens: 80,
          completion_tokens: 20
        }
      })
    ).toEqual({
      promptTokens: 80,
      completionTokens: 20,
      totalTokens: 100
    })
  })

  it("resolves estimated cost from common cost fields", () => {
    expect(
      resolveMessageCostUsd({
        usage: {
          estimated_cost_usd: 0.0042
        }
      })
    ).toBe(0.0042)
    expect(
      resolveMessageCostUsd({
        pricing: {
          total_cost_usd: 0.0011
        }
      })
    ).toBe(0.0011)
  })
})
