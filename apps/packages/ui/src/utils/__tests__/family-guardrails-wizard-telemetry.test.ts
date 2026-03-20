import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:family-guardrails:wizard:telemetry"

describe("family-guardrails-wizard-telemetry", () => {
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

  it("records step and completion events by cohort", async () => {
    const telemetry = await import("@/utils/family-guardrails-wizard-telemetry")
    await telemetry.resetFamilyGuardrailsWizardTelemetryState()

    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "setup_started",
      cohort: "new_household",
      step: "basics",
      mode: "family"
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "step_completed",
      cohort: "new_household",
      step: "dependents",
      new_invite_count: 2,
      existing_account_count: 1
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "setup_completed",
      cohort: "new_household",
      step: "review",
      active_count: 1,
      pending_count: 2,
      failed_count: 0
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "draft_resumed",
      cohort: "existing_household",
      step: "review",
      household_status: "invites_pending"
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.setup_started).toBe(1)
    expect(state.counters.step_completed).toBe(1)
    expect(state.counters.setup_completed).toBe(1)
    expect(state.counters.draft_resumed).toBe(1)
    expect(state.by_cohort.new_household.setup_started).toBe(1)
    expect(state.by_cohort.new_household.setup_completed).toBe(1)
    expect(state.by_cohort.existing_household.draft_resumed).toBe(1)
    expect(state.recent_events).toHaveLength(4)
    expect(state.recent_events[1]?.details.new_invite_count).toBe(2)
    expect(state.recent_events[2]?.details.pending_count).toBe(2)
  })

  it("builds rollout completion and drop-off rates by cohort", async () => {
    const telemetry = await import("@/utils/family-guardrails-wizard-telemetry")
    await telemetry.resetFamilyGuardrailsWizardTelemetryState()

    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "setup_started",
      cohort: "new_household",
      step: "basics"
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "drop_off",
      cohort: "new_household",
      step: "dependents"
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "draft_resumed",
      cohort: "existing_household",
      step: "tracker"
    })
    await telemetry.trackFamilyGuardrailsWizardTelemetry({
      type: "setup_completed",
      cohort: "existing_household",
      step: "review"
    })

    const state = await telemetry.getFamilyGuardrailsWizardTelemetryState()
    const snapshot = telemetry.buildFamilyGuardrailsWizardRolloutSnapshot(state)

    expect(snapshot.completionRates.new_household).toBe(0)
    expect(snapshot.dropOffRates.new_household).toBe(1)
    expect(snapshot.completionRates.existing_household).toBe(1)
    expect(snapshot.dropOffRates.existing_household).toBe(0)
  })
})
