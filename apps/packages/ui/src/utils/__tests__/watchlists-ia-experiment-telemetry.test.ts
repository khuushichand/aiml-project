import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  flushWatchlistsIaExperimentSession,
  WATCHLISTS_IA_EXPERIMENT_STORAGE_KEY,
  readWatchlistsIaExperimentTelemetryState,
  trackWatchlistsIaExperimentTransition
} from "@/utils/watchlists-ia-experiment-telemetry"

const mocks = vi.hoisted(() => ({
  recordWatchlistsIaExperimentTelemetryMock: vi.fn()
}))

vi.mock("@/services/watchlists", () => ({
  recordWatchlistsIaExperimentTelemetry: (...args: unknown[]) =>
    mocks.recordWatchlistsIaExperimentTelemetryMock(...args)
}))

describe("watchlists-ia-experiment-telemetry", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.recordWatchlistsIaExperimentTelemetryMock.mockResolvedValue({ accepted: true })
    localStorage.removeItem(WATCHLISTS_IA_EXPERIMENT_STORAGE_KEY)
  })

  it("records local state and emits a telemetry payload", () => {
    const initial = trackWatchlistsIaExperimentTransition(null, "sources", "experimental")
    expect(initial).not.toBeNull()
    expect(initial?.variant).toBe("experimental")
    expect(initial?.transitions).toBe(0)
    expect(initial?.visited_tabs).toEqual(["sources"])

    const next = trackWatchlistsIaExperimentTransition("sources", "runs", "experimental")
    expect(next?.transitions).toBe(1)
    expect(next?.visited_tabs).toContain("sources")
    expect(next?.visited_tabs).toContain("runs")

    expect(mocks.recordWatchlistsIaExperimentTelemetryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: "experimental",
        previous_tab: "sources",
        current_tab: "runs",
        transitions: 1
      })
    )
  })

  it("keeps local telemetry state when sink emission fails", () => {
    mocks.recordWatchlistsIaExperimentTelemetryMock.mockRejectedValue(
      new Error("network down")
    )

    expect(() =>
      trackWatchlistsIaExperimentTransition(null, "sources", "baseline")
    ).not.toThrow()

    const persisted = readWatchlistsIaExperimentTelemetryState()
    expect(persisted).not.toBeNull()
    expect(persisted?.variant).toBe("baseline")
    expect(persisted?.visited_tabs).toContain("sources")
  })

  it("flushes session heartbeat without incrementing transitions", () => {
    const initial = trackWatchlistsIaExperimentTransition(null, "sources", "experimental")
    const flushed = flushWatchlistsIaExperimentSession("sources", "experimental")

    expect(initial).not.toBeNull()
    expect(flushed).not.toBeNull()
    expect(flushed?.transitions).toBe(initial?.transitions)
    expect(mocks.recordWatchlistsIaExperimentTelemetryMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        variant: "experimental",
        previous_tab: "sources",
        current_tab: "sources",
        transitions: initial?.transitions
      })
    )
    expect(flushed?.last_seen_at).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })
})
