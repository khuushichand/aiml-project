import { recordWatchlistsOnboardingTelemetry } from "@/services/watchlists"
import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY =
  "tldw:watchlists:onboarding:telemetry"
const MAX_RECENT_EVENTS = 200

export type WatchlistsQuickSetupStep = "feed" | "monitor" | "review"
export type WatchlistsGuidedTourStep = 1 | 2 | 3 | 4 | 5
export type WatchlistsQuickSetupDestination = "runs" | "outputs" | "jobs"
export type WatchlistsQuickSetupPreview = "candidate" | "template"
export type WatchlistsOnboardingSuccessSource =
  | "overview"
  | "outputs"
  | "run_notifications"

type EventDetails = Record<string, string | number | boolean | null>

export type WatchlistsOnboardingTelemetryEvent =
  | { type: "quick_setup_opened" }
  | { type: "quick_setup_step_completed"; step: WatchlistsQuickSetupStep }
  | { type: "quick_setup_cancelled"; step: WatchlistsQuickSetupStep }
  | {
      type: "quick_setup_completed"
      goal: "briefing" | "triage"
      runNow: boolean
      destination: WatchlistsQuickSetupDestination
    }
  | { type: "quick_setup_failed"; step: WatchlistsQuickSetupStep }
  | {
      type: "quick_setup_preview_loaded"
      preview: WatchlistsQuickSetupPreview
      total?: number
      ingestable?: number
      filtered?: number
      goal?: "briefing" | "triage"
      audioEnabled?: boolean
    }
  | {
      type: "quick_setup_preview_failed"
      preview: WatchlistsQuickSetupPreview
      reason?: string
    }
  | {
      type: "quick_setup_test_run_triggered"
      runId: number
    }
  | { type: "quick_setup_test_run_failed" }
  | {
      type: "quick_setup_first_run_succeeded"
      source?: WatchlistsOnboardingSuccessSource
      runId?: number
    }
  | {
      type: "quick_setup_first_output_succeeded"
      source?: WatchlistsOnboardingSuccessSource
      outputId?: number
      format?: string
    }
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
type QuickSetupDestinationCounters = Record<WatchlistsQuickSetupDestination, number>
type QuickSetupPreviewCounters = Record<WatchlistsQuickSetupPreview, number>

export type WatchlistsUc2FunnelDashboardSnapshot = {
  counters: {
    quickSetupOpened: number
    quickSetupCompleted: number
    briefingCompletions: number
    triageCompletions: number
    runNowOptIns: number
    reviewStepCompletions: number
    destination: QuickSetupDestinationCounters
    previewLoaded: QuickSetupPreviewCounters
    previewFailed: QuickSetupPreviewCounters
    testRunTriggered: number
    testRunFailed: number
    firstRunSuccess: number
    firstOutputSuccess: number
  }
  rates: {
    setupCompletionRate: number
    briefingCompletionRate: number
    runNowOptInRate: number
    testRunTriggerRate: number
    firstSuccessProxyRate: number
    firstRunSuccessRate: number
    firstOutputSuccessRate: number
    setupDropoffRate: number
    runSuccessDropoffRate: number
    outputSuccessDropoffRate: number
  }
  timings: {
    medianSecondsToSetupCompletion: number
    medianSecondsToFirstRunSuccess: number
    medianSecondsToFirstOutputSuccess: number
  }
}

