import { describe, expect, it } from "vitest"
import { runWatchlistsScaleBenchmark } from "../scale-benchmark"
import {
  WATCHLISTS_SCALE_PROFILES,
  WATCHLISTS_SURFACE_PERFORMANCE_BUDGETS
} from "../scale-profiles"

describe("watchlists scale profiles and benchmark harness", () => {
  it("defines ascending profile volumes for feeds, monitors, runs, and items", () => {
    const small = WATCHLISTS_SCALE_PROFILES.small
    const team = WATCHLISTS_SCALE_PROFILES.team
    const large = WATCHLISTS_SCALE_PROFILES.large

    expect(team.feeds).toBeGreaterThan(small.feeds)
    expect(large.feeds).toBeGreaterThan(team.feeds)
    expect(team.monitors).toBeGreaterThan(small.monitors)
    expect(large.monitors).toBeGreaterThan(team.monitors)
    expect(team.runs).toBeGreaterThan(small.runs)
    expect(large.runs).toBeGreaterThan(team.runs)
    expect(team.items).toBeGreaterThan(small.items)
    expect(large.items).toBeGreaterThan(team.items)
  })

  it("defines positive per-surface performance budgets", () => {
    for (const budget of Object.values(WATCHLISTS_SURFACE_PERFORMANCE_BUDGETS)) {
      expect(budget.renderLatencyMs).toBeGreaterThan(0)
      expect(budget.interactionLatencyMs).toBeGreaterThan(0)
      expect(budget.refreshCadenceSeconds).toBeGreaterThan(0)
    }
  })

  it.each(["small", "team", "large"] as const)(
    "captures baseline render and mutation timings for the %s profile",
    (profileKey) => {
      const result = runWatchlistsScaleBenchmark(profileKey)

      expect(result.profile.key).toBe(profileKey)

      for (const timing of Object.values(result.timings)) {
        expect(Number.isFinite(timing)).toBe(true)
        expect(timing).toBeGreaterThanOrEqual(0)
      }

      for (const withinBudget of Object.values(result.withinBudget)) {
        expect(typeof withinBudget).toBe("boolean")
      }
    }
  )
})
