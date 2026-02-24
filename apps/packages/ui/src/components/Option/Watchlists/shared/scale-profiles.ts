export type WatchlistsScaleProfileKey = "small" | "team" | "large"

export interface WatchlistsScaleProfile {
  key: WatchlistsScaleProfileKey
  label: string
  feeds: number
  monitors: number
  runs: number
  items: number
}

export type WatchlistsScaleSurfaceKey =
  | "overview"
  | "feeds"
  | "monitors"
  | "activity"
  | "articles"
  | "reports"

export interface WatchlistsSurfacePerformanceBudget {
  renderLatencyMs: number
  interactionLatencyMs: number
  refreshCadenceSeconds: number
}

export const WATCHLISTS_SCALE_PROFILES: Record<
  WatchlistsScaleProfileKey,
  WatchlistsScaleProfile
> = {
  small: {
    key: "small",
    label: "5-feed personal setup",
    feeds: 5,
    monitors: 5,
    runs: 25,
    items: 250
  },
  team: {
    key: "team",
    label: "50-feed analyst team setup",
    feeds: 50,
    monitors: 25,
    runs: 200,
    items: 2000
  },
  large: {
    key: "large",
    label: "200-feed high-volume deployment",
    feeds: 200,
    monitors: 75,
    runs: 600,
    items: 8000
  }
}

export const WATCHLISTS_SURFACE_PERFORMANCE_BUDGETS: Record<
  WatchlistsScaleSurfaceKey,
  WatchlistsSurfacePerformanceBudget
> = {
  overview: {
    renderLatencyMs: 100,
    interactionLatencyMs: 60,
    refreshCadenceSeconds: 180
  },
  feeds: {
    renderLatencyMs: 140,
    interactionLatencyMs: 90,
    refreshCadenceSeconds: 300
  },
  monitors: {
    renderLatencyMs: 150,
    interactionLatencyMs: 100,
    refreshCadenceSeconds: 300
  },
  activity: {
    renderLatencyMs: 130,
    interactionLatencyMs: 90,
    refreshCadenceSeconds: 120
  },
  articles: {
    renderLatencyMs: 180,
    interactionLatencyMs: 120,
    refreshCadenceSeconds: 60
  },
  reports: {
    renderLatencyMs: 140,
    interactionLatencyMs: 90,
    refreshCadenceSeconds: 180
  }
}