export type WatchlistsOnboardingTelemetryState = {
  version: 1
  session_id: string
  counters: Record<string, number>
  quick_setup: {
    step_completed: StepCounters
    cancelled_at_step: StepCounters
    failed_at_step: StepCounters
    completed_by_goal: Record<"briefing" | "triage", number>
    completed_by_destination: QuickSetupDestinationCounters
    completed_with_run_now: number
    completed_without_run_now: number
    preview_loaded: QuickSetupPreviewCounters
    preview_failed: QuickSetupPreviewCounters
    test_run_triggered: number
    test_run_failed: number
    first_run_success: number
    first_output_success: number
    active_setup_started_at: number | null
    pending_first_run_success_at: number[]
    pending_first_output_success_at: number[]
    seconds_to_setup_completion_samples: number[]
    seconds_to_first_run_success_samples: number[]
    seconds_to_first_output_success_samples: number[]
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

const DEFAULT_DESTINATION_COUNTERS: QuickSetupDestinationCounters = {
  runs: 0,
  outputs: 0,
  jobs: 0
}

const DEFAULT_PREVIEW_COUNTERS: QuickSetupPreviewCounters = {
  candidate: 0,
  template: 0
}

const MAX_DURATION_SAMPLES = 100
const MAX_PENDING_COMPLETION_EVENTS = 64

const createOnboardingSessionId = (): string =>
  `wl-onboarding-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`

const DEFAULT_STATE: WatchlistsOnboardingTelemetryState = {
  version: 1,
  session_id: createOnboardingSessionId(),
  counters: {},
  quick_setup: {
    step_completed: { ...DEFAULT_STEP_COUNTERS },
    cancelled_at_step: { ...DEFAULT_STEP_COUNTERS },
    failed_at_step: { ...DEFAULT_STEP_COUNTERS },
    completed_by_goal: {
      briefing: 0,
      triage: 0
    },
    completed_by_destination: { ...DEFAULT_DESTINATION_COUNTERS },
    completed_with_run_now: 0,
    completed_without_run_now: 0,
    preview_loaded: { ...DEFAULT_PREVIEW_COUNTERS },
    preview_failed: { ...DEFAULT_PREVIEW_COUNTERS },
    test_run_triggered: 0,
    test_run_failed: 0,
    first_run_success: 0,
    first_output_success: 0,
    active_setup_started_at: null,
    pending_first_run_success_at: [],
    pending_first_output_success_at: [],
    seconds_to_setup_completion_samples: [],
    seconds_to_first_run_success_samples: [],
    seconds_to_first_output_success_samples: []
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

const toBoundedNumberList = (value: unknown, maxSize: number): number[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => Number(entry))
    .filter((entry) => Number.isFinite(entry) && entry >= 0)
    .slice(-maxSize)
}

const pushDurationSample = (samples: number[], durationSeconds: number): number[] => {
  if (!Number.isFinite(durationSeconds) || durationSeconds < 0) return samples.slice(-MAX_DURATION_SAMPLES)
  const rounded = Math.round(durationSeconds * 100) / 100
  return [...samples, rounded].slice(-MAX_DURATION_SAMPLES)
}

const consumePendingTimestamp = (pending: number[]): { next: number[]; consumedAt: number | null } => {
  if (!Array.isArray(pending) || pending.length <= 0) {
    return {
      next: [],
      consumedAt: null
    }
  }
  const [consumedAt, ...rest] = pending
  return {
    next: rest.slice(-MAX_PENDING_COMPLETION_EVENTS),
    consumedAt: Number.isFinite(consumedAt) ? Number(consumedAt) : null
  }
}

const hasPendingOnboardingMilestone = (
  state: WatchlistsOnboardingTelemetryState,
  event: WatchlistsOnboardingTelemetryEvent
): boolean => {
  if (event.type === "quick_setup_first_run_succeeded") {
    return state.quick_setup.pending_first_run_success_at.length > 0
  }
  if (event.type === "quick_setup_first_output_succeeded") {
    return state.quick_setup.pending_first_output_success_at.length > 0
  }
  return true
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
      session_id:
        typeof state.session_id === "string" && state.session_id.trim().length > 0
          ? state.session_id
          : createOnboardingSessionId(),
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
        },
        completed_by_destination: {
          ...DEFAULT_STATE.quick_setup.completed_by_destination,
          ...(state.quick_setup?.completed_by_destination || {})
        },
        preview_loaded: {
          ...DEFAULT_STATE.quick_setup.preview_loaded,
          ...(state.quick_setup?.preview_loaded || {})
        },
        preview_failed: {
          ...DEFAULT_STATE.quick_setup.preview_failed,
          ...(state.quick_setup?.preview_failed || {})
        },
        pending_first_run_success_at: toBoundedNumberList(
          state.quick_setup?.pending_first_run_success_at,
          MAX_PENDING_COMPLETION_EVENTS
        ),
        pending_first_output_success_at: toBoundedNumberList(
          state.quick_setup?.pending_first_output_success_at,
          MAX_PENDING_COMPLETION_EVENTS
        ),
        seconds_to_setup_completion_samples: toBoundedNumberList(
          state.quick_setup?.seconds_to_setup_completion_samples,
          MAX_DURATION_SAMPLES
        ),
        seconds_to_first_run_success_samples: toBoundedNumberList(
          state.quick_setup?.seconds_to_first_run_success_samples,
          MAX_DURATION_SAMPLES
        ),
        seconds_to_first_output_success_samples: toBoundedNumberList(
          state.quick_setup?.seconds_to_first_output_success_samples,
          MAX_DURATION_SAMPLES
        ),
        active_setup_started_at: Number.isFinite(state.quick_setup?.active_setup_started_at)
          ? Number(state.quick_setup?.active_setup_started_at)
          : null
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
    if (!hasPendingOnboardingMilestone(state, event)) {
      return
    }
    const now = Date.now()

    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "quick_setup_step_completed":
        state.quick_setup.step_completed[event.step] += 1
        break
      case "quick_setup_cancelled":
        state.quick_setup.cancelled_at_step[event.step] += 1
        state.quick_setup.active_setup_started_at = null
        break
      case "quick_setup_failed":
        state.quick_setup.failed_at_step[event.step] += 1
        state.quick_setup.active_setup_started_at = null
        break
      case "quick_setup_completed":
        state.quick_setup.completed_by_goal[event.goal] += 1
        state.quick_setup.completed_by_destination[event.destination] += 1
        if (Number.isFinite(state.quick_setup.active_setup_started_at)) {
          const elapsedSeconds =
            (now - Number(state.quick_setup.active_setup_started_at)) / 1000
          state.quick_setup.seconds_to_setup_completion_samples = pushDurationSample(
            state.quick_setup.seconds_to_setup_completion_samples,
            elapsedSeconds
          )
        }
        state.quick_setup.active_setup_started_at = null
        if (event.runNow) {
          state.quick_setup.completed_with_run_now += 1
        } else {
          state.quick_setup.completed_without_run_now += 1
        }
        if (event.goal === "briefing") {
          state.quick_setup.pending_first_run_success_at = [
            ...state.quick_setup.pending_first_run_success_at,
            now
          ].slice(-MAX_PENDING_COMPLETION_EVENTS)
          state.quick_setup.pending_first_output_success_at = [
            ...state.quick_setup.pending_first_output_success_at,
            now
          ].slice(-MAX_PENDING_COMPLETION_EVENTS)
        }
        break
      case "quick_setup_preview_loaded":
        state.quick_setup.preview_loaded[event.preview] += 1
        break
      case "quick_setup_preview_failed":
        state.quick_setup.preview_failed[event.preview] += 1
        break
      case "quick_setup_test_run_triggered":
        state.quick_setup.test_run_triggered += 1
        break
      case "quick_setup_test_run_failed":
        state.quick_setup.test_run_failed += 1
        break
      case "quick_setup_first_run_succeeded": {
        const runCompletion = consumePendingTimestamp(
          state.quick_setup.pending_first_run_success_at
        )
        state.quick_setup.pending_first_run_success_at = runCompletion.next
        state.quick_setup.first_run_success += 1
        if (runCompletion.consumedAt != null) {
          state.quick_setup.seconds_to_first_run_success_samples = pushDurationSample(
            state.quick_setup.seconds_to_first_run_success_samples,
            (now - runCompletion.consumedAt) / 1000
          )
        }
        break
      }
      case "quick_setup_first_output_succeeded": {
        const outputCompletion = consumePendingTimestamp(
          state.quick_setup.pending_first_output_success_at
        )
        state.quick_setup.pending_first_output_success_at = outputCompletion.next
        state.quick_setup.first_output_success += 1
        if (outputCompletion.consumedAt != null) {
          state.quick_setup.seconds_to_first_output_success_samples = pushDurationSample(
            state.quick_setup.seconds_to_first_output_success_samples,
            (now - outputCompletion.consumedAt) / 1000
          )
        }
        break
      }
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
      case "quick_setup_opened":
        state.quick_setup.active_setup_started_at = now
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

    void recordWatchlistsOnboardingTelemetry({
      session_id: state.session_id,
      event_type: event.type,
      event_at: new Date(now).toISOString(),
      details: toEventDetails(event)
    }).catch(() => {
      // Backend telemetry sink failures are non-blocking by design.
    })
  } catch (error) {
    console.warn("[watchlists-onboarding-telemetry] Failed to record event", error)
  }
}

export const getWatchlistsOnboardingTelemetryState =
  async (): Promise<WatchlistsOnboardingTelemetryState> => readTelemetryState()

export const resetWatchlistsOnboardingTelemetryState = async () => {
  await storage.set(WATCHLISTS_ONBOARDING_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}

const toFiniteRate = (numerator: number, denominator: number): number => {
  if (!Number.isFinite(numerator) || numerator <= 0) return 0
  if (!Number.isFinite(denominator) || denominator <= 0) return 0
  return numerator / denominator
}

const toFiniteDropoff = (completionRate: number): number => {
  if (!Number.isFinite(completionRate)) return 1
  return Math.max(0, Math.min(1, 1 - completionRate))
}

const toMedian = (values: number[]): number => {
  if (!Array.isArray(values) || values.length <= 0) return 0
  const sorted = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value >= 0)
    .sort((a, b) => a - b)
  if (sorted.length <= 0) return 0
  const middle = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 1) return sorted[middle]
  return Math.round(((sorted[middle - 1] + sorted[middle]) / 2) * 100) / 100
}

