import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const FAMILY_GUARDRAILS_WIZARD_TELEMETRY_STORAGE_KEY =
  "tldw:family-guardrails:wizard:telemetry"
const MAX_RECENT_EVENTS = 200

export type FamilyGuardrailsWizardTelemetryEventType =
  | "setup_started"
  | "draft_resumed"
  | "step_viewed"
  | "step_completed"
  | "step_error"
  | "setup_completed"
  | "drop_off"

export type FamilyGuardrailsWizardTelemetryStep =
  | "basics"
  | "guardians"
  | "dependents"
  | "mapping"
  | "templates"
  | "alerts"
  | "tracker"
  | "review"

export type FamilyGuardrailsWizardTelemetryCohort =
  | "new_household"
  | "existing_household"

type EventDetails = Record<string, string | number | boolean | null>

export type FamilyGuardrailsWizardTelemetryEvent = {
  type: FamilyGuardrailsWizardTelemetryEventType
  cohort: FamilyGuardrailsWizardTelemetryCohort
  step?: FamilyGuardrailsWizardTelemetryStep
  [key: string]: string | number | boolean | null | undefined
}

type FamilyGuardrailsWizardRecentEvent = {
  type: FamilyGuardrailsWizardTelemetryEventType
  cohort: FamilyGuardrailsWizardTelemetryCohort
  step: FamilyGuardrailsWizardTelemetryStep | null
  at: number
  details: EventDetails
}

type CohortSummary = {
  setup_started: number
  draft_resumed: number
  setup_completed: number
  drop_off: number
}

export type FamilyGuardrailsWizardTelemetryState = {
  version: 1
  counters: Record<FamilyGuardrailsWizardTelemetryEventType, number>
  by_cohort: Record<FamilyGuardrailsWizardTelemetryCohort, CohortSummary>
  last_event_at: number | null
  recent_events: FamilyGuardrailsWizardRecentEvent[]
}

export type FamilyGuardrailsWizardRolloutSnapshot = {
  counters: Record<FamilyGuardrailsWizardTelemetryEventType, number>
  byCohort: Record<FamilyGuardrailsWizardTelemetryCohort, CohortSummary>
  completionRates: Record<FamilyGuardrailsWizardTelemetryCohort, number>
  dropOffRates: Record<FamilyGuardrailsWizardTelemetryCohort, number>
}

const DEFAULT_COUNTERS: Record<FamilyGuardrailsWizardTelemetryEventType, number> = {
  setup_started: 0,
  draft_resumed: 0,
  step_viewed: 0,
  step_completed: 0,
  step_error: 0,
  setup_completed: 0,
  drop_off: 0
}

const DEFAULT_COHORT_SUMMARY: CohortSummary = {
  setup_started: 0,
  draft_resumed: 0,
  setup_completed: 0,
  drop_off: 0
}

const DEFAULT_STATE: FamilyGuardrailsWizardTelemetryState = {
  version: 1,
  counters: DEFAULT_COUNTERS,
  by_cohort: {
    new_household: DEFAULT_COHORT_SUMMARY,
    existing_household: DEFAULT_COHORT_SUMMARY
  },
  last_event_at: null,
  recent_events: []
}

const toEventDetails = (
  event: FamilyGuardrailsWizardTelemetryEvent
): EventDetails => {
  const details: EventDetails = {}
  for (const [key, value] of Object.entries(event)) {
    if (key === "type" || key === "cohort" || key === "step") continue
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
  async (): Promise<FamilyGuardrailsWizardTelemetryState> => {
    const raw = await storage.get<FamilyGuardrailsWizardTelemetryState | undefined>(
      FAMILY_GUARDRAILS_WIZARD_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: {
        ...DEFAULT_COUNTERS,
        ...(state.counters || {})
      },
      by_cohort: {
        new_household: {
          ...DEFAULT_COHORT_SUMMARY,
          ...(state.by_cohort?.new_household || {})
        },
        existing_household: {
          ...DEFAULT_COHORT_SUMMARY,
          ...(state.by_cohort?.existing_household || {})
        }
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: FamilyGuardrailsWizardTelemetryState) => {
  await storage.set(FAMILY_GUARDRAILS_WIZARD_TELEMETRY_STORAGE_KEY, state)
}

export const trackFamilyGuardrailsWizardTelemetry = async (
  event: FamilyGuardrailsWizardTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()

    state.last_event_at = now
    state.counters[event.type] = (state.counters[event.type] || 0) + 1
    state.by_cohort[event.cohort] = {
      ...DEFAULT_COHORT_SUMMARY,
      ...(state.by_cohort[event.cohort] || {})
    }

    if (
      event.type === "setup_started" ||
      event.type === "draft_resumed" ||
      event.type === "setup_completed" ||
      event.type === "drop_off"
    ) {
      state.by_cohort[event.cohort][event.type] =
        (state.by_cohort[event.cohort][event.type] || 0) + 1
    }

    state.recent_events.push({
      type: event.type,
      cohort: event.cohort,
      step: event.step || null,
      at: now,
      details: toEventDetails(event)
    })
    if (state.recent_events.length > MAX_RECENT_EVENTS) {
      state.recent_events = state.recent_events.slice(-MAX_RECENT_EVENTS)
    }

    await writeTelemetryState(state)
  } catch (error) {
    console.warn("[family-guardrails-wizard-telemetry] Failed to record event", error)
  }
}

export const getFamilyGuardrailsWizardTelemetryState =
  async (): Promise<FamilyGuardrailsWizardTelemetryState> => readTelemetryState()

export const resetFamilyGuardrailsWizardTelemetryState = async () => {
  await storage.set(FAMILY_GUARDRAILS_WIZARD_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}

const toFiniteRate = (numerator: number, denominator: number): number => {
  if (!Number.isFinite(numerator) || numerator <= 0) return 0
  if (!Number.isFinite(denominator) || denominator <= 0) return 0
  return numerator / denominator
}

export const buildFamilyGuardrailsWizardRolloutSnapshot = (
  state: FamilyGuardrailsWizardTelemetryState | null | undefined
): FamilyGuardrailsWizardRolloutSnapshot => {
  const counters = state?.counters || DEFAULT_COUNTERS
  const byCohort = state?.by_cohort || DEFAULT_STATE.by_cohort

  return {
    counters,
    byCohort,
    completionRates: {
      new_household: toFiniteRate(
        byCohort.new_household.setup_completed,
        byCohort.new_household.setup_started
      ),
      existing_household: toFiniteRate(
        byCohort.existing_household.setup_completed,
        byCohort.existing_household.setup_started + byCohort.existing_household.draft_resumed
      )
    },
    dropOffRates: {
      new_household: toFiniteRate(
        byCohort.new_household.drop_off,
        byCohort.new_household.setup_started
      ),
      existing_household: toFiniteRate(
        byCohort.existing_household.drop_off,
        byCohort.existing_household.setup_started + byCohort.existing_household.draft_resumed
      )
    }
  }
}
