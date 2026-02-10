import { describe, expect, it } from "vitest"

import {
  MEDIA_NAVIGATION_PERF_TARGETS,
  computePercentile,
  estimatePayloadSizeBytes,
  evaluateMediaNavigationPerfFixture,
  isMediaNavigationPerfFixturePassing
} from "@/utils/media-navigation-performance"

const buildNavigationFixture = (nodeCount: number) =>
  Array.from({ length: nodeCount }, (_, index) => ({
    id: `n-${index}`,
    parent_id: index === 0 ? null : `n-${Math.max(0, index - 1)}`,
    level: Math.min(4, Math.floor(index / 5)),
    title: `Section ${index}`,
    order: index,
    path_label: `${index + 1}`,
    target_type: "char_range",
    target_start: index * 100,
    target_end: index * 100 + 50
  }))

describe("media-navigation-performance", () => {
  it("computes percentile with nearest-rank behavior", () => {
    const values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    expect(computePercentile(values, 50)).toBe(50)
    expect(computePercentile(values, 95)).toBe(100)
    expect(computePercentile(values, 0)).toBe(10)
  })

  it("estimates utf8 payload bytes from serialized payload", () => {
    const bytes = estimatePayloadSizeBytes({ value: "hello" })
    expect(bytes).toBeGreaterThan(0)
  })

  it("passes fixture gates under baseline limits", () => {
    const navigationPayload = {
      media_id: 123,
      nodes: buildNavigationFixture(120),
      stats: {
        returned_node_count: 120,
        node_count: 120,
        truncated: false
      }
    }
    const sectionPayload = {
      content_format: "markdown",
      content: "A".repeat(10_000)
    }

    const report = evaluateMediaNavigationPerfFixture({
      fixture_name: "baseline-warm",
      cache_state: "warm",
      navigation_payload: navigationPayload,
      section_payload: sectionPayload,
      navigation_latencies_ms: [180, 190, 210, 220, 240, 250, 260],
      section_switch_latencies_ms: [90, 100, 120, 130, 140, 150, 160]
    })

    expect(report.cache_state).toBe("warm")
    expect(report.navigation_payload_bytes).toBeLessThanOrEqual(
      MEDIA_NAVIGATION_PERF_TARGETS.navigation_payload_max_bytes
    )
    expect(report.section_payload_bytes).toBeLessThanOrEqual(
      MEDIA_NAVIGATION_PERF_TARGETS.section_payload_max_bytes
    )
    expect(isMediaNavigationPerfFixturePassing(report)).toBe(true)
  })

  it("fails fixture gates when payload or p95 latency breaches limits", () => {
    const report = evaluateMediaNavigationPerfFixture({
      fixture_name: "oversized-cold",
      cache_state: "cold",
      navigation_payload: {
        media_id: 456,
        nodes: buildNavigationFixture(800),
        // Inflate payload intentionally above limit
        extra: "x".repeat(300_000)
      },
      section_payload: {
        content_format: "html",
        content: "z".repeat(90_000)
      },
      navigation_latencies_ms: [120, 180, 250, 410, 430, 450],
      section_switch_latencies_ms: [120, 140, 200, 260, 280, 300],
      payload_truncated: true
    })

    expect(report.payload_truncated).toBe(true)
    expect(report.checks.navigation_payload_within_limit).toBe(false)
    expect(report.checks.section_payload_within_limit).toBe(false)
    expect(report.checks.navigation_p95_within_target).toBe(false)
    expect(report.checks.section_switch_p95_within_target).toBe(false)
    expect(isMediaNavigationPerfFixturePassing(report)).toBe(false)
  })
})
