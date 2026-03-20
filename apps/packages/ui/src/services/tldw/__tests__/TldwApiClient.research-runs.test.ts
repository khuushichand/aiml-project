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

  it("creates follow-up research runs with bounded launch metadata", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "rs_456",
      status: "running",
      phase: "collecting",
      control_state: "running"
    })

    const client = new TldwApiClient()
    await client.createResearchRun({
      query: "Investigate source of claim",
      source_policy: "balanced",
      autonomy_mode: "checkpointed",
      chat_handoff: {
        chat_id: "chat_123",
        launch_message_id: "msg_123"
      },
      follow_up: {
        question: "Investigate source of claim",
        background: {
          question: "Seed question",
          outline: [{ title: "Overview" }],
          key_claims: [{ claim_id: "claim_1", text: "Claim one" }],
          unresolved_questions: ["What changed?"],
          verification_summary: {
            supported_claim_count: 1,
            unsupported_claim_count: 0
          },
          source_trust_summary: {
            high_trust_count: 1,
            low_trust_count: 0
          }
        }
      }
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/research/runs",
        method: "POST",
        body: expect.objectContaining({
          query: "Investigate source of claim",
          source_policy: "balanced",
          autonomy_mode: "checkpointed",
          chat_handoff: {
            chat_id: "chat_123",
            launch_message_id: "msg_123"
          },
          follow_up: {
            question: "Investigate source of claim",
            background: expect.objectContaining({
              question: "Seed question"
            })
          }
        })
      })
    )
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
