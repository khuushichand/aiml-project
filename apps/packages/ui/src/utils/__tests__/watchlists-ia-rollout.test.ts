import { afterAll, beforeEach, describe, expect, it, vi } from "vitest"
import {
  WATCHLISTS_IA_ROLLOUT_STORAGE_KEY,
  resolveWatchlistsIaExperimentVariant
} from "@/utils/watchlists-ia-rollout"

describe("watchlists-ia-rollout", () => {
  const originalPercent = process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT
  const originalVariant = process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.removeItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY)
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
    delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT
    delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT
  })

  afterAll(() => {
    if (originalPercent == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT
    } else {
      process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT = originalPercent
    }
    if (originalVariant == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT
    } else {
      process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT = originalVariant
    }
  })

  it("uses runtime override when provided", () => {
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = true
    expect(resolveWatchlistsIaExperimentVariant()).toBe("experimental")

    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = "baseline"
    expect(resolveWatchlistsIaExperimentVariant()).toBe("baseline")
  })

  it("uses persisted rollout assignment when present", () => {
    localStorage.setItem(
      WATCHLISTS_IA_ROLLOUT_STORAGE_KEY,
      JSON.stringify({ version: 1, variant: "experimental" })
    )

    expect(resolveWatchlistsIaExperimentVariant()).toBe("experimental")
  })

  it("assigns and persists percentage rollout when configured", () => {
    const randomSpy = vi.spyOn(Math, "random").mockReturnValue(0.1)
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT = "20"

    expect(resolveWatchlistsIaExperimentVariant()).toBe("experimental")
    randomSpy.mockRestore()

    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT = "0"
    expect(resolveWatchlistsIaExperimentVariant()).toBe("experimental")
  })

  it("falls back to baseline when rollout config is invalid", () => {
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT = "not-a-number"
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT = "invalid"
    expect(resolveWatchlistsIaExperimentVariant()).toBe("baseline")
  })
})
