import { describe, expect, it } from "vitest"
import { buildSyncBatchPlan } from "../sync-batch-utils"

describe("buildSyncBatchPlan", () => {
  it("builds push tasks for pending workspace prompts", () => {
    const plan = buildSyncBatchPlan([
      {
        prompt: {
          id: "p1",
          name: "Pending local",
          syncStatus: "pending",
          sourceSystem: "workspace"
        }
      }
    ])

    expect(plan.tasks).toEqual([
      expect.objectContaining({
        promptId: "p1",
        direction: "push"
      })
    ])
    expect(plan.skippedConflicts).toBe(0)
  })

  it("builds pull tasks for local studio prompts linked to server", () => {
    const plan = buildSyncBatchPlan([
      {
        prompt: {
          id: "p2",
          title: "Studio prompt",
          syncStatus: "local",
          sourceSystem: "studio",
          serverId: 88
        }
      }
    ])

    expect(plan.tasks).toEqual([
      expect.objectContaining({
        promptId: "p2",
        direction: "pull",
        serverId: 88
      })
    ])
  })

  it("skips conflict prompts and copilot pending prompts", () => {
    const plan = buildSyncBatchPlan([
      {
        prompt: {
          id: "p3",
          name: "Conflict prompt",
          syncStatus: "conflict",
          sourceSystem: "workspace"
        }
      },
      {
        prompt: {
          id: "p4",
          name: "Copilot pending",
          syncStatus: "pending",
          sourceSystem: "copilot"
        }
      }
    ])

    expect(plan.tasks).toHaveLength(0)
    expect(plan.skippedConflicts).toBe(1)
    expect(plan.skippedCopilotPending).toBe(1)
  })
})
