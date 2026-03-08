import { describe, it, expect } from "vitest"
import {
  estimateIngestSeconds,
  estimateTotalSeconds,
  formatEstimate,
} from "../timeEstimation"
import type { WizardQueueItem } from "../types"

// ---------------------------------------------------------------------------
// estimateIngestSeconds
// ---------------------------------------------------------------------------

describe("estimateIngestSeconds", () => {
  const mediaTypes = ["audio", "video", "document", "pdf", "ebook", "image", "web"]

  it.each(mediaTypes)(
    "returns a positive number for media type '%s'",
    (type) => {
      const result = estimateIngestSeconds(10_000_000, type, "standard")
      expect(result).toBeGreaterThan(0)
    }
  )

  it("quick preset gives roughly 0.5x the standard estimate", () => {
    const size = 5_000_000
    const standard = estimateIngestSeconds(size, "audio", "standard")
    const quick = estimateIngestSeconds(size, "audio", "quick")
    // quick multiplier is 0.5, standard is 1.0
    expect(quick).toBeCloseTo(standard * 0.5, 5)
  })

  it("deep preset gives roughly 2.5x the standard estimate", () => {
    const size = 5_000_000
    const standard = estimateIngestSeconds(size, "video", "standard")
    const deep = estimateIngestSeconds(size, "video", "deep")
    expect(deep).toBeCloseTo(standard * 2.5, 5)
  })

  it("returns baseline for URLs with zero fileSize", () => {
    const result = estimateIngestSeconds(0, "web", "standard")
    // web estimator ignores size, returns 8 * 1.0
    expect(result).toBe(8)
  })

  it("returns default (5s * multiplier) for unknown media type", () => {
    const result = estimateIngestSeconds(0, "alien_format", "standard")
    expect(result).toBe(5) // 5 * 1.0
  })

  it("returns default * quick multiplier for unknown type with quick preset", () => {
    const result = estimateIngestSeconds(0, "alien_format", "quick")
    expect(result).toBe(2.5) // 5 * 0.5
  })

  it("uses default multiplier 1.0 for unrecognized preset", () => {
    const result = estimateIngestSeconds(0, "web", "turbo")
    expect(result).toBe(8) // 8 * 1.0
  })

  it("never returns a negative number", () => {
    const result = estimateIngestSeconds(0, "document", "quick")
    expect(result).toBeGreaterThanOrEqual(0)
  })
})

// ---------------------------------------------------------------------------
// estimateTotalSeconds
// ---------------------------------------------------------------------------

describe("estimateTotalSeconds", () => {
  const makeItem = (
    id: string,
    detectedType: string,
    fileSize: number
  ): WizardQueueItem => ({
    id,
    detectedType: detectedType as WizardQueueItem["detectedType"],
    fileSize,
    icon: "file",
    validation: { valid: true },
  })

  it("sums individual estimates correctly", () => {
    const items = [
      makeItem("1", "audio", 1_000_000),
      makeItem("2", "document", 2_000_000),
    ]
    const total = estimateTotalSeconds(items, "standard")
    const expected =
      estimateIngestSeconds(1_000_000, "audio", "standard") +
      estimateIngestSeconds(2_000_000, "document", "standard")
    expect(total).toBeCloseTo(expected, 5)
  })

  it("returns 0 for an empty array", () => {
    expect(estimateTotalSeconds([], "standard")).toBe(0)
  })

  it("works with a single item", () => {
    const items = [makeItem("1", "pdf", 500_000)]
    const total = estimateTotalSeconds(items, "deep")
    const expected = estimateIngestSeconds(500_000, "pdf", "deep")
    expect(total).toBeCloseTo(expected, 5)
  })
})

// ---------------------------------------------------------------------------
// formatEstimate
// ---------------------------------------------------------------------------

describe("formatEstimate", () => {
  it("shows seconds for values under 60", () => {
    expect(formatEstimate(5)).toBe("~5 sec")
    expect(formatEstimate(0)).toBe("~0 sec")
    expect(formatEstimate(59)).toBe("~59 sec")
  })

  it("shows minutes for values from 60 to 3599", () => {
    expect(formatEstimate(60)).toBe("~1 min")
    expect(formatEstimate(120)).toBe("~2 min")
    expect(formatEstimate(3599)).toMatch(/~\d+ min/)
  })

  it("shows hours for values >= 3600", () => {
    expect(formatEstimate(3600)).toBe("~1 hr")
    expect(formatEstimate(7200)).toBe("~2 hr")
  })

  it("rounds fractional seconds", () => {
    expect(formatEstimate(4.7)).toBe("~5 sec")
    expect(formatEstimate(0.3)).toBe("~0 sec")
  })
})
