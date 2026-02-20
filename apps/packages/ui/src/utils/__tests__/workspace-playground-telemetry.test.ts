import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:workspace:playground:telemetry"

describe("workspace-playground-telemetry", () => {
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

  it("records counters and recent event details", async () => {
    const telemetry = await import("@/utils/workspace-playground-telemetry")
    await telemetry.resetWorkspacePlaygroundTelemetryState()

    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "conflict_modal_opened",
      workspace_id: "workspace-a",
      changed_fields_count: 2
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "connectivity_state_changed",
      from: "connected",
      to: "disconnected"
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "confusion_retry_burst",
      retry_count: 3,
      window_ms: 30000
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.conflict_modal_opened).toBe(1)
    expect(state.counters.connectivity_state_changed).toBe(1)
    expect(state.counters.confusion_retry_burst).toBe(1)
    expect(state.recent_events).toHaveLength(3)
    expect(state.recent_events[0]?.details.workspace_id).toBe("workspace-a")
    expect(state.recent_events[0]?.details.changed_fields_count).toBe(2)
    expect(state.recent_events[2]?.details.retry_count).toBe(3)
  })

  it("builds confusion dashboard queries and CSV exports", async () => {
    const telemetry = await import("@/utils/workspace-playground-telemetry")
    await telemetry.resetWorkspacePlaygroundTelemetryState()

    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "status_viewed",
      workspace_id: "workspace-a"
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "conflict_modal_opened",
      workspace_id: "workspace-a"
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "confusion_retry_burst",
      workspace_id: "workspace-a",
      retry_count: 3,
      window_ms: 30000
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "confusion_refresh_loop",
      workspace_id: "workspace-a",
      refresh_count: 3,
      window_ms: 45000
    })
    await telemetry.trackWorkspacePlaygroundTelemetry({
      type: "confusion_duplicate_submission",
      workspace_id: "workspace-a",
      duplicate_count: 2,
      window_ms: 12000
    })

    const state = await telemetry.getWorkspacePlaygroundTelemetryState()
    const confusionEvents = telemetry.queryWorkspacePlaygroundTelemetryEvents(
      state,
      {
        eventTypes: telemetry.WORKSPACE_PLAYGROUND_CONFUSION_EVENT_TYPES
      }
    )
    expect(confusionEvents).toHaveLength(3)

    const confusionSnapshot =
      telemetry.buildWorkspacePlaygroundConfusionDashboardSnapshot(state)
    expect(confusionSnapshot.counters.retryBurst).toBe(1)
    expect(confusionSnapshot.counters.refreshLoop).toBe(1)
    expect(confusionSnapshot.counters.duplicateSubmission).toBe(1)
    expect(confusionSnapshot.rates.retryPerStatusView).toBe(1)
    expect(confusionSnapshot.rates.refreshPerConflict).toBe(1)

    const csv = telemetry.buildWorkspacePlaygroundTelemetryEventsCsv(confusionEvents)
    expect(csv).toContain("event_type,timestamp_iso,timestamp_ms")
    expect(csv).toContain("confusion_retry_burst")
    expect(csv).toContain("confusion_refresh_loop")
    expect(csv).toContain("confusion_duplicate_submission")
  })
})
