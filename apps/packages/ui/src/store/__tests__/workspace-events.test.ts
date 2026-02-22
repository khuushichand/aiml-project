import { describe, expect, it } from "vitest"
import {
  isWorkspaceBroadcastUpdateMessage,
  shouldSurfaceWorkspaceConflictNotice
} from "@/store/workspace-events"

describe("workspace events helpers", () => {
  it("validates workspace broadcast payload shape", () => {
    expect(
      isWorkspaceBroadcastUpdateMessage({
        type: "workspace-storage-updated",
        key: "tldw-workspace",
        updatedAt: Date.now()
      })
    ).toBe(true)

    expect(
      isWorkspaceBroadcastUpdateMessage({
        type: "workspace-storage-updated",
        key: 42,
        updatedAt: Date.now()
      })
    ).toBe(false)

    expect(isWorkspaceBroadcastUpdateMessage(null)).toBe(false)
  })

  it("throttles repeated cross-tab conflict prompts", () => {
    expect(shouldSurfaceWorkspaceConflictNotice(0, 1000, 8000)).toBe(true)
    expect(shouldSurfaceWorkspaceConflictNotice(1000, 5000, 8000)).toBe(false)
    expect(shouldSurfaceWorkspaceConflictNotice(1000, 9000, 8000)).toBe(true)
  })
})
