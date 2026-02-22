import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:flashcards:errorRecoveryTelemetry"

describe("flashcards-error-recovery-telemetry", () => {
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

  it("records failure, retry, success-after-retry, and reload-recovery events", async () => {
    const telemetry = await import("@/utils/flashcards-error-recovery-telemetry")

    await telemetry.trackFlashcardsErrorRecoveryTelemetry({
      type: "flashcards_mutation_failed",
      surface: "review",
      operation: "submitting your review",
      error_code: "FLASHCARDS_NETWORK",
      status: 0,
      retriable: true
    })
    await telemetry.trackFlashcardsErrorRecoveryTelemetry({
      type: "flashcards_retry_requested",
      surface: "review",
      operation: "submitting your review",
      error_code: "FLASHCARDS_NETWORK"
    })
    await telemetry.trackFlashcardsErrorRecoveryTelemetry({
      type: "flashcards_retry_succeeded",
      surface: "review",
      operation: "submitting your review",
      error_code: "FLASHCARDS_NETWORK"
    })
    await telemetry.trackFlashcardsErrorRecoveryTelemetry({
      type: "flashcards_recovered_by_reload",
      surface: "cards",
      operation: "updating this card",
      error_code: "FLASHCARDS_VERSION_CONFLICT"
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.flashcards_mutation_failed).toBe(1)
    expect(state.counters.flashcards_retry_requested).toBe(1)
    expect(state.counters.flashcards_retry_succeeded).toBe(1)
    expect(state.counters.flashcards_recovered_by_reload).toBe(1)
    expect(state.failures_by_code.FLASHCARDS_NETWORK).toBe(1)
    expect(state.retries_by_code.FLASHCARDS_NETWORK).toBe(1)
    expect(state.retry_success_by_code.FLASHCARDS_NETWORK).toBe(1)
    expect(state.reload_recovery_by_code.FLASHCARDS_VERSION_CONFLICT).toBe(1)
    expect(state.recent_events).toHaveLength(4)
  })

  it("caps recent events to the configured maximum", async () => {
    const telemetry = await import("@/utils/flashcards-error-recovery-telemetry")

    for (let i = 0; i < 220; i += 1) {
      await telemetry.trackFlashcardsErrorRecoveryTelemetry({
        type: "flashcards_mutation_failed",
        surface: i % 2 === 0 ? "review" : "cards",
        operation: "synthetic",
        error_code: i % 3 === 0 ? "FLASHCARDS_NETWORK" : "FLASHCARDS_SERVER",
        status: 500,
        retriable: true
      })
    }

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.counters.flashcards_mutation_failed).toBe(220)
  })
})
