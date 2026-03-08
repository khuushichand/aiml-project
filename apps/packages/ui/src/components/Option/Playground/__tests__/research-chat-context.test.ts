import { describe, expect, it } from "vitest"

import {
  applyAttachedResearchContextEdits,
  deriveAttachedResearchContext,
  isDeepResearchCompletionMetadata,
  resetAttachedResearchContext,
  sanitizeAttachedResearchContext,
  toChatResearchContext
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

  it("sanitizes and applies attached research context edits without mutating identity fields", () => {
    const active = {
      attached_at: "2026-03-08T20:00:00Z",
      run_id: "run_123",
      query: "Battery recycling supply chain",
      question: "Battery recycling supply chain",
      outline: [{ title: "Overview" }],
      key_claims: [{ text: "Claim one" }],
      unresolved_questions: ["What changed in Europe?"],
      verification_summary: { unsupported_claim_count: 0 },
      source_trust_summary: { high_trust_count: 2 },
      research_url: "/research?run=run_123"
    } as const

    const edited = applyAttachedResearchContextEdits(active, {
      question: "  Edited question  ",
      outline: [{ title: " Updated overview " }, { title: "   " }],
      key_claims: [{ text: " Edited claim " }, { text: " " }],
      unresolved_questions: ["  Follow-up  ", ""],
      verification_summary: { unsupported_claim_count: 3 },
      source_trust_summary: { high_trust_count: 5 },
      run_id: "run_mutated",
      query: "mutated query",
      research_url: "/research?run=mutated"
    })

    expect(edited).toMatchObject({
      run_id: "run_123",
      query: "Battery recycling supply chain",
      research_url: "/research?run=run_123",
      question: "Edited question",
      outline: [{ title: "Updated overview" }],
      key_claims: [{ text: "Edited claim" }],
      unresolved_questions: ["Follow-up"],
      verification_summary: { unsupported_claim_count: 3 },
      source_trust_summary: { high_trust_count: 5 }
    })
    expect(toChatResearchContext(edited)).toMatchObject({
      run_id: "run_123",
      question: "Edited question",
      outline: [{ title: "Updated overview" }]
    })
  })

  it("sanitizes a draft and resets back to the run-derived baseline", () => {
    const baseline = {
      attached_at: "2026-03-08T20:00:00Z",
      run_id: "run_123",
      query: "Battery recycling supply chain",
      question: "Battery recycling supply chain",
      outline: [{ title: "Overview" }],
      key_claims: [{ text: "Claim one" }],
      unresolved_questions: ["What changed in Europe?"],
      verification_summary: { unsupported_claim_count: 0 },
      source_trust_summary: { high_trust_count: 2 },
      research_url: "/research?run=run_123"
    } as const

    expect(
      sanitizeAttachedResearchContext({
        ...baseline,
        question: "   ",
        outline: [{ title: " " }, { title: "Regional shifts" }],
        key_claims: [{ text: " " }, { text: "Claim two" }],
        unresolved_questions: [" ", "Question two"]
      })
    ).toMatchObject({
      question: "Battery recycling supply chain",
      outline: [{ title: "Regional shifts" }],
      key_claims: [{ text: "Claim two" }],
      unresolved_questions: ["Question two"]
    })

    expect(resetAttachedResearchContext(baseline)).toEqual(baseline)
    expect(resetAttachedResearchContext(null)).toBeNull()
  })
})
