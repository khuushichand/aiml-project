import { describe, expect, it } from "vitest"
import { useWritingPlaygroundStore } from "../writing-playground"

describe("writing playground store", () => {
  it("defaults workspace mode to draft", () => {
    const state = useWritingPlaygroundStore.getState()
    expect(state.workspaceMode).toBe("draft")
  })

  it("updates workspace mode", () => {
    useWritingPlaygroundStore.getState().setWorkspaceMode("manage")
    expect(useWritingPlaygroundStore.getState().workspaceMode).toBe("manage")
    useWritingPlaygroundStore.getState().setWorkspaceMode("draft")
  })
})
