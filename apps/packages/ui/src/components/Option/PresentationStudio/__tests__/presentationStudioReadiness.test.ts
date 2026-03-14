import { describe, expect, it } from "vitest"

import {
  deriveDeckReadiness,
  describeSlideReadiness,
  formatNarrationDuration
} from "../presentationStudioReadiness"
import type { PresentationStudioEditorSlide } from "@/store/presentation-studio"

const createSlide = (
  overrides: Partial<PresentationStudioEditorSlide> & {
    metadata?: Record<string, any>
  }
): PresentationStudioEditorSlide => ({
  order: 0,
  layout: "content",
  title: "Slide",
  content: "Content",
  speaker_notes: "Narration",
  metadata: {
    studio: {
      slideId: "slide-1",
      audio: {
        status: "missing"
      },
      image: {
        status: "missing"
      }
    }
  },
  ...overrides
})

describe("presentationStudioReadiness", () => {
  it("formats narration duration for short and long clips", () => {
    expect(formatNarrationDuration(18_000)).toBe("18s")
    expect(formatNarrationDuration(92_000)).toBe("1m 32s")
    expect(formatNarrationDuration(null)).toBe("Unknown until audio is generated")
  })

  it("describes slide readiness issues and narration timing", () => {
    const readiness = describeSlideReadiness(
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-1",
            audio: {
              status: "stale",
              duration_ms: 92_000
            },
            image: {
              status: "missing"
            }
          }
        }
      })
    )

    expect(readiness.summaryLabel).toBe("Needs attention")
    expect(readiness.narrationTiming).toBe("1m 32s")
    expect(readiness.issues).toEqual([
      "Refresh narration to match the latest script changes.",
      "Add or generate a slide image before publishing."
    ])
  })

  it("prefers manual slide timing over narration duration when present", () => {
    const readiness = describeSlideReadiness(
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-manual",
            transition: "wipe",
            timing_mode: "manual",
            manual_duration_ms: 45_000,
            audio: { status: "ready", duration_ms: 18_000, asset_ref: "output:1" },
            image: { status: "ready", asset_ref: "output:2" }
          }
        }
      })
    )

    expect((readiness as any).effectiveTiming).toBe("45s")
    expect((readiness as any).transitionLabel).toBe("Wipe")
  })

  it("summarizes deck readiness counts", () => {
    const deckReadiness = deriveDeckReadiness([
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-ready",
            audio: { status: "ready", duration_ms: 18_000, asset_ref: "output:1" },
            image: { status: "ready", asset_ref: "output:2" }
          }
        }
      }),
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-stale",
            audio: { status: "stale", duration_ms: 32_000 },
            image: { status: "ready", asset_ref: "output:3" }
          }
        }
      }),
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-missing",
            audio: { status: "missing" },
            image: { status: "missing" }
          }
        }
      })
    ])

    expect(deckReadiness.readySlides).toBe(1)
    expect(deckReadiness.slidesMissingImages).toBe(1)
    expect(deckReadiness.slidesWithStaleNarration).toBe(1)
    expect(deckReadiness.slidesMissingNarration).toBe(1)
    expect(deckReadiness.totalNarrationDuration).toBe("50s")
  })

  it("summarizes total deck runtime using manual timing overrides", () => {
    const deckReadiness = deriveDeckReadiness([
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-auto",
            timing_mode: "auto",
            audio: { status: "ready", duration_ms: 18_000, asset_ref: "output:1" },
            image: { status: "ready", asset_ref: "output:2" }
          }
        }
      }),
      createSlide({
        metadata: {
          studio: {
            slideId: "slide-manual",
            timing_mode: "manual",
            manual_duration_ms: 45_000,
            audio: { status: "ready", duration_ms: 12_000, asset_ref: "output:3" },
            image: { status: "ready", asset_ref: "output:4" }
          }
        }
      })
    ])

    expect((deckReadiness as any).totalDeckDuration).toBe("1m 3s")
  })
})
