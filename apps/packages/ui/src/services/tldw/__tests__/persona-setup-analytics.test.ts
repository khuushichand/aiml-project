import { afterEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn()
}))

vi.mock("../TldwApiClient", () => ({
  tldwClient: {
    fetchWithAuth: (...args: unknown[]) =>
      (mocks.fetchWithAuth as (...args: unknown[]) => unknown)(...args)
  }
}))

import {
  buildSetupEventKey,
  postPersonaSetupEvent
} from "../persona-setup-analytics"

describe("buildSetupEventKey", () => {
  it("builds stable event keys for once-only setup events", () => {
    expect(
      buildSetupEventKey({
        eventType: "step_viewed",
        step: "test"
      })
    ).toBe("step_viewed:test")
    expect(
      buildSetupEventKey({
        eventType: "step_completed",
        step: "commands"
      })
    ).toBe("step_completed:commands")
    expect(buildSetupEventKey({ eventType: "setup_started" })).toBe("setup_started")
    expect(buildSetupEventKey({ eventType: "setup_completed" })).toBe("setup_completed")
    expect(buildSetupEventKey({ eventType: "handoff_dismissed" })).toBe(
      "handoff_dismissed"
    )
    expect(buildSetupEventKey({ eventType: "first_post_setup_action" })).toBe(
      "first_post_setup_action"
    )
    expect(
      buildSetupEventKey({
        eventType: "detour_returned",
        detourSource: "live_failure"
      })
    ).toBe("detour_returned:live_failure")
    expect(buildSetupEventKey({ eventType: "retry_clicked" })).toBeUndefined()
  })
})

describe("postPersonaSetupEvent", () => {
  afterEach(() => {
    mocks.fetchWithAuth.mockReset()
  })

  it("posts normalized setup event payloads through the tldw client", async () => {
    mocks.fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({})
    })

    await postPersonaSetupEvent("garden-helper", {
      runId: "setup-run-1",
      eventType: "step_viewed",
      step: "test"
    })

    expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
      "/api/v1/persona/profiles/garden-helper/setup-events",
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          run_id: "setup-run-1",
          event_type: "step_viewed",
          step: "test",
          event_key: "step_viewed:test"
        })
      })
    )
  })
})
