export type WatchlistsOnboardingPath = "beginner" | "advanced"

export const WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY = "watchlists:onboarding-path:v1"
export const DEFAULT_WATCHLISTS_ONBOARDING_PATH: WatchlistsOnboardingPath = "beginner"

export const isWatchlistsOnboardingPath = (
  value: unknown
): value is WatchlistsOnboardingPath => value === "beginner" || value === "advanced"

export const readWatchlistsOnboardingPath = (): WatchlistsOnboardingPath => {
  if (typeof window === "undefined") return DEFAULT_WATCHLISTS_ONBOARDING_PATH
  try {
    const stored = localStorage.getItem(WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY)
    return isWatchlistsOnboardingPath(stored)
      ? stored
      : DEFAULT_WATCHLISTS_ONBOARDING_PATH
  } catch {
    return DEFAULT_WATCHLISTS_ONBOARDING_PATH
  }
}

export const writeWatchlistsOnboardingPath = (
  path: WatchlistsOnboardingPath
): void => {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(WATCHLISTS_ONBOARDING_PATH_STORAGE_KEY, path)
  } catch {
    // Ignore storage write failures.
  }
}
