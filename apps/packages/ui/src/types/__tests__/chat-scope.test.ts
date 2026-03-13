import { describe, it, expect } from "vitest"
import { toChatScopeParams } from "../chat-scope"

describe("toChatScopeParams", () => {
  it("defaults to global when no scope provided", () => {
    expect(toChatScopeParams()).toEqual({ scope_type: "global" })
  })

  it("returns global scope params for global type", () => {
    expect(toChatScopeParams({ type: "global" })).toEqual({ scope_type: "global" })
  })

  it("returns workspace scope params with workspace_id", () => {
    expect(toChatScopeParams({ type: "workspace", workspaceId: "ws-1" })).toEqual({
      scope_type: "workspace",
      workspace_id: "ws-1",
    })
  })
})
