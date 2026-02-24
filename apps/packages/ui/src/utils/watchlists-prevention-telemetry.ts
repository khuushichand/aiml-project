import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY =
  "tldw:watchlists:preventionTelemetry"
const MAX_RECENT_EVENTS = 200

export type WatchlistsPreventionSurface =
  | "job_form"
  | "schedule_picker"
  | "groups_tree"

export type WatchlistsPreventionRule =
  | "scope_required"
  | "schedule_too_frequent"
  | "invalid_email_recipients"
  | "group_cycle_parent"

export type WatchlistsAuthoringSurface = "job_form" | "template_editor"
export type WatchlistsAuthoringMode = "basic" | "advanced"
export type WatchlistsAuthoringContext = "create" | "edit"
export type WatchlistsBasicStep = "scope" | "schedule" | "output" | "review"
export type WatchlistsTemplateRecipe = "briefing_md" | "newsletter_html" | "mece_md"
export type WatchlistsTemplatePreviewMode = "static" | "live"
export type WatchlistsTemplatePreviewStatus = "success" | "error"

type EventDetails = Record<string, string | number | boolean | null>

type WatchlistsValidationBlockedEvent = {
  type: "watchlists_validation_blocked"
  surface: WatchlistsPreventionSurface
  rule: WatchlistsPreventionRule
  remediation: string
  count?: number
  minutes?: number
}

type WatchlistsAuthoringStartedEvent = {
  type: "watchlists_authoring_started"
  surface: WatchlistsAuthoringSurface
  mode: WatchlistsAuthoringMode
  context: WatchlistsAuthoringContext
}

type WatchlistsAuthoringModeChangedEvent = {
  type: "watchlists_authoring_mode_changed"
  surface: WatchlistsAuthoringSurface
  from_mode: WatchlistsAuthoringMode
  to_mode: WatchlistsAuthoringMode
  context: WatchlistsAuthoringContext
}

type WatchlistsAuthoringSavedEvent = {
  type: "watchlists_authoring_saved"
  surface: WatchlistsAuthoringSurface
  mode: WatchlistsAuthoringMode
  context: WatchlistsAuthoringContext
}

type WatchlistsBasicStepCompletedEvent = {
  type: "watchlists_basic_step_completed"
  surface: "job_form"
  step: WatchlistsBasicStep
}

type WatchlistsTemplateRecipeAppliedEvent = {
  type: "watchlists_template_recipe_applied"
  surface: "template_editor"
  recipe: WatchlistsTemplateRecipe
  mode: WatchlistsAuthoringMode
}

type WatchlistsTemplatePreviewModeChangedEvent = {
  type: "watchlists_template_preview_mode_changed"
  surface: "template_editor"
  mode: WatchlistsTemplatePreviewMode
}

type WatchlistsTemplatePreviewRenderedEvent = {
  type: "watchlists_template_preview_rendered"
  surface: "template_editor"
  mode: "live"
  status: WatchlistsTemplatePreviewStatus
  warning_count: number
  run_id?: number | null
}

export type WatchlistsPreventionTelemetryEvent =
  | WatchlistsValidationBlockedEvent
  | WatchlistsAuthoringStartedEvent
  | WatchlistsAuthoringModeChangedEvent
  | WatchlistsAuthoringSavedEvent
  | WatchlistsBasicStepCompletedEvent
  | WatchlistsTemplateRecipeAppliedEvent
  | WatchlistsTemplatePreviewModeChangedEvent
  | WatchlistsTemplatePreviewRenderedEvent

type WatchlistsPreventionRecentEvent = {
  type: WatchlistsPreventionTelemetryEvent["type"]
  at: number
  details: EventDetails
}

type WatchlistsAuthoringSurfaceCounters = Record<WatchlistsAuthoringSurface, number>
type WatchlistsModeCounters = Record<WatchlistsAuthoringMode, number>
type WatchlistsAuthoringModeCountersBySurface = Record<
  WatchlistsAuthoringSurface,
  WatchlistsModeCounters
>
type WatchlistsTemplatePreviewModeCounters = Record<WatchlistsTemplatePreviewMode, number>
type WatchlistsTemplatePreviewRenderCounters = Record<WatchlistsTemplatePreviewStatus, number>

type WatchlistsModeSwitchCounters = {
  basic_to_advanced: number
  advanced_to_basic: number
}

type WatchlistsModeSwitchCountersBySurface = Record<
  WatchlistsAuthoringSurface,
  WatchlistsModeSwitchCounters
>

