import { describe, expect, it } from "vitest"

import {
  deriveAttachedResearchContext,
  isDeepResearchCompletionMetadata
} from "../research-chat-context"

describe("research-chat-context", () => {
  it("derives a bounded attached context from a completed research bundle", () => {
    const context = deriveAttachedResearchContext(
      {
        question: "What changed in the battery recycling market?",
        outline: {
          sections: [
            { title: "Overview" },
            { title: "Regional shifts" }
          ]
        },
        claims: [
          { text: "Claim 1" },
          { text: "Claim 2" },
          { text: "Claim 3" },
          { text: "Claim 4" },
          { text: "Claim 5" },
          { text: "Claim 6" }
        ],
        unresolved_questions: [
          "Question 1",
          "Question 2",
          "Question 3",
          "Question 4",
          "Question 5",
          "Question 6"
        ],
        verification_summary: {
          unsupported_claim_count: 2
        },
        source_trust: [
          { source_id: "src_high_1", trust_tier: "high" },
          { source_id: "src_medium", trust_tier: "medium" },
          { source_id: "src_high_2", trust_tier: "HIGH" }
        ],
        report_markdown: "# Full report",
        source_inventory: [{ source_id: "src_high_1" }]
      },
      "run_123",
      "battery recycling supply chain"
    )

    expect(context).toMatchObject({
      run_id: "run_123",
      query: "battery recycling supply chain",
      question: "What changed in the battery recycling market?",
      outline: [{ title: "Overview" }, { title: "Regional shifts" }],
      key_claims: [
        { text: "Claim 1" },
        { text: "Claim 2" },
        { text: "Claim 3" },
        { text: "Claim 4" },
        { text: "Claim 5" }
      ],
      unresolved_questions: [
        "Question 1",
        "Question 2",
        "Question 3",
        "Question 4",
        "Question 5"
      ],
      verification_summary: {
        unsupported_claim_count: 2
      },
      source_trust_summary: {
        high_trust_count: 2
      },
      research_url: "/research?run=run_123"
    })
    expect(context.attached_at).toEqual(expect.any(String))
    expect("report_markdown" in context).toBe(false)
    expect("source_inventory" in context).toBe(false)
    expect(context.key_claims).toHaveLength(5)
    expect(context.unresolved_questions).toHaveLength(5)
  })

  it("recognizes deep research completion handoff metadata", () => {
    expect(
      isDeepResearchCompletionMetadata({
        run_id: "run_123",
        query: "battery recycling supply chain",
        kind: "completion_handoff"
      })
    ).toBe(true)
    expect(
      isDeepResearchCompletionMetadata({
        run_id: "run_123",
        query: "battery recycling supply chain",
        kind: "other"
      })
    ).toBe(false)
    expect(isDeepResearchCompletionMetadata(null)).toBe(false)
  })
})
