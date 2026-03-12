import { describe, expect, it } from "vitest"

import {
  applyAttachedResearchContextEdits,
  clearAttachedResearchContext,
  deriveAttachedResearchContext,
  isDeepResearchCompletionMetadata,
  resetAttachedResearchContext,
  setAttachedResearchContextActive,
  sanitizeAttachedResearchContext,
  type AttachedResearchContext,
  toChatResearchContext
} from "../research-chat-context"

describe("research-chat-context", () => {
  const buildContext = (
    runId: string,
    overrides: Partial<AttachedResearchContext> = {}
  ): AttachedResearchContext => ({
    attached_at: "2026-03-08T20:00:00Z",
    run_id: runId,
    query: `Query for ${runId}`,
    question: `Question for ${runId}`,
    outline: [{ title: `Outline ${runId}` }],
    key_claims: [{ text: `Claim ${runId}` }],
    unresolved_questions: [`Question ${runId}`],
    verification_summary: { unsupported_claim_count: 0 },
    source_trust_summary: { high_trust_count: 1 },
    research_url: `/research?run=${runId}`,
    ...overrides
  })

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

  it("attaching a different run pushes the old active attachment into history and resets baseline", () => {
    const active = buildContext("run_active")
    const prior = buildContext("run_prior", {
      attached_at: "2026-03-08T19:00:00Z"
    })
    const next = buildContext("run_next", {
      attached_at: "2026-03-08T21:00:00Z"
    })

    const transitioned = setAttachedResearchContextActive({
      active,
      baseline: active,
      history: [prior],
      nextActive: next
    })

    expect(transitioned.active).toEqual(next)
    expect(transitioned.baseline).toEqual(next)
    expect(transitioned.history.map((entry) => entry.run_id)).toEqual([
      "run_active",
      "run_prior"
    ])
  })

  it("attaching the same run_id updates active and baseline without churning history", () => {
    const active = buildContext("run_same", {
      question: "Original question"
    })
    const history = [buildContext("run_prior")]
    const replacement = buildContext("run_same", {
      question: "Replacement question"
    })

    const transitioned = setAttachedResearchContextActive({
      active,
      baseline: active,
      history,
      nextActive: replacement
    })

    expect(transitioned.active?.question).toBe("Replacement question")
    expect(transitioned.baseline?.question).toBe("Replacement question")
    expect(transitioned.history.map((entry) => entry.run_id)).toEqual([
      "run_prior"
    ])
  })

  it("restoring a history entry swaps it into active immediately and keeps history deduped", () => {
    const active = buildContext("run_active")
    const history = [
      buildContext("run_restore", { attached_at: "2026-03-08T21:00:00Z" }),
      buildContext("run_old", { attached_at: "2026-03-08T19:00:00Z" })
    ]

    const transitioned = setAttachedResearchContextActive({
      active,
      baseline: active,
      history,
      nextActive: history[0]
    })

    expect(transitioned.active?.run_id).toBe("run_restore")
    expect(transitioned.baseline?.run_id).toBe("run_restore")
    expect(transitioned.history.map((entry) => entry.run_id)).toEqual([
      "run_active",
      "run_old"
    ])
  })

  it("removing the active attachment preserves history and clears baseline", () => {
    const active = buildContext("run_active")
    const history = [buildContext("run_prior")]

    const cleared = clearAttachedResearchContext({
      active,
      baseline: active,
      history
    })

    expect(cleared.active).toBeNull()
    expect(cleared.baseline).toBeNull()
    expect(cleared.history.map((entry) => entry.run_id)).toEqual(["run_prior"])
  })

  it("caps history at three entries after repeated swaps", () => {
    const active = buildContext("run_active")
    const history = [
      buildContext("run_hist_1", { attached_at: "2026-03-08T19:00:00Z" }),
      buildContext("run_hist_2", { attached_at: "2026-03-08T18:00:00Z" }),
      buildContext("run_hist_3", { attached_at: "2026-03-08T17:00:00Z" })
    ]
    const next = buildContext("run_next", { attached_at: "2026-03-08T21:00:00Z" })

    const transitioned = setAttachedResearchContextActive({
      active,
      baseline: active,
      history,
      nextActive: next
    })

    expect(transitioned.history.map((entry) => entry.run_id)).toEqual([
      "run_active",
      "run_hist_1",
      "run_hist_2"
    ])
  })
})
