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
      scopeKey: "scope:a",
      queuedMessages: [buildQueuedRequest({ promptText: "Run this later" })]
    })

    expect(usePlaygroundSessionStore.getState().isSessionValid()).toBe(true)
  })

  it("rejects persisted sessions when the expected scope key changes", () => {
    usePlaygroundSessionStore.getState().saveSession({
      scopeKey: "scope:a",
      queuedMessages: [buildQueuedRequest({ promptText: "Run this later" })]
    })

    expect(usePlaygroundSessionStore.getState().isSessionValid("scope:a")).toBe(
      true
    )
    expect(usePlaygroundSessionStore.getState().isSessionValid("scope:b")).toBe(
      false
    )
  })
})
