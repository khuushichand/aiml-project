import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import { TldwApiClient } from "@/services/tldw/TldwApiClient"

describe("TldwApiClient research run methods", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("lists linked deep research runs for a chat", async () => {
    mocks.bgRequest.mockResolvedValue({
      runs: [
        {
          run_id: "rs_123",
          query: "Investigate source of claim",
          status: "running",
          phase: "collecting",
          control_state: "running",
          latest_checkpoint_id: null,
          updated_at: "2026-03-08T20:00:00+00:00"
        }
      ]
    })

    const client = new TldwApiClient()
    const response = await client.listChatResearchRuns("chat_123")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/chats/chat_123/research-runs",
        method: "GET"
      })
    )
    expect(response).toEqual({
      runs: [
        {
          run_id: "rs_123",
          query: "Investigate source of claim",
          status: "running",
          phase: "collecting",
          control_state: "running",
          latest_checkpoint_id: null,
          updated_at: "2026-03-08T20:00:00+00:00"
        }
      ]
    })
  })
})
