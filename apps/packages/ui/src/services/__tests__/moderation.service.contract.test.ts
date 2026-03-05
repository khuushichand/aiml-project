import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  getUserOverride,
  setUserOverride,
  type ModerationUserOverride
} from "@/services/moderation"

describe("moderation service contract", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("returns rules from getUserOverride payload", async () => {
    mocks.bgRequest.mockResolvedValue({
      enabled: true,
      rules: [
        {
          id: "r1",
          pattern: "bad",
          is_regex: false,
          action: "block",
          phase: "both"
        }
      ]
    })

    const response = await getUserOverride("alice")

    expect((response as any).rules?.[0]).toMatchObject({
      id: "r1",
      action: "block",
      phase: "both"
    })
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/moderation/users/alice"
      })
    )
  })

  it("sends rules in setUserOverride payload", async () => {
    const body: ModerationUserOverride = {
      enabled: true,
      rules: [
        {
          id: "n1",
          pattern: "heads up",
          is_regex: false,
          action: "warn",
          phase: "both"
        }
      ]
    }
    mocks.bgRequest.mockResolvedValue({ persisted: true })

    await setUserOverride("alice", body)

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "PUT",
        path: "/api/v1/moderation/users/alice",
        body: expect.objectContaining({
          rules: [
            expect.objectContaining({
              id: "n1",
              action: "warn",
              phase: "both"
            })
          ]
        })
      })
    )
  })
})
