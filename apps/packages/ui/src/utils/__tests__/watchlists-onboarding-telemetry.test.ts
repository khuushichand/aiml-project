import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:watchlists:onboarding:telemetry"

describe("watchlists-onboarding-telemetry", () => {
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

  it("records quick setup and guided tour funnel counters", async () => {
    const telemetry = await import("@/utils/watchlists-onboarding-telemetry")

    await telemetry.trackWatchlistsOnboardingTelemetry({ type: "quick_setup_opened" })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_step_completed",
      step: "feed"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_step_completed",
      step: "monitor"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_completed",
      goal: "briefing",
      runNow: false,
      destination: "outputs"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({ type: "guided_tour_started" })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "guided_tour_step_viewed",
      step: 1
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "guided_tour_step_viewed",
      step: 2
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "guided_tour_dismissed",
      step: 2
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_run_succeeded",
      runId: 91
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_output_succeeded",
      outputId: 301,
      format: "md"
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.quick_setup_opened).toBe(1)
    expect(state.counters.quick_setup_step_completed).toBe(2)
    expect(state.counters.quick_setup_completed).toBe(1)
    expect(state.quick_setup.step_completed.feed).toBe(1)
    expect(state.quick_setup.step_completed.monitor).toBe(1)
    expect(state.quick_setup.completed_by_goal.briefing).toBe(1)
    expect(state.quick_setup.completed_without_run_now).toBe(1)
    expect(state.guided_tour.started).toBe(1)
    expect(state.guided_tour.dismissed).toBe(1)
    expect(state.guided_tour.step_views["1"]).toBe(1)
    expect(state.guided_tour.step_views["2"]).toBe(1)
    expect(state.value_milestones.first_run_succeeded).toBe(1)
    expect(state.value_milestones.first_output_succeeded).toBe(1)
    expect(state.value_milestones.first_run_succeeded_at).toBeTypeOf("number")
    expect(state.value_milestones.first_output_succeeded_at).toBeTypeOf("number")
    expect(state.recent_events).toHaveLength(10)
  })

  it("caps recent events to the configured maximum", async () => {
    const telemetry = await import("@/utils/watchlists-onboarding-telemetry")

    for (let i = 0; i < 260; i += 1) {
      await telemetry.trackWatchlistsOnboardingTelemetry({
        type: "guided_tour_step_viewed",
        step: ((i % 5) + 1) as 1 | 2 | 3 | 4 | 5
      })
    }

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.counters.guided_tour_step_viewed).toBe(260)
  })

  it("records first-value milestones only once", async () => {
    const telemetry = await import("@/utils/watchlists-onboarding-telemetry")

    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_run_succeeded",
      runId: 1
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_run_succeeded",
      runId: 2
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_output_succeeded",
      outputId: 11,
      format: "md"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "first_output_succeeded",
      outputId: 12,
      format: "html"
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.first_run_succeeded).toBe(1)
    expect(state.counters.first_output_succeeded).toBe(1)
    expect(state.value_milestones.first_run_succeeded).toBe(1)
    expect(state.value_milestones.first_output_succeeded).toBe(1)
    const milestoneEvents = state.recent_events.filter((event: Record<string, unknown>) =>
      event.type === "first_run_succeeded" || event.type === "first_output_succeeded"
    )
    expect(milestoneEvents).toHaveLength(2)
  })
})
