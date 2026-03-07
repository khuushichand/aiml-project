import { describe, expect, it } from "vitest"

import {
  blockQueuedRequest,
  buildQueuedRequest,
  moveQueuedRequestToFront
} from "@/utils/chat-request-queue"

describe("chat request queue helpers", () => {
  it("promotes the selected queued request while preserving the remaining order", () => {
    const first = buildQueuedRequest({ promptText: "first" })
    const second = buildQueuedRequest({ promptText: "second" })
    const third = buildQueuedRequest({ promptText: "third" })

    const reordered = moveQueuedRequestToFront(
      [first, second, third],
      third.id
    )

    expect(reordered.map((item) => item.promptText)).toEqual([
      "third",
      "first",
      "second"
    ])
  })

  it("marks a queued request blocked without losing its snapshot", () => {
    const item = buildQueuedRequest({
      promptText: "needs repair",
      snapshot: { selectedModel: "gpt-4o-mini", chatMode: "normal" }
    })

    const blocked = blockQueuedRequest(item, "missing_attachment")

    expect(blocked.status).toBe("blocked")
    expect(blocked.blockedReason).toBe("missing_attachment")
    expect(blocked.snapshot.selectedModel).toBe("gpt-4o-mini")
  })
})
