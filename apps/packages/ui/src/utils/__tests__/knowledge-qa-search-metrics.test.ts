import { beforeEach, describe, expect, it, vi } from "vitest"

const storageMap = new Map<string, unknown>()

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: async (key: string) => storageMap.get(key),
    set: async (key: string, value: unknown) => {
      storageMap.set(key, value)
    },
    remove: async (key: string) => {
      storageMap.delete(key)
    },
  }),
}))

describe("knowledge-qa-search-metrics", () => {
  beforeEach(() => {
    storageMap.clear()
  })

  it("tracks completion latency and feedback events", async () => {
    const { trackKnowledgeQaSearchMetric } = await import(
      "@/utils/knowledge-qa-search-metrics"
    )

    await trackKnowledgeQaSearchMetric({ type: "search_submit", query_length: 22 })
    await trackKnowledgeQaSearchMetric({
      type: "search_complete",
      duration_ms: 1350,
      result_count: 4,
      has_answer: true,
      used_streaming: true,
    })
    await trackKnowledgeQaSearchMetric({
      type: "answer_feedback_submit",
      helpful: true,
    })
    await trackKnowledgeQaSearchMetric({
      type: "source_feedback_submit",
      relevant: false,
    })

    const stored = storageMap.get("knowledgeQaSearchMetrics") as Record<string, unknown>

    expect(stored.submitCount).toBe(1)
    expect(stored.completeCount).toBe(1)
    expect(stored.totalSearchDurationMs).toBe(1350)
    expect(stored.answerFeedbackCount).toBe(1)
    expect(stored.sourceFeedbackCount).toBe(1)
    expect(Array.isArray(stored.recentEvents)).toBe(true)
    expect((stored.recentEvents as Array<{ type: string }>)[1]?.type).toBe(
      "search_complete"
    )
  })

  it("tracks workspace handoff and suggestion acceptance", async () => {
    const { trackKnowledgeQaSearchMetric } = await import(
      "@/utils/knowledge-qa-search-metrics"
    )

    await trackKnowledgeQaSearchMetric({
      type: "workspace_handoff",
      source_count: 7,
    })
    await trackKnowledgeQaSearchMetric({
      type: "suggestion_accept",
      source: "history",
    })

    const stored = storageMap.get("knowledgeQaSearchMetrics") as Record<string, unknown>
    expect(stored.workspaceHandoffCount).toBe(1)
    expect(stored.suggestionAcceptCount).toBe(1)
  })
})
