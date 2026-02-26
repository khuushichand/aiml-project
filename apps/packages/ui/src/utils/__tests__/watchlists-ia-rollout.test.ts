import { afterEach, beforeEach, describe, expect, it } from "vitest"
import {
  FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS,
  FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY
} from "@/utils/feature-rollout"
import {
  WATCHLISTS_IA_ROLLOUT_STORAGE_KEY,
  resolveWatchlistsIaExperimentRollout
} from "@/utils/watchlists-ia-rollout"

const originalEnvMode = process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE
const originalEnvPercent = process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT
const originalLegacyFlag = process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA

describe("watchlists-ia-rollout", () => {
  beforeEach(() => {
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
    delete (window as { __TLDW_WATCHLISTS_IA_VARIANT__?: unknown }).__TLDW_WATCHLISTS_IA_VARIANT__
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT__

    localStorage.removeItem(FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY)
    localStorage.removeItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY)
    localStorage.removeItem(FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS.watchlists_ia_reduced_nav_v1)

    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE = "rollout"
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT = "0"
    delete process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA
  })

  afterEach(() => {
    if (originalEnvMode == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE
    } else {
      process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE = originalEnvMode
    }

    if (originalEnvPercent == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT
    } else {
      process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT = originalEnvPercent
    }

    if (originalLegacyFlag == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA
    } else {
      process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA = originalLegacyFlag
    }
  })

  it("honors runtime variant override as highest-priority control", () => {
    ;(window as { __TLDW_WATCHLISTS_IA_VARIANT__?: unknown }).__TLDW_WATCHLISTS_IA_VARIANT__ = "experimental"
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE = "baseline"

    const result = resolveWatchlistsIaExperimentRollout()

    expect(result.variant).toBe("experimental")
    expect(result.enabled).toBe(true)
    expect(result.source).toBe("window_override")
  })

  it("supports legacy boolean override for backwards compatibility", () => {
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = true

    const result = resolveWatchlistsIaExperimentRollout()

    expect(result.variant).toBe("experimental")
    expect(result.enabled).toBe(true)
    expect(result.source).toBe("window_override")
  })

  it("uses deterministic rollout assignment and persists subject + assignment", () => {
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE = "rollout"
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT = "100"

    const first = resolveWatchlistsIaExperimentRollout()
    const second = resolveWatchlistsIaExperimentRollout()

    expect(first.variant).toBe("experimental")
    expect(first.source).toBe("rollout")
    expect(second.variant).toBe(first.variant)
    expect(localStorage.getItem(FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY)).toBeTruthy()
    expect(localStorage.getItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY)).toContain('"variant":"experimental"')
  })

  it("prefers explicit local rollout percentage override and falls back to baseline safely", () => {
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE = "rollout"
    process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT = "100"
    localStorage.setItem(FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS.watchlists_ia_reduced_nav_v1, "0")

    const result = resolveWatchlistsIaExperimentRollout()

    expect(result.variant).toBe("baseline")
    expect(result.enabled).toBe(false)
    expect(result.source).toBe("rollout")
    expect(result.rolloutPercentage).toBe(0)
  })
})
