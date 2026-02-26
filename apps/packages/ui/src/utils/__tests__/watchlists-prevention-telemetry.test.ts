import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:watchlists:preventionTelemetry"

describe("watchlists-prevention-telemetry", () => {
  let storageMap: Map<string, unknown>

  beforeEach(() => {
    storageMap = new Map<string, unknown>()
    vi.resetModules()
    vi.doMock("@/utils/safe-storage", () => ({
      createSafeStorage: () => ({
        get: async (key: string) => storageMap.get(key),
        set: async (key: string, value: unknown) => {
          storageMap.set(key, value)
        },
        remove: async (key: string) => {
          storageMap.delete(key)
        }
      })
    }))
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  it("records validation blocks and authoring adoption counters", async () => {
    const telemetry = await import("@/utils/watchlists-prevention-telemetry")

    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_validation_blocked",
      surface: "job_form",
      rule: "scope_required",
      remediation: "select_scope"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_validation_blocked",
      surface: "schedule_picker",
      rule: "schedule_too_frequent",
      remediation: "increase_interval",
      minutes: 5
    })

    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_authoring_started",
      surface: "job_form",
      mode: "basic",
      context: "create"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_authoring_mode_changed",
      surface: "job_form",
      from_mode: "basic",
      to_mode: "advanced",
      context: "create"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_basic_step_completed",
      surface: "job_form",
      step: "scope"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_basic_step_completed",
      surface: "job_form",
      step: "schedule"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_authoring_saved",
      surface: "job_form",
      mode: "advanced",
      context: "create"
    })

    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_authoring_started",
      surface: "template_editor",
      mode: "basic",
      context: "create"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_template_recipe_applied",
      surface: "template_editor",
      recipe: "newsletter_html",
      mode: "basic"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_authoring_saved",
      surface: "template_editor",
      mode: "basic",
      context: "create"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_template_preview_mode_changed",
      surface: "template_editor",
      mode: "live"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_template_preview_rendered",
      surface: "template_editor",
      mode: "live",
      status: "success",
      warning_count: 2,
      run_id: 101
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_template_preview_rendered",
      surface: "template_editor",
      mode: "live",
      status: "error",
      warning_count: 0,
      run_id: 102
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>

    expect(state.counters.watchlists_validation_blocked).toBe(2)
    expect(state.blocked_by_rule.scope_required).toBe(1)
    expect(state.blocked_by_rule.schedule_too_frequent).toBe(1)
    expect(state.blocked_by_surface.job_form).toBe(1)
    expect(state.blocked_by_surface.schedule_picker).toBe(1)

    expect(state.counters.watchlists_authoring_started).toBe(2)
    expect(state.counters.watchlists_authoring_mode_changed).toBe(1)
    expect(state.counters.watchlists_authoring_saved).toBe(2)
    expect(state.counters.watchlists_basic_step_completed).toBe(2)
    expect(state.counters.watchlists_template_recipe_applied).toBe(1)
    expect(state.counters.watchlists_template_preview_mode_changed).toBe(1)
    expect(state.counters.watchlists_template_preview_rendered).toBe(2)

    expect(state.authoring.started_by_surface.job_form).toBe(1)
    expect(state.authoring.started_by_surface.template_editor).toBe(1)
    expect(state.authoring.started_by_mode.job_form.basic).toBe(1)
    expect(state.authoring.started_by_mode.template_editor.basic).toBe(1)
    expect(state.authoring.mode_switches.job_form.basic_to_advanced).toBe(1)
    expect(state.authoring.saved_by_mode.job_form.advanced).toBe(1)
    expect(state.authoring.saved_by_mode.template_editor.basic).toBe(1)
    expect(state.authoring.saved_by_context.create).toBe(2)
    expect(state.authoring.basic_step_completed.scope).toBe(1)
    expect(state.authoring.basic_step_completed.schedule).toBe(1)
    expect(state.authoring.template_recipe_applied.newsletter_html).toBe(1)
    expect(state.authoring.template_preview.mode_selected.live).toBe(1)
    expect(state.authoring.template_preview.live_rendered.success).toBe(1)
    expect(state.authoring.template_preview.live_rendered.error).toBe(1)
    expect(state.authoring.template_preview.live_warning_total).toBe(2)
    expect(state.recent_events).toHaveLength(13)
  })

  it("caps recent events to the configured maximum", async () => {
    const telemetry = await import("@/utils/watchlists-prevention-telemetry")

    for (let i = 0; i < 220; i += 1) {
      await telemetry.trackWatchlistsPreventionTelemetry({
        type: "watchlists_validation_blocked",
        surface: i % 2 === 0 ? "job_form" : "groups_tree",
        rule: i % 3 === 0 ? "scope_required" : "group_cycle_parent",
        remediation: "synthetic"
      })
    }

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.counters.watchlists_validation_blocked).toBe(220)
  })
})
