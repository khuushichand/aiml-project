import { describe, expect, it } from "vitest"

import type { ChatLinkedResearchRun } from "@/services/tldw/TldwApiClient"

import {
  getChatLinkedResearchReviewReason,
  isCheckpointReviewRun
} from "../research-run-status"

const buildRun = (
  overrides: Partial<ChatLinkedResearchRun> = {}
): ChatLinkedResearchRun => ({
  run_id: "rs_test",
  query: "Test query",
  status: "running",
  phase: "processing",
  control_state: "running",
  latest_checkpoint_id: null,
  updated_at: "2026-03-19T20:03:00+00:00",
  ...overrides
})

describe("research-run-status", () => {
  it("detects checkpoint review eligibility for waiting_human review phases", () => {
    expect(
      isCheckpointReviewRun(
        buildRun({ status: "waiting_human", phase: "awaiting_plan_review" })
      )
    ).toBe(true)
    expect(
      isCheckpointReviewRun(
        buildRun({ status: "waiting_human", phase: "awaiting_custom_review" })
      )
    ).toBe(true)
    expect(
      isCheckpointReviewRun(
        buildRun({ status: "waiting_human", phase: "processing" })
      )
    ).toBe(false)
    expect(
      isCheckpointReviewRun(
        buildRun({ status: "completed", phase: "awaiting_plan_review" })
      )
    ).toBe(false)
  })

  it("derives a plan review reason label", () => {
    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "waiting_human",
          phase: "awaiting_plan_review"
        })
      )
    ).toBe("Plan review needed")
  })

  it("derives a sources review reason label for singular and plural phases", () => {
    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "waiting_human",
          phase: "awaiting_source_review"
        })
      )
    ).toBe("Sources review needed")

    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "waiting_human",
          phase: "awaiting_sources_review"
        })
      )
    ).toBe("Sources review needed")
  })

  it("derives an outline review reason label", () => {
    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "waiting_human",
          phase: "awaiting_outline_review"
        })
      )
    ).toBe("Outline review needed")
  })

  it("falls back to a generic review label for unknown waiting_human phases", () => {
    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "waiting_human",
          phase: "awaiting_custom_review"
        })
      )
    ).toBe("Review needed")
  })

  it("returns null for non-review runs", () => {
    expect(
      getChatLinkedResearchReviewReason(
        buildRun({
          status: "completed",
          phase: "completed"
        })
      )
    ).toBeNull()
  })
})
