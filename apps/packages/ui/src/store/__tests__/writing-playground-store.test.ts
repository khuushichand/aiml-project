import { describe, expect, it } from "vitest"
import { useWritingPlaygroundStore } from "../writing-playground"

describe("writing playground store", () => {
  it("defaults activeSessionId to null", () => {
    const state = useWritingPlaygroundStore.getState()
    expect(state.activeSessionId).toBeNull()
  })

  it("updates activeSessionId", () => {
    useWritingPlaygroundStore.getState().setActiveSessionId("test-id")
    expect(useWritingPlaygroundStore.getState().activeSessionId).toBe("test-id")
    useWritingPlaygroundStore.getState().setActiveSessionId(null)
  })
})
