import { describe, it, expect, vi, beforeEach } from "vitest"
import { migrateLocalWorkspacesToServer } from "@/store/workspace-migration"

describe("one-time workspace migration", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("migrates local workspaces to server", async () => {
    const upsertMock = vi.fn().mockResolvedValue({ id: "ws-1", version: 1 })
    const addSourceMock = vi.fn().mockResolvedValue({ id: "src-1", version: 1 })
    const addArtifactMock = vi.fn().mockResolvedValue({ id: "art-1", version: 1 })

    const localWorkspaces = [
      {
        id: "ws-1",
        name: "Local WS",
        sources: [{ id: "src-1", mediaId: 1, title: "V", sourceType: "video" }],
        artifacts: [{ id: "art-1", type: "summary", title: "S" }],
        notes: [],
      },
    ]

    await migrateLocalWorkspacesToServer(localWorkspaces, {
      upsertWorkspace: upsertMock,
      addSource: addSourceMock,
      addArtifact: addArtifactMock,
      addNote: vi.fn(),
    })

    expect(upsertMock).toHaveBeenCalledWith("ws-1", expect.objectContaining({ name: "Local WS" }))
    expect(addSourceMock).toHaveBeenCalledOnce()
    expect(addArtifactMock).toHaveBeenCalledOnce()
  })

  it("sets migration flag after completion", async () => {
    await migrateLocalWorkspacesToServer([], {
      upsertWorkspace: vi.fn(),
      addSource: vi.fn(),
      addArtifact: vi.fn(),
      addNote: vi.fn(),
    })
    expect(localStorage.getItem("workspace_migrated")).toBe("true")
  })

  it("skips migration if flag already set", async () => {
    localStorage.setItem("workspace_migrated", "true")
    const upsertMock = vi.fn()
    await migrateLocalWorkspacesToServer(
      [{ id: "ws-1", name: "X", sources: [], artifacts: [], notes: [] }],
      { upsertWorkspace: upsertMock, addSource: vi.fn(), addArtifact: vi.fn(), addNote: vi.fn() }
    )
    expect(upsertMock).not.toHaveBeenCalled()
  })
})
