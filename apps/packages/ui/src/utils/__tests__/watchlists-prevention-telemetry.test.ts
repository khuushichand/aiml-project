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

  it("records prevention blocks by rule and surface", async () => {
    const telemetry = await import("@/utils/watchlists-prevention-telemetry")

    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_validation_blocked",
      surface: "job_form",
      rule: "scope_required",
      remediation: "select_scope"
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_validation_blocked",
      surface: "job_form",
      rule: "invalid_email_recipients",
      remediation: "fix_recipients",
      count: 3
    })
    await telemetry.trackWatchlistsPreventionTelemetry({
      type: "watchlists_validation_blocked",
      surface: "schedule_picker",
      rule: "schedule_too_frequent",
      remediation: "increase_interval",
      minutes: 5
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.watchlists_validation_blocked).toBe(3)
    expect(state.blocked_by_rule.scope_required).toBe(1)
    expect(state.blocked_by_rule.invalid_email_recipients).toBe(1)
    expect(state.blocked_by_rule.schedule_too_frequent).toBe(1)
    expect(state.blocked_by_surface.job_form).toBe(2)
    expect(state.blocked_by_surface.schedule_picker).toBe(1)
    expect(state.recent_events).toHaveLength(3)
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

