import { describe, expect, test } from "vitest"

import { extractChatLoopEvent } from "@/services/chat-loop/stream"

describe("chat-loop stream parser", () => {
  test("extracts loop event fields from nested data payload", () => {
    const parsed = extractChatLoopEvent({
      event: "tool_finished",
      data: {
        run_id: "run_1",
        seq: 5,
        tool_call_id: "tc_1",
      },
    })

    expect(parsed).toEqual({
      run_id: "run_1",
      seq: 5,
      event: "tool_finished",
      data: {
        run_id: "run_1",
        seq: 5,
        tool_call_id: "tc_1",
      },
    })
  })

  test("returns null for non-loop events", () => {
    const parsed = extractChatLoopEvent({
      event: "stream_start",
      data: { foo: "bar" },
    })

    expect(parsed).toBeNull()
  })
})
