// @vitest-environment jsdom
import { describe, expect, it } from "vitest"

import {
  createChatSurfaceCoordinatorStore,
  shouldEnableOptionalResource
} from "@/store/chat-surface-coordinator"

describe("chat-surface-coordinator", () => {
  it("keeps server history disabled until the user engages the panel", () => {
    const store = createChatSurfaceCoordinatorStore()

    store.getState().setRouteContext({ routeId: "chat", surface: "webui" })
    store.getState().setPanelVisible("server-history", true)

    expect(
      shouldEnableOptionalResource(store.getState(), "server-history")
    ).toBe(false)

    store.getState().markPanelEngaged("server-history")

    expect(
      shouldEnableOptionalResource(store.getState(), "server-history")
    ).toBe(true)
  })
})
