import { describe, expect, it } from "vitest"
import {
  buildConversationSummaryCheckpointPrompt,
  evaluateSummaryCheckpointSuggestion
} from "../conversation-summary-checkpoint"

describe("conversation-summary-checkpoint", () => {
  it("builds a checkpoint prompt from recent conversation messages", () => {
    const prompt = buildConversationSummaryCheckpointPrompt([
      { isBot: false, role: "user", name: "You", message: "Plan a migration." } as any,
      {
        isBot: true,
        role: "assistant",
        name: "Assistant",
        message: "Use a staged rollout with validation checkpoints."
      } as any
    ])

    expect(prompt).toContain("Create a checkpoint summary")
    expect(prompt).toContain("1. User: Plan a migration.")
    expect(prompt).toContain(
      "2. Assistant: Use a staged rollout with validation checkpoints."
    )
    expect(prompt).toContain("Sources that must remain pinned")
  })

  it("suggests checkpointing when the token budget is near or over limit", () => {
    const suggestion = evaluateSummaryCheckpointSuggestion({
      messageCount: 4,
      projectedBudget: {
        projectedTotalTokens: 3800,
        remainingTokens: 200,
        utilizationPercent: 95,
        isNearLimit: true,
        isOverLimit: false
      }
    })

    expect(suggestion).toEqual({
      shouldSuggest: true,
      reason: "token-budget"
    })
  })

  it("suggests checkpointing for long threads with high utilization", () => {
    const suggestion = evaluateSummaryCheckpointSuggestion({
      messageCount: 10,
      projectedBudget: {
        projectedTotalTokens: 2900,
        remainingTokens: 1200,
        utilizationPercent: 73,
        isNearLimit: false,
        isOverLimit: false
      }
    })

    expect(suggestion).toEqual({
      shouldSuggest: true,
      reason: "message-volume"
    })
  })

  it("does not suggest checkpointing when thread and usage are small", () => {
    const suggestion = evaluateSummaryCheckpointSuggestion({
      messageCount: 3,
      projectedBudget: {
        projectedTotalTokens: 900,
        remainingTokens: 3200,
        utilizationPercent: 22,
        isNearLimit: false,
        isOverLimit: false
      }
    })

    expect(suggestion).toEqual({
      shouldSuggest: false,
      reason: null
    })
  })
})