export type WatchlistsPreventionTelemetryState = {
  version: 1
  counters: Record<string, number>
  blocked_by_rule: Record<WatchlistsPreventionRule, number>
  blocked_by_surface: Record<WatchlistsPreventionSurface, number>
  authoring: {
    started_by_surface: WatchlistsAuthoringSurfaceCounters
    started_by_mode: WatchlistsAuthoringModeCountersBySurface
    mode_switches: WatchlistsModeSwitchCountersBySurface
    saved_by_surface: WatchlistsAuthoringSurfaceCounters
    saved_by_mode: WatchlistsAuthoringModeCountersBySurface
    saved_by_context: Record<WatchlistsAuthoringContext, number>
    basic_step_completed: Record<WatchlistsBasicStep, number>
    template_recipe_applied: Record<WatchlistsTemplateRecipe, number>
    template_preview: {
      mode_selected: WatchlistsTemplatePreviewModeCounters
      live_rendered: WatchlistsTemplatePreviewRenderCounters
      live_warning_total: number
    }
  }
  last_event_at: number | null
  recent_events: WatchlistsPreventionRecentEvent[]
}

const DEFAULT_AUTHORING_SURFACE_COUNTERS: WatchlistsAuthoringSurfaceCounters = {
  job_form: 0,
  template_editor: 0
}

const DEFAULT_MODE_COUNTERS: WatchlistsModeCounters = {
  basic: 0,
  advanced: 0
}

const DEFAULT_MODE_SWITCH_COUNTERS: WatchlistsModeSwitchCounters = {
  basic_to_advanced: 0,
  advanced_to_basic: 0
}

const DEFAULT_TEMPLATE_PREVIEW_MODE_COUNTERS: WatchlistsTemplatePreviewModeCounters = {
  static: 0,
  live: 0
}

const DEFAULT_TEMPLATE_PREVIEW_RENDER_COUNTERS: WatchlistsTemplatePreviewRenderCounters = {
  success: 0,
  error: 0
}

const DEFAULT_AUTHORING_BY_MODE: WatchlistsAuthoringModeCountersBySurface = {
  job_form: { ...DEFAULT_MODE_COUNTERS },
  template_editor: { ...DEFAULT_MODE_COUNTERS }
}

const DEFAULT_MODE_SWITCHES_BY_SURFACE: WatchlistsModeSwitchCountersBySurface = {
  job_form: { ...DEFAULT_MODE_SWITCH_COUNTERS },
  template_editor: { ...DEFAULT_MODE_SWITCH_COUNTERS }
}

const DEFAULT_STATE: WatchlistsPreventionTelemetryState = {
  version: 1,
  counters: {},
  blocked_by_rule: {
    scope_required: 0,
    schedule_too_frequent: 0,
    invalid_email_recipients: 0,
    group_cycle_parent: 0
  },
  blocked_by_surface: {
    job_form: 0,
    schedule_picker: 0,
    groups_tree: 0
  },
  authoring: {
    started_by_surface: { ...DEFAULT_AUTHORING_SURFACE_COUNTERS },
    started_by_mode: {
      job_form: { ...DEFAULT_MODE_COUNTERS },
      template_editor: { ...DEFAULT_MODE_COUNTERS }
    },
    mode_switches: {
      job_form: { ...DEFAULT_MODE_SWITCH_COUNTERS },
      template_editor: { ...DEFAULT_MODE_SWITCH_COUNTERS }
    },
    saved_by_surface: { ...DEFAULT_AUTHORING_SURFACE_COUNTERS },
    saved_by_mode: {
      job_form: { ...DEFAULT_MODE_COUNTERS },
      template_editor: { ...DEFAULT_MODE_COUNTERS }
    },
    saved_by_context: {
      create: 0,
      edit: 0
    },
    basic_step_completed: {
      scope: 0,
      schedule: 0,
      output: 0,
      review: 0
    },
    template_recipe_applied: {
      briefing_md: 0,
      newsletter_html: 0,
      mece_md: 0
    },
    template_preview: {
      mode_selected: { ...DEFAULT_TEMPLATE_PREVIEW_MODE_COUNTERS },
      live_rendered: { ...DEFAULT_TEMPLATE_PREVIEW_RENDER_COUNTERS },
      live_warning_total: 0
    }
  },
  last_event_at: null,
  recent_events: []
}

const incrementCounter = (counters: Record<string, number>, key: string) => {
  counters[key] = (counters[key] || 0) + 1
}

