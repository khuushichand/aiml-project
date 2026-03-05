import { describe, expect, test } from "vitest"

import { createInitialChatLoopState, reduceLoopEvent } from "@/services/chat-loop/reducer"
import type { ChatLoopEvent } from "@/services/chat-loop/types"

describe("chat-loop reducer", () => {
  test("approval_required adds pending approval", () => {
    const state = createInitialChatLoopState()
    const next = reduceLoopEvent(
      state,
      {
        run_id: "run_1",
        seq: 3,
        event: "approval_required",
        data: { approval_id: "a1", tool_call_id: "tc1" },
      } as ChatLoopEvent,
    )

    expect(next.pendingApprovals).toHaveLength(1)
    expect(next.pendingApprovals[0]?.approvalId).toBe("a1")
  })

  test("run_started resets transient state for new runs", () => {
    const first = reduceLoopEvent(
      createInitialChatLoopState(),
      {
        run_id: "run_1",
        seq: 1,
        event: "approval_required",
        data: { approval_id: "a1" },
      } as ChatLoopEvent,
    )
    const running = reduceLoopEvent(
      first,
      {
        run_id: "run_1",
        seq: 2,
        event: "tool_started",
        data: { tool_call_id: "tc1" },
      } as ChatLoopEvent,
    )
    const nextRun = reduceLoopEvent(
      running,
      {
        run_id: "run_2",
        seq: 1,
        event: "run_started",
        data: {},
      } as ChatLoopEvent,
    )

    expect(nextRun.runId).toBe("run_2")
    expect(nextRun.pendingApprovals).toHaveLength(0)
    expect(nextRun.inflightToolCallIds).toHaveLength(0)
    expect(nextRun.status).toBe("running")
  })

  test("run_complete clears inflight tools and approvals", () => {
    const withState = {
      ...createInitialChatLoopState(),
      runId: "run_1",
      pendingApprovals: [{ approvalId: "a1", seq: 2 }],
      inflightToolCallIds: ["tc1"],
      status: "running" as const,
    }
    const completed = reduceLoopEvent(
      withState,
      {
        run_id: "run_1",
        seq: 3,
        event: "run_complete",
        data: {},
      } as ChatLoopEvent,
    )

    expect(completed.status).toBe("complete")
    expect(completed.pendingApprovals).toHaveLength(0)
    expect(completed.inflightToolCallIds).toHaveLength(0)
  })
})
