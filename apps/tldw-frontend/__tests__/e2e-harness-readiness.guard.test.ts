import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readSource = (relativePath: string) =>
  readFileSync(path.join(process.cwd(), relativePath), "utf8")

describe("e2e harness readiness contracts", () => {
  it("keeps smoke and review harnesses off direct networkidle waits", () => {
    const smokeSource = readSource("e2e/smoke/all-pages.spec.ts")
    const reviewSource = readSource("e2e/review/parallel-review.spec.ts")

    expect(smokeSource).toContain("waitForAppShell")
    expect(reviewSource).toContain("waitForAppShell")
    expect(smokeSource).not.toContain("waitForLoadState('networkidle'")
    expect(reviewSource).not.toContain('waitForLoadState("networkidle"')
  })

  it("keeps BasePage state change checks on polling instead of fixed sleeps", () => {
    const basePageSource = readSource("e2e/utils/page-objects/BasePage.ts")

    expect(basePageSource).toContain("expect\n                .poll")
    expect(basePageSource).not.toContain("waitForTimeout(500)")
  })

  it("keeps journey helpers on explicit quick-ingest and stream readiness markers", () => {
    const helperSource = readSource("e2e/utils/journey-helpers.ts")

    expect(helperSource).toContain("wizard-results-step")
    expect(helperSource).toContain("quick-ingest-complete")
    expect(helperSource).toContain("/api/v1/media/ingest/jobs/")
    expect(helperSource).toContain("article[aria-label*='Assistant message']")
    expect(helperSource).toContain("Generating response")
    expect(helperSource).not.toContain("waitForTimeout(1_000)")
  })

  it("keeps the media review workflow off fixed sleeps", () => {
    const mediaReviewSource = readSource("e2e/workflows/media-review.spec.ts")

    expect(mediaReviewSource).not.toContain("waitForTimeout(")
    expect(mediaReviewSource).toContain("expect\n        .poll")
  })

  it("keeps refreshed journey workflows off blind timeout waits", () => {
    const characterJourneySource = readSource("e2e/workflows/journeys/character-chat.spec.ts")
    const ingestSearchChatSource = readSource("e2e/workflows/journeys/ingest-search-chat.spec.ts")
    const ingestEvaluateReviewSource = readSource("e2e/workflows/journeys/ingest-evaluate-review.spec.ts")

    expect(characterJourneySource).not.toContain("waitForTimeout(")
    expect(ingestSearchChatSource).not.toContain("waitForTimeout(")
    expect(ingestEvaluateReviewSource).not.toContain("waitForTimeout(")
  })
})
