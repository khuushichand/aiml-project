import { describe, expect, it } from "vitest"
import {
  WRITING_WORKSPACE_MODE_STORAGE_KEY,
  normalizeWritingWorkspaceMode,
  resolveInitialWorkspaceMode
} from "../writing-workspace-mode-prefs"

describe("writing workspace mode prefs", () => {
  it("uses stable storage key", () => {
    expect(WRITING_WORKSPACE_MODE_STORAGE_KEY).toBe("writing:workspace-mode")
  })

  it("normalizes unknown values to draft", () => {
    expect(normalizeWritingWorkspaceMode("x")).toBe("draft")
    expect(normalizeWritingWorkspaceMode(undefined)).toBe("draft")
  })

  it("keeps valid values", () => {
    expect(normalizeWritingWorkspaceMode("draft")).toBe("draft")
    expect(normalizeWritingWorkspaceMode("manage")).toBe("manage")
  })

  it("applies mode precedence for first-load vs persisted value", () => {
    expect(resolveInitialWorkspaceMode(undefined)).toBe("draft")
    expect(resolveInitialWorkspaceMode("manage")).toBe("manage")
    expect(resolveInitialWorkspaceMode("draft")).toBe("draft")
  })
})
