import {
  DEFAULT_WATCHLISTS_ONBOARDING_PATH,
  WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY,
  isWatchlistsOnboardingPath,
  readWatchlistsOnboardingPath,
  writeWatchlistsOnboardingPath
} from "../onboarding-path"
import { afterEach, describe, expect, it } from "vitest"

describe("watchlists onboarding path helpers", () => {
  afterEach(() => {
    localStorage.removeItem(WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY)
  })

  it("validates onboarding path values", () => {
    expect(isWatchlistsOnboardingPath("beginner")).toBe(true)
    expect(isWatchlistsOnboardingPath("advanced")).toBe(true)
    expect(isWatchlistsOnboardingPath("unknown")).toBe(false)
    expect(isWatchlistsOnboardingPath(null)).toBe(false)
  })

  it("returns default when storage is missing or invalid", () => {
    expect(readWatchlistsOnboardingPath()).toBe(
      DEFAULT_WATCHLISTS_ONBOARDING_PATH
    )

    localStorage.setItem(WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY, "invalid")
    expect(readWatchlistsOnboardingPath()).toBe(
      DEFAULT_WATCHLISTS_ONBOARDING_PATH
    )
  })

  it("persists and reads valid onboarding path values", () => {
    writeWatchlistsOnboardingPath("advanced")
    expect(localStorage.getItem(WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY)).toBe(
      "advanced"
    )
    expect(readWatchlistsOnboardingPath()).toBe("advanced")

    writeWatchlistsOnboardingPath("beginner")
    expect(readWatchlistsOnboardingPath()).toBe("beginner")
  })
})
