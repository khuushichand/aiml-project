import type { WatchlistsIaExperimentVariant } from "@/types/watchlists"

export const WATCHLISTS_IA_ROLLOUT_STORAGE_KEY = "watchlists:ia-rollout:v1"

interface WatchlistsIaRolloutAssignment {
  version: 1
  variant: WatchlistsIaExperimentVariant
  source: "override" | "storage" | "env_variant" | "env_percent" | "default"
  assigned_at: string
  percent?: number
}

const parseVariant = (value: unknown): WatchlistsIaExperimentVariant | null => {
  const normalized = String(value ?? "").trim().toLowerCase()
  if (normalized === "experimental" || normalized === "1" || normalized === "true" || normalized === "on") {
    return "experimental"
  }
  if (normalized === "baseline" || normalized === "0" || normalized === "false" || normalized === "off") {
    return "baseline"
  }
  return null
}

const parseOverrideVariant = (value: unknown): WatchlistsIaExperimentVariant | null => {
  if (typeof value === "boolean") {
    return value ? "experimental" : "baseline"
  }
  return parseVariant(value)
}

const readStoredAssignment = (): WatchlistsIaRolloutAssignment | null => {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<WatchlistsIaRolloutAssignment>
    const variant = parseVariant(parsed.variant)
    if (!variant) return null
    const source =
      parsed.source === "override" ||
      parsed.source === "storage" ||
      parsed.source === "env_variant" ||
      parsed.source === "env_percent" ||
      parsed.source === "default"
        ? parsed.source
        : "storage"
    return {
      version: 1,
      variant,
      source,
      assigned_at:
        typeof parsed.assigned_at === "string" && parsed.assigned_at
          ? parsed.assigned_at
          : new Date().toISOString(),
      percent: typeof parsed.percent === "number" ? parsed.percent : undefined
    }
  } catch {
    return null
  }
}

const writeStoredAssignment = (
  variant: WatchlistsIaExperimentVariant,
  source: WatchlistsIaRolloutAssignment["source"],
  percent?: number
): void => {
  if (typeof window === "undefined") return
  const payload: WatchlistsIaRolloutAssignment = {
    version: 1,
    variant,
    source,
    assigned_at: new Date().toISOString(),
    percent: Number.isFinite(percent) ? Number(percent) : undefined
  }
  try {
    localStorage.setItem(WATCHLISTS_IA_ROLLOUT_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // localStorage may be unavailable.
  }
}

const resolvePercentVariant = (): WatchlistsIaExperimentVariant | null => {
  const raw = process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT
  if (raw == null || String(raw).trim() === "") return null
  const percent = Number(raw)
  if (!Number.isFinite(percent)) return null
  const bounded = Math.max(0, Math.min(100, percent))
  return Math.random() * 100 < bounded ? "experimental" : "baseline"
}

export const resolveWatchlistsIaExperimentVariant = (): WatchlistsIaExperimentVariant => {
  if (typeof window !== "undefined") {
    const override = (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown })
      .__TLDW_WATCHLISTS_IA_EXPERIMENT__
    const overrideVariant = parseOverrideVariant(override)
    if (overrideVariant) {
      writeStoredAssignment(overrideVariant, "override")
      return overrideVariant
    }

    const stored = readStoredAssignment()
    if (stored) return stored.variant
  }

  const envVariant = parseVariant(process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT)
  if (envVariant) {
    writeStoredAssignment(envVariant, "env_variant")
    return envVariant
  }

  const percentVariant = resolvePercentVariant()
  if (percentVariant) {
    const percent = Number(process.env.NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT)
    writeStoredAssignment(percentVariant, "env_percent", percent)
    return percentVariant
  }

  return "baseline"
}
