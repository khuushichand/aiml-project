import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY =
  "tldw:watchlists:onboarding:telemetry"
const MAX_RECENT_EVENTS = 200

export type WatchlistsQuickSetupStep = "feed" | "monitor" | "review"
export type WatchlistsGuidedTourStep = 1 | 2 | 3 | 4 | 5

type EventDetails = Record<string, string | number | boolean | null>

export type WatchlistsOnboardingTelemetryEvent =
  | { type: "quick_setup_opened" }
  | { type: "quick_setup_step_completed"; step: WatchlistsQuickSetupStep }
  | { type: "quick_setup_cancelled"; step: WatchlistsQuickSetupStep }
  | {
      type: "quick_setup_completed"
      goal: "briefing" | "triage"
      runNow: boolean
      destination: "runs" | "outputs" | "jobs"
    }
  | { type: "quick_setup_failed"; step: WatchlistsQuickSetupStep }
  | { type: "guided_tour_started" }
  | { type: "guided_tour_step_viewed"; step: WatchlistsGuidedTourStep }
  | { type: "guided_tour_completed" }
  | { type: "guided_tour_dismissed"; step: WatchlistsGuidedTourStep }
  | { type: "guided_tour_resumed"; step: WatchlistsGuidedTourStep }

type WatchlistsOnboardingRecentEvent = {
  type: WatchlistsOnboardingTelemetryEvent["type"]
  at: number
  details: EventDetails
}

type StepCounters = Record<WatchlistsQuickSetupStep, number>
type GuidedStepCounters = Record<`${WatchlistsGuidedTourStep}`, number>

export type WatchlistsOnboardingTelemetryState = {
  version: 1
  counters: Record<string, number>
  quick_setup: {
    step_completed: StepCounters
    cancelled_at_step: StepCounters
    failed_at_step: StepCounters
    completed_by_goal: Record<"briefing" | "triage", number>
    completed_with_run_now: number
    completed_without_run_now: number
  }
  guided_tour: {
    started: number
    completed: number
    dismissed: number
    resumed: number
    step_views: GuidedStepCounters
  }
  last_event_at: number | null
  recent_events: WatchlistsOnboardingRecentEvent[]
}

const DEFAULT_STEP_COUNTERS: StepCounters = {
  feed: 0,
  monitor: 0,
  review: 0
}

const DEFAULT_GUIDED_STEP_COUNTERS: GuidedStepCounters = {
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0
}

const DEFAULT_STATE: WatchlistsOnboardingTelemetryState = {
  version: 1,
  counters: {},
  quick_setup: {
    step_completed: { ...DEFAULT_STEP_COUNTERS },
    cancelled_at_step: { ...DEFAULT_STEP_COUNTERS },
    failed_at_step: { ...DEFAULT_STEP_COUNTERS },
    completed_by_goal: {
      briefing: 0,
      triage: 0
    },
    completed_with_run_now: 0,
    completed_without_run_now: 0
  },
  guided_tour: {
    started: 0,
    completed: 0,
    dismissed: 0,
    resumed: 0,
    step_views: { ...DEFAULT_GUIDED_STEP_COUNTERS }
  },
  last_event_at: null,
  recent_events: []
}

const incrementCounter = (counters: Record<string, number>, key: string) => {
  counters[key] = (counters[key] || 0) + 1
}

const toEventDetails = (
  event: WatchlistsOnboardingTelemetryEvent
): EventDetails => {
  const details: EventDetails = {}
  for (const [key, value] of Object.entries(event)) {
    if (key === "type") continue
    if (
      value == null ||
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      details[key] = value
    }
  }
  return details
}

const readTelemetryState =
  async (): Promise<WatchlistsOnboardingTelemetryState> => {
    const raw = await storage.get<WatchlistsOnboardingTelemetryState | undefined>(
      WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
      quick_setup: {
        ...DEFAULT_STATE.quick_setup,
        ...(state.quick_setup || {}),
        step_completed: {
          ...DEFAULT_STATE.quick_setup.step_completed,
          ...(state.quick_setup?.step_completed || {})
        },
        cancelled_at_step: {
          ...DEFAULT_STATE.quick_setup.cancelled_at_step,
          ...(state.quick_setup?.cancelled_at_step || {})
        },
        failed_at_step: {
          ...DEFAULT_STATE.quick_setup.failed_at_step,
          ...(state.quick_setup?.failed_at_step || {})
        },
        completed_by_goal: {
          ...DEFAULT_STATE.quick_setup.completed_by_goal,
          ...(state.quick_setup?.completed_by_goal || {})
        }
      },
      guided_tour: {
        ...DEFAULT_STATE.guided_tour,
        ...(state.guided_tour || {}),
        step_views: {
          ...DEFAULT_STATE.guided_tour.step_views,
          ...(state.guided_tour?.step_views || {})
        }
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: WatchlistsOnboardingTelemetryState) => {
  await storage.set(WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY, state)
}

export const trackWatchlistsOnboardingTelemetry = async (
  event: WatchlistsOnboardingTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()

    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "quick_setup_step_completed":
        state.quick_setup.step_completed[event.step] += 1
        break
      case "quick_setup_cancelled":
        state.quick_setup.cancelled_at_step[event.step] += 1
        break
      case "quick_setup_failed":
        state.quick_setup.failed_at_step[event.step] += 1
        break
      case "quick_setup_completed":
        state.quick_setup.completed_by_goal[event.goal] += 1
        if (event.runNow) {
          state.quick_setup.completed_with_run_now += 1
        } else {
          state.quick_setup.completed_without_run_now += 1
        }
        break
      case "guided_tour_started":
        state.guided_tour.started += 1
        break
      case "guided_tour_completed":
        state.guided_tour.completed += 1
        break
      case "guided_tour_dismissed":
        state.guided_tour.dismissed += 1
        break
      case "guided_tour_resumed":
        state.guided_tour.resumed += 1
        break
      case "guided_tour_step_viewed":
        state.guided_tour.step_views[String(event.step) as keyof GuidedStepCounters] += 1
        break
      default:
        break
    }

    state.recent_events.push({
      type: event.type,
      at: now,
      details: toEventDetails(event)
    })
    if (state.recent_events.length > MAX_RECENT_EVENTS) {
      state.recent_events = state.recent_events.slice(-MAX_RECENT_EVENTS)
    }

    await writeTelemetryState(state)
  } catch (error) {
    console.warn("[watchlists-onboarding-telemetry] Failed to record event", error)
  }
}

export const getWatchlistsOnboardingTelemetryState =
  async (): Promise<WatchlistsOnboardingTelemetryState> => readTelemetryState()

export const resetWatchlistsOnboardingTelemetryState = async () => {
  await storage.set(WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}
