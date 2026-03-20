import { describe, expect, it } from "vitest"

import type { ChatLinkedResearchRun } from "@/services/tldw/TldwApiClient"

import {
  type ChatLinkedResearchActionPolicy,
  getChatLinkedResearchActionPolicy,
  getChatReturnedResearchBannerState,
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
  it("derives a completed-run action policy", () => {
    const policy: ChatLinkedResearchActionPolicy =
      getChatLinkedResearchActionPolicy(
        buildRun({
          status: "completed",
          phase: "completed"
        })
      )

    expect(policy).toMatchObject({
      needsReview: false,
      reasonLabel: null,
      primaryActionKind: "open",
      primaryActionLabel: "Open in Research",
      canUseInChat: true,
      canFollowUp: true
    })
    expect(policy.researchHref).toContain("rs_test")
  })

  it("derives a checkpoint review action policy for plan review", () => {
    const policy = getChatLinkedResearchActionPolicy(
      buildRun({
        status: "waiting_human",
        phase: "awaiting_plan_review"
      })
    )

    expect(policy).toMatchObject({
      needsReview: true,
      reasonLabel: "Plan review needed",
      primaryActionKind: "review",
      primaryActionLabel: "Review in Research",
      canUseInChat: false,
      canFollowUp: false
    })
  })

  it("falls back to a generic review policy label for unknown review phases", () => {
    const policy = getChatLinkedResearchActionPolicy(
      buildRun({
        status: "waiting_human",
        phase: "awaiting_custom_review"
      })
    )

    expect(policy).toMatchObject({
      needsReview: true,
      reasonLabel: "Review needed",
      primaryActionKind: "review",
      primaryActionLabel: "Review in Research",
      canUseInChat: false,
      canFollowUp: false
    })
  })

  it("keeps running and failed runs conservative while preserving the research link", () => {
    const runningPolicy = getChatLinkedResearchActionPolicy(
      buildRun({
        status: "running",
        phase: "processing"
      })
    )
    const failedPolicy = getChatLinkedResearchActionPolicy(
      buildRun({
        status: "failed",
        phase: "failed"
      })
    )

    expect(runningPolicy).toMatchObject({
      needsReview: false,
      reasonLabel: null,
      primaryActionKind: "open",
      primaryActionLabel: "Open in Research",
      canUseInChat: false,
      canFollowUp: false
    })
    expect(failedPolicy).toMatchObject({
      needsReview: false,
      reasonLabel: null,
      primaryActionKind: "open",
      primaryActionLabel: "Open in Research",
      canUseInChat: false,
      canFollowUp: false
    })
    expect(runningPolicy.researchHref).toContain("rs_test")
    expect(failedPolicy.researchHref).toContain("rs_test")
  })

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

  it("derives a completed return-banner state for completed runs", () => {
    expect(
      getChatReturnedResearchBannerState({
        run: buildRun({
          status: "completed",
          phase: "completed"
        }),
        explicitReturn: true
      })
    ).toMatchObject({
      mode: "completed",
      primaryActionLabel: "Use in Chat",
      supportingText: null
    })
  })

  it("derives a review-required return-banner state for checkpoint-blocked runs", () => {
    expect(
      getChatReturnedResearchBannerState({
        run: buildRun({
          status: "waiting_human",
          phase: "awaiting_plan_review"
        }),
        explicitReturn: true
      })
    ).toMatchObject({
      mode: "review_required",
      primaryActionLabel: "Review in Research"
    })
  })

  it("derives a review-cleared return-banner state for explicit returns that no longer need review", () => {
    expect(
      getChatReturnedResearchBannerState({
        run: buildRun({
          status: "running",
          phase: "collecting"
        }),
        explicitReturn: true
      })
    ).toMatchObject({
      mode: "review_cleared",
      primaryActionLabel: "Continue with reviewed research",
      supportingText: "Your review is reflected in this run."
    })
  })

  it("falls back to a generic return-banner state when the run is not an explicit return", () => {
    expect(
      getChatReturnedResearchBannerState({
        run: buildRun({
          status: "running",
          phase: "collecting"
        }),
        explicitReturn: false
      })
    ).toMatchObject({
      mode: "generic",
      primaryActionLabel: "Open in Research",
      supportingText: null
    })
  })
})
