import { describe, it, expect, vi } from "vitest"
import {
  hydrateWorkspaceFromServer,
  optimisticWorkspaceUpdate,
} from "@/store/workspace-api"

describe("workspace store API-first mutations", () => {
  it("hydrates workspace state from server on workspace switch", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      id: "ws-1",
      name: "Server WS",
      sources: [{ id: "src-1", title: "Video", version: 1 }],
      artifacts: [],
      notes: [],
      version: 3,
    })
    const state = await hydrateWorkspaceFromServer("ws-1", { fetch: mockFetch })
    expect(state.name).toBe("Server WS")
    expect(state.sources).toHaveLength(1)
    expect(state.version).toBe(3)
    expect(mockFetch).toHaveBeenCalledWith("ws-1")
  })

  it("hydrates with empty arrays when server returns no sub-resources", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      id: "ws-2",
      name: "Empty WS",
      version: 1,
    })
    const state = await hydrateWorkspaceFromServer("ws-2", { fetch: mockFetch })
    expect(state.sources).toEqual([])
    expect(state.artifacts).toEqual([])
    expect(state.notes).toEqual([])
  })

  it("performs optimistic update with rollback on 409", async () => {
    const mockUpdate = vi.fn().mockRejectedValue({
      status: 409,
      body: { version: 5, name: "Server Name" },
    })
    const result = await optimisticWorkspaceUpdate(
      { id: "ws-1", name: "Local Name", version: 3 },
      { name: "New Name" },
      { update: mockUpdate }
    )
    expect(result.name).toBe("Server Name")
    expect(result.version).toBe(5)
  })

  it("updates local store on successful server mutation", async () => {
    const mockUpdate = vi.fn().mockResolvedValue({
      id: "ws-1",
      name: "New",
      version: 4,
    })
    const result = await optimisticWorkspaceUpdate(
      { id: "ws-1", name: "Old", version: 3 },
      { name: "New" },
      { update: mockUpdate }
    )
    expect(result.name).toBe("New")
    expect(result.version).toBe(4)
  })

  it("rethrows non-409 errors", async () => {
    const mockUpdate = vi.fn().mockRejectedValue(new Error("Network error"))
    await expect(
      optimisticWorkspaceUpdate(
        { id: "ws-1", name: "X", version: 1 },
        { name: "Y" },
        { update: mockUpdate }
      )
    ).rejects.toThrow("Network error")
  })
})
