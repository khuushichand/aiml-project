// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest"

import { buildQueuedRequest } from "@/utils/chat-request-queue"
import { usePlaygroundSessionStore } from "../playground-session"

describe("playground-session-store", () => {
  beforeEach(() => {
    usePlaygroundSessionStore.getState().clearSession()
  })

  it("treats a fresh queue-only session as valid", () => {
    usePlaygroundSessionStore.getState().saveSession({
      queuedMessages: [buildQueuedRequest({ promptText: "Run this later" })]
    })

    expect(usePlaygroundSessionStore.getState().isSessionValid()).toBe(true)
  })
})
