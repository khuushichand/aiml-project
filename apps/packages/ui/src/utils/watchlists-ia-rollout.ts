import type { WatchlistsIaExperimentVariant } from "@/types/watchlists"
import {
  FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS,
  FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY,
  createRolloutSubjectId,
  isFlagEnabledForRollout,
  resolveRolloutPercentageFromCandidates
} from "@/utils/feature-rollout"

export const WATCHLISTS_IA_ROLLOUT_FLAG_KEY = "watchlists_ia_reduced_nav_v1"
export const WATCHLISTS_IA_ROLLOUT_STORAGE_KEY = "watchlists:ia-rollout:v1"

export type WatchlistsIaRolloutSource =
  | "window_override"
  | "legacy_env"
  | "mode_forced"
  | "rollout"
  | "fallback_baseline"

export interface WatchlistsIaRolloutResolution {
  variant: WatchlistsIaExperimentVariant
  enabled: boolean
  source: WatchlistsIaRolloutSource
  rolloutPercentage: number
  subjectId: string | null
}

interface WatchlistsIaRolloutSnapshot {
  version: 1
  variant: WatchlistsIaExperimentVariant
  source: WatchlistsIaRolloutSource
  rollout_percentage: number
  subject_id: string | null
  updated_at: string
}

const parseVariant = (value: unknown): WatchlistsIaExperimentVariant | null => {
  const normalized = String(value || "").trim().toLowerCase()
  if (normalized === "experimental") return "experimental"
  if (normalized === "baseline") return "baseline"
  return null
}

const parseBooleanVariant = (value: unknown): WatchlistsIaExperimentVariant | null => {
  if (typeof value === "boolean") {
    return value ? "experimental" : "baseline"
  }
  if (typeof value !== "string") return null
  const normalized = value.trim().toLowerCase()
  if (normalized === "true" || normalized === "1" || normalized === "yes") {
    return "experimental"
  }
  if (normalized === "false" || normalized === "0" || normalized === "no") {
    return "baseline"
  }
  return null
}

const resolveExperimentMode = (value: unknown): "baseline" | "experimental" | "rollout" => {
  const normalized = String(value || "").trim().toLowerCase()
  if (normalized === "baseline" || normalized === "experimental") {
    return normalized
  }
  return "rollout"
}

const safeGetItem = (key: string): string | null => {
  if (typeof window === "undefined") return null
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

const safeSetItem = (key: string, value: string): void => {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Ignore storage write failures and continue with in-memory resolution.
  }
}

const ensureRolloutSubjectId = (): string => {
  const existing = safeGetItem(FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY)
  if (existing && existing.trim().length > 0) {
    return existing.trim()
  }

  const created = createRolloutSubjectId()
  safeSetItem(FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY, created)
  return created
}

const buildResolution = (
  variant: WatchlistsIaExperimentVariant,
  source: WatchlistsIaRolloutSource,
  rolloutPercentage: number,
  subjectId: string | null
): WatchlistsIaRolloutResolution => ({
  variant,
  enabled: variant === "experimental",
  source,
  rolloutPercentage,
  subjectId
})

const persistResolution = (resolution: WatchlistsIaRolloutResolution): void => {
  const snapshot: WatchlistsIaRolloutSnapshot = {
    version: 1,
    variant: resolution.variant,
    source: resolution.source,
    rollout_percentage: resolution.rolloutPercentage,
    subject_id: resolution.subjectId,
    updated_at: new Date().toISOString()
  }
  safeSetItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY, JSON.stringify(snapshot))
}

export const resolveWatchlistsIaExperimentRollout = (): WatchlistsIaRolloutResolution => {
  if (typeof window === "undefined") {
    return buildResolution("baseline", "fallback_baseline", 0, null)
  }

  const windowVariant = parseVariant(
    (window as { __TLDW_WATCHLISTS_IA_VARIANT__?: unknown }).__TLDW_WATCHLISTS_IA_VARIANT__
  )
  if (windowVariant) {
    const resolution = buildResolution(windowVariant, "window_override", windowVariant === "experimental" ? 100 : 0, null)
    persistResolution(resolution)
    return resolution
  }

  const windowBooleanVariant = parseBooleanVariant(
    (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
  )
  if (windowBooleanVariant) {
    const resolution = buildResolution(
      windowBooleanVariant,
      "window_override",
      windowBooleanVariant === "experimental" ? 100 : 0,
      null
    )
    persistResolution(resolution)
    return resolution
  }

  const legacyEnvVariant = parseBooleanVariant(process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA)
  if (legacyEnvVariant) {
    const resolution = buildResolution(
      legacyEnvVariant,
      "legacy_env",
      legacyEnvVariant === "experimental" ? 100 : 0,
      null
    )
    persistResolution(resolution)
    return resolution
  }

  const mode = resolveExperimentMode(process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_MODE)
  if (mode === "baseline" || mode === "experimental") {
    const resolution = buildResolution(
      mode,
      "mode_forced",
      mode === "experimental" ? 100 : 0,
      null
    )
    persistResolution(resolution)
    return resolution
  }

  const rolloutPercentage = resolveRolloutPercentageFromCandidates(
    [
      (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT__?: unknown })
        .__TLDW_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT__,
      safeGetItem(FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS.watchlists_ia_reduced_nav_v1),
      process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_ROLLOUT_PERCENT
    ],
    0
  )
  const subjectId = ensureRolloutSubjectId()
  const enabled = isFlagEnabledForRollout({
    flagKey: WATCHLISTS_IA_ROLLOUT_FLAG_KEY,
    subjectId,
    rolloutPercentage
  })
  const resolution = buildResolution(
    enabled ? "experimental" : "baseline",
    "rollout",
    rolloutPercentage,
    subjectId
  )
  persistResolution(resolution)
  return resolution
}
