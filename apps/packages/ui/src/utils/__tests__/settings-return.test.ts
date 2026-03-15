import { beforeEach, describe, expect, it } from "vitest"

import {
  clearSettingsReturnTo,
  getSettingsReturnTo,
  setSettingsReturnTo
} from "@/utils/settings-return"

describe("settings return target", () => {
  beforeEach(() => {
    sessionStorage.clear()
    clearSettingsReturnTo()
  })

  it("stores non-settings routes for return navigation", () => {
    setSettingsReturnTo("/media")

    expect(getSettingsReturnTo()).toBe("/media")
  })

  it("stores chat context for chat return targets", () => {
    setSettingsReturnTo("/chat", {
      historyId: "history-123",
      serverChatId: "server-chat-456"
    })

    expect(getSettingsReturnTo()).toBe(
      "/chat?settingsHistoryId=history-123&settingsServerChatId=server-chat-456"
    )
  })

  it("does not overwrite return target with settings routes", () => {
    setSettingsReturnTo("/chat", {
      historyId: "history-abc"
    })
    setSettingsReturnTo("/settings/tldw")

    expect(getSettingsReturnTo()).toBe("/chat?settingsHistoryId=history-abc")
  })
})
