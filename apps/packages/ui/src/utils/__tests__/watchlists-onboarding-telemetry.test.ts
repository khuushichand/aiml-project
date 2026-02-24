import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:watchlists:onboarding:telemetry"

describe("watchlists-onboarding-telemetry", () => {
  let storageMap: Map<string, unknown>
  let recordOnboardingTelemetryMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    storageMap = new Map<string, unknown>()
    recordOnboardingTelemetryMock = vi.fn().mockResolvedValue({ accepted: true })
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
    vi.doMock("@/services/watchlists", () => ({
      recordWatchlistsOnboardingTelemetry: (...args: unknown[]) =>
        recordOnboardingTelemetryMock(...args)
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
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_preview_loaded",
      preview: "candidate",
      total: 6,
      ingestable: 4,
      filtered: 2
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_preview_loaded",
      preview: "template",
      goal: "briefing",
      audioEnabled: true
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_preview_failed",
      preview: "candidate",
      reason: "load_failed"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_test_run_triggered",
      runId: 777
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_first_run_succeeded",
      source: "run_notifications",
      runId: 777
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_first_output_succeeded",
      source: "outputs"
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

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.quick_setup_opened).toBe(1)
    expect(state.counters.quick_setup_step_completed).toBe(2)
    expect(state.counters.quick_setup_completed).toBe(1)
    expect(state.quick_setup.step_completed.feed).toBe(1)
    expect(state.quick_setup.step_completed.monitor).toBe(1)
    expect(state.quick_setup.completed_by_goal.briefing).toBe(1)
    expect(state.quick_setup.completed_by_destination.outputs).toBe(1)
    expect(state.quick_setup.completed_without_run_now).toBe(1)
    expect(state.quick_setup.preview_loaded.candidate).toBe(1)
    expect(state.quick_setup.preview_loaded.template).toBe(1)
    expect(state.quick_setup.preview_failed.candidate).toBe(1)
    expect(state.quick_setup.test_run_triggered).toBe(1)
    expect(state.quick_setup.first_run_success).toBe(1)
    expect(state.quick_setup.first_output_success).toBe(1)
    expect(state.quick_setup.pending_first_run_success_at).toHaveLength(0)
    expect(state.quick_setup.pending_first_output_success_at).toHaveLength(0)
    expect(state.guided_tour.started).toBe(1)
    expect(state.guided_tour.dismissed).toBe(1)
    expect(state.guided_tour.step_views["1"]).toBe(1)
    expect(state.guided_tour.step_views["2"]).toBe(1)
    expect(state.recent_events).toHaveLength(14)
    expect(typeof state.session_id).toBe("string")
    expect(recordOnboardingTelemetryMock).toHaveBeenCalledTimes(14)
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

  it("builds UC2 funnel dashboard snapshot metrics", async () => {
    const telemetry = await import("@/utils/watchlists-onboarding-telemetry")

    await telemetry.trackWatchlistsOnboardingTelemetry({ type: "quick_setup_opened" })
    await telemetry.trackWatchlistsOnboardingTelemetry({ type: "quick_setup_opened" })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_step_completed",
      step: "review"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_completed",
      goal: "briefing",
      runNow: true,
      destination: "runs"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_preview_loaded",
      preview: "candidate",
      total: 4,
      ingestable: 3,
      filtered: 1
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_preview_failed",
      preview: "candidate",
      reason: "load_failed"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_test_run_triggered",
      runId: 42
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_first_run_succeeded",
      source: "run_notifications",
      runId: 42
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_first_output_succeeded",
      source: "overview"
    })
    await telemetry.trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_first_output_succeeded",
      source: "overview"
    })

    const state = await telemetry.getWatchlistsOnboardingTelemetryState()
    const snapshot = telemetry.buildWatchlistsUc2FunnelDashboardSnapshot(state)

    expect(snapshot.counters.quickSetupOpened).toBe(2)
    expect(snapshot.counters.quickSetupCompleted).toBe(1)
    expect(snapshot.counters.briefingCompletions).toBe(1)
    expect(snapshot.counters.runNowOptIns).toBe(1)
    expect(snapshot.counters.destination.runs).toBe(1)
    expect(snapshot.counters.previewLoaded.candidate).toBe(1)
    expect(snapshot.counters.previewFailed.candidate).toBe(1)
    expect(snapshot.counters.testRunTriggered).toBe(1)
    expect(snapshot.counters.firstRunSuccess).toBe(1)
    expect(snapshot.counters.firstOutputSuccess).toBe(1)
    expect(snapshot.rates.setupCompletionRate).toBe(0.5)
    expect(snapshot.rates.testRunTriggerRate).toBe(1)
    expect(snapshot.rates.firstSuccessProxyRate).toBe(1)
    expect(snapshot.rates.firstRunSuccessRate).toBe(1)
    expect(snapshot.rates.firstOutputSuccessRate).toBe(1)
    expect(snapshot.rates.setupDropoffRate).toBe(0.5)
    expect(snapshot.rates.runSuccessDropoffRate).toBe(0)
    expect(snapshot.rates.outputSuccessDropoffRate).toBe(0)
    expect(snapshot.timings.medianSecondsToSetupCompletion).toBeGreaterThanOrEqual(0)
    expect(snapshot.timings.medianSecondsToFirstRunSuccess).toBeGreaterThanOrEqual(0)
    expect(snapshot.timings.medianSecondsToFirstOutputSuccess).toBeGreaterThanOrEqual(0)
  })

  it("swallows backend telemetry ingest failures and keeps local state updates", async () => {
    recordOnboardingTelemetryMock.mockRejectedValueOnce(new Error("backend unavailable"))
    const telemetry = await import("@/utils/watchlists-onboarding-telemetry")

    await telemetry.trackWatchlistsOnboardingTelemetry({ type: "quick_setup_opened" })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.quick_setup_opened).toBe(1)
    expect(recordOnboardingTelemetryMock).toHaveBeenCalledTimes(1)
  })
})
