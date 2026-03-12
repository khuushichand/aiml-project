import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  getWorkflowInvestigation,
  getWorkflowStepAttempts,
  preflightWorkflowDefinition
} from "../workflows"

describe("workflow diagnostics service helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches workflow investigation data", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      run_id: "run-1",
      status: "failed",
      schema_version: 1,
      primary_failure: { reason_code_core: "runtime_error" }
    })

    const result = await getWorkflowInvestigation("run-1")

    expect(result.primary_failure?.reason_code_core).toBe("runtime_error")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/workflows/runs/run-1/investigation",
        method: "GET"
      })
    )
  })

  it("fetches workflow step attempts", async () => {
    mocks.bgRequest.mockResolvedValueOnce({
      run_id: "run-1",
      step_id: "step-2",
      attempts: [{ attempt: 2, status: "failed" }]
    })

    const result = await getWorkflowStepAttempts("run-1", "step-2")

    expect(result.attempts[0]?.attempt).toBe(2)
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/workflows/runs/run-1/steps/step-2/attempts",
        method: "GET"
      })
    )
  })

  it("posts workflow preflight requests", async () => {
    const definition = {
      name: "preflight-test",
      version: 1,
      steps: [{ id: "s1", type: "webhook", config: { url: "https://example.invalid" } }]
    }

    mocks.bgRequest.mockResolvedValueOnce({
      valid: true,
      errors: [],
      warnings: [{ code: "unsafe_replay_step", message: "unsafe" }]
    })

    const result = await preflightWorkflowDefinition({
      definition,
      validation_mode: "non-block"
    })

    expect(result.warnings[0]?.code).toBe("unsafe_replay_step")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/workflows/preflight",
        method: "POST",
        body: {
          definition,
          validation_mode: "non-block"
        }
      })
    )
  })
})
