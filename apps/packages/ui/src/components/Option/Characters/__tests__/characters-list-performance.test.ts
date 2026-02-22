import { describe, expect, it } from "vitest"
import {
  CHARACTERS_LIST_PERF_TARGETS,
  computeP95,
  evaluateCharactersListPerfFixture,
  isCharactersListPerfFixturePassing
} from "../characters-list-performance"

const buildCharacters = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: String(index + 1),
    name: `Character ${index + 1}`,
    description: "A short description used for rendering checks.",
    tags: ["test", "performance", `bucket-${index % 5}`],
    avatar_url: `https://example.com/avatar/${index + 1}.png`
  }))

describe("characters-list-performance", () => {
  it("computes p95 using nearest-rank", () => {
    expect(computeP95([10, 20, 30, 40, 50])).toBe(50)
    expect(computeP95([])).toBe(0)
  })

  it("passes baseline fixture for 200-character list interactions", () => {
    const report = evaluateCharactersListPerfFixture({
      fixture_name: "characters-200-baseline",
      list_payload: {
        page: 1,
        page_size: 100,
        total: 200,
        has_more: true,
        items: buildCharacters(100)
      },
      initial_render_latencies_ms: [140, 160, 170, 180, 200, 210],
      interaction_latencies_ms: [50, 58, 60, 62, 70, 85]
    })

    expect(report.list_payload_bytes).toBeLessThanOrEqual(
      CHARACTERS_LIST_PERF_TARGETS.list_payload_max_bytes
    )
    expect(report.initial_render.p95).toBeLessThanOrEqual(
      CHARACTERS_LIST_PERF_TARGETS.initial_render_p95_ms
    )
    expect(report.interaction.p95).toBeLessThanOrEqual(
      CHARACTERS_LIST_PERF_TARGETS.interaction_p95_ms
    )
    expect(isCharactersListPerfFixturePassing(report)).toBe(true)
  })

  it("fails gates when payloads and latency exceed targets", () => {
    const report = evaluateCharactersListPerfFixture({
      fixture_name: "characters-oversized",
      list_payload: {
        page: 1,
        page_size: 100,
        total: 100,
        has_more: false,
        items: buildCharacters(100).map((character) => ({
          ...character,
          image_base64: "a".repeat(20_000)
        }))
      },
      initial_render_latencies_ms: [120, 180, 260, 280, 310],
      interaction_latencies_ms: [40, 55, 75, 130, 190]
    })

    expect(report.checks.list_payload_within_limit).toBe(false)
    expect(report.checks.initial_render_within_target).toBe(false)
    expect(report.checks.interaction_within_target).toBe(false)
    expect(isCharactersListPerfFixturePassing(report)).toBe(false)
  })
})