const toEventDetails = (
  event: WatchlistsPreventionTelemetryEvent
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
  async (): Promise<WatchlistsPreventionTelemetryState> => {
    const raw = await storage.get<WatchlistsPreventionTelemetryState | undefined>(
      WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
      blocked_by_rule: {
        ...DEFAULT_STATE.blocked_by_rule,
        ...(state.blocked_by_rule || {})
      },
      blocked_by_surface: {
        ...DEFAULT_STATE.blocked_by_surface,
        ...(state.blocked_by_surface || {})
      },
      authoring: {
        ...DEFAULT_STATE.authoring,
        ...(state.authoring || {}),
        started_by_surface: {
          ...DEFAULT_AUTHORING_SURFACE_COUNTERS,
          ...(state.authoring?.started_by_surface || {})
        },
        started_by_mode: {
          job_form: {
            ...DEFAULT_MODE_COUNTERS,
            ...(state.authoring?.started_by_mode?.job_form || {})
          },
          template_editor: {
            ...DEFAULT_MODE_COUNTERS,
            ...(state.authoring?.started_by_mode?.template_editor || {})
          }
        },
        mode_switches: {
          job_form: {
            ...DEFAULT_MODE_SWITCH_COUNTERS,
            ...(state.authoring?.mode_switches?.job_form || {})
          },
          template_editor: {
            ...DEFAULT_MODE_SWITCH_COUNTERS,
            ...(state.authoring?.mode_switches?.template_editor || {})
          }
        },
        saved_by_surface: {
          ...DEFAULT_AUTHORING_SURFACE_COUNTERS,
          ...(state.authoring?.saved_by_surface || {})
        },
        saved_by_mode: {
          job_form: {
            ...DEFAULT_MODE_COUNTERS,
            ...(state.authoring?.saved_by_mode?.job_form || {})
          },
          template_editor: {
            ...DEFAULT_MODE_COUNTERS,
            ...(state.authoring?.saved_by_mode?.template_editor || {})
          }
        },
        saved_by_context: {
          create: 0,
          edit: 0,
          ...(state.authoring?.saved_by_context || {})
        },
        basic_step_completed: {
          scope: 0,
          schedule: 0,
          output: 0,
          review: 0,
          ...(state.authoring?.basic_step_completed || {})
        },
        template_recipe_applied: {
          briefing_md: 0,
          newsletter_html: 0,
          mece_md: 0,
          ...(state.authoring?.template_recipe_applied || {})
        },
        template_preview: {
          mode_selected: {
            ...DEFAULT_TEMPLATE_PREVIEW_MODE_COUNTERS,
            ...(state.authoring?.template_preview?.mode_selected || {})
          },
          live_rendered: {
            ...DEFAULT_TEMPLATE_PREVIEW_RENDER_COUNTERS,
            ...(state.authoring?.template_preview?.live_rendered || {})
          },
          live_warning_total:
            typeof state.authoring?.template_preview?.live_warning_total === "number"
              ? state.authoring.template_preview.live_warning_total
              : 0
        }
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: WatchlistsPreventionTelemetryState) => {
  await storage.set(WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY, state)
}

export const trackWatchlistsPreventionTelemetry = async (
  event: WatchlistsPreventionTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()
    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "watchlists_validation_blocked": {
        state.blocked_by_rule[event.rule] += 1
        state.blocked_by_surface[event.surface] += 1
        break
      }
      case "watchlists_authoring_started": {
        state.authoring.started_by_surface[event.surface] += 1
        state.authoring.started_by_mode[event.surface][event.mode] += 1
        break
      }
      case "watchlists_authoring_mode_changed": {
        if (event.from_mode !== event.to_mode) {
          if (event.from_mode === "basic" && event.to_mode === "advanced") {
            state.authoring.mode_switches[event.surface].basic_to_advanced += 1
          }
          if (event.from_mode === "advanced" && event.to_mode === "basic") {
            state.authoring.mode_switches[event.surface].advanced_to_basic += 1
          }
        }
        break
      }
      case "watchlists_authoring_saved": {
        state.authoring.saved_by_surface[event.surface] += 1
        state.authoring.saved_by_mode[event.surface][event.mode] += 1
        state.authoring.saved_by_context[event.context] += 1
        break
      }
      case "watchlists_basic_step_completed": {
        state.authoring.basic_step_completed[event.step] += 1
        break
      }
      case "watchlists_template_recipe_applied": {
        state.authoring.template_recipe_applied[event.recipe] += 1
        break
      }
      case "watchlists_template_preview_mode_changed": {
        state.authoring.template_preview.mode_selected[event.mode] += 1
        break
      }
      case "watchlists_template_preview_rendered": {
        state.authoring.template_preview.live_rendered[event.status] += 1
        state.authoring.template_preview.live_warning_total += Number(
          event.warning_count || 0
        )
        break
      }
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
    console.warn("[watchlists-prevention-telemetry] Failed to record event", error)
  }
}

export const getWatchlistsPreventionTelemetryState =
  async (): Promise<WatchlistsPreventionTelemetryState> => readTelemetryState()

export const resetWatchlistsPreventionTelemetryState = async () => {
  await storage.set(WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}