export const buildWatchlistsUc2FunnelDashboardSnapshot = (
  state: WatchlistsOnboardingTelemetryState | null | undefined
): WatchlistsUc2FunnelDashboardSnapshot => {
  const counters = state?.counters || {}
  const quickSetup = state?.quick_setup || DEFAULT_STATE.quick_setup
  const quickSetupOpened = counters.quick_setup_opened || 0
  const quickSetupCompleted = counters.quick_setup_completed || 0
  const briefingCompletions = quickSetup.completed_by_goal.briefing || 0
  const triageCompletions = quickSetup.completed_by_goal.triage || 0
  const runNowOptIns = quickSetup.completed_with_run_now || 0
  const reviewStepCompletions = quickSetup.step_completed.review || 0
  const testRunTriggered = quickSetup.test_run_triggered || 0
  const testRunFailed = quickSetup.test_run_failed || 0
  const firstRunSuccess = quickSetup.first_run_success || 0
  const firstOutputSuccess = quickSetup.first_output_success || 0

  const setupCompletionRate = toFiniteRate(quickSetupCompleted, quickSetupOpened)
  const briefingCompletionRate = toFiniteRate(briefingCompletions, quickSetupCompleted)
  const runNowOptInRate = toFiniteRate(runNowOptIns, briefingCompletions)
  const testRunTriggerRate = toFiniteRate(testRunTriggered, runNowOptIns)
  const firstSuccessProxyRate = toFiniteRate(testRunTriggered, briefingCompletions)
  const firstRunSuccessRate = toFiniteRate(firstRunSuccess, briefingCompletions)
  const firstOutputSuccessRate = toFiniteRate(firstOutputSuccess, briefingCompletions)

  return {
    counters: {
      quickSetupOpened,
      quickSetupCompleted,
      briefingCompletions,
      triageCompletions,
      runNowOptIns,
      reviewStepCompletions,
      destination: {
        ...DEFAULT_DESTINATION_COUNTERS,
        ...(quickSetup.completed_by_destination || {})
      },
      previewLoaded: {
        ...DEFAULT_PREVIEW_COUNTERS,
        ...(quickSetup.preview_loaded || {})
      },
      previewFailed: {
        ...DEFAULT_PREVIEW_COUNTERS,
        ...(quickSetup.preview_failed || {})
      },
      testRunTriggered,
      testRunFailed,
      firstRunSuccess,
      firstOutputSuccess
    },
    rates: {
      setupCompletionRate,
      briefingCompletionRate,
      runNowOptInRate,
      testRunTriggerRate,
      firstSuccessProxyRate,
      firstRunSuccessRate,
      firstOutputSuccessRate,
      setupDropoffRate: toFiniteDropoff(setupCompletionRate),
      runSuccessDropoffRate: toFiniteDropoff(firstRunSuccessRate),
      outputSuccessDropoffRate: toFiniteDropoff(firstOutputSuccessRate)
    },
    timings: {
      medianSecondsToSetupCompletion: toMedian(
        quickSetup.seconds_to_setup_completion_samples || []
      ),
      medianSecondsToFirstRunSuccess: toMedian(
        quickSetup.seconds_to_first_run_success_samples || []
      ),
      medianSecondsToFirstOutputSuccess: toMedian(
        quickSetup.seconds_to_first_output_success_samples || []
      )
    }
  }
}
