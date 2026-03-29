import { describe, expect, it } from "vitest"
import type {
  WorkspaceSource,
  WorkspaceSourceFolder,
  WorkspaceSourceFolderMembership,
  WorkspaceSourceTransferSnapshot
} from "@/types/workspace"
import { applyWorkspaceSourceTransfer } from "../workspace-source-transfer"

const now = new Date("2026-03-28T12:00:00.000Z")
const sourceFolderFallbackName = "Untitled Folder"

const createSource = (
  overrides: Partial<WorkspaceSource> &
    Pick<WorkspaceSource, "id" | "mediaId" | "title">
): WorkspaceSource => ({
  id: overrides.id,
  mediaId: overrides.mediaId,
  title: overrides.title,
  type: overrides.type || "pdf",
  status: overrides.status || "ready",
  addedAt: overrides.addedAt || now
})

const createFolder = (
  overrides: Partial<WorkspaceSourceFolder> &
    Pick<WorkspaceSourceFolder, "id" | "name">
): WorkspaceSourceFolder => ({
  id: overrides.id,
  workspaceId: overrides.workspaceId || "origin-workspace",
  name: overrides.name,
  parentFolderId: overrides.parentFolderId ?? null,
  createdAt: overrides.createdAt || now,
  updatedAt: overrides.updatedAt || now
})

const createMembership = (
  overrides: WorkspaceSourceFolderMembership
): WorkspaceSourceFolderMembership => ({
  folderId: overrides.folderId,
  sourceId: overrides.sourceId
})

const createSnapshot = (
  overrides: Partial<WorkspaceSourceTransferSnapshot> &
    Pick<WorkspaceSourceTransferSnapshot, "workspaceId">
): WorkspaceSourceTransferSnapshot => ({
  workspaceId: overrides.workspaceId,
  sources: overrides.sources || [],
  sourceFolders: overrides.sourceFolders || [],
  sourceFolderMemberships: overrides.sourceFolderMemberships || []
})

const createIdFactory = (): ((kind: "source" | "folder") => string) => {
  let sourceIndex = 0
  let folderIndex = 0
  return (kind) => {
    if (kind === "source") {
      sourceIndex += 1
      return `generated-source-${sourceIndex}`
    }
    folderIndex += 1
    return `generated-folder-${folderIndex}`
  }
}

describe("applyWorkspaceSourceTransfer", () => {
  it("copies selected sources into a destination by shared mediaId without mutating the origin", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Origin One" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace"
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.originSnapshot.sources).toHaveLength(1)
    expect(result.originSnapshot.sources[0]?.id).toBe("origin-s1")
    expect(result.originSnapshot.sources[0]?.mediaId).toBe(101)
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources[0]?.mediaId).toBe(101)
    expect(result.destinationSnapshot.sources[0]?.id).not.toBe("origin-s1")
    expect(result.transferredMediaIds).toEqual([101])
    expect(result.transferredDestinationSourceIds).toHaveLength(1)
    expect(result.removedOriginSourceIds).toEqual([])
  })

  it("preserves the union of memberships when multiple selected wrappers share a mediaId", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Origin One" }),
        createSource({ id: "origin-s2", mediaId: 101, title: "Origin Two" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-evidence", name: "Evidence" }),
        createFolder({ id: "origin-reference", name: "Reference" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-evidence", sourceId: "origin-s1" }),
        createMembership({ folderId: "origin-reference", sourceId: "origin-s2" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace"
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1", "origin-s2"],
      conflictResolutions: {},
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.transferredMediaIds).toEqual([101])
    expect(result.transferredDestinationSourceIds).toEqual(["generated-source-1"])
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sourceFolderMemberships).toEqual(
      expect.arrayContaining([
        { folderId: "generated-folder-1", sourceId: "generated-source-1" },
        { folderId: "generated-folder-2", sourceId: "generated-source-1" }
      ])
    )
    expect(result.destinationSnapshot.sourceFolderMemberships).toHaveLength(2)
    expect(result.originSnapshot.sources).toHaveLength(2)
  })

  it("moves selected sources only after the destination work is prepared and reports newly emptied folders", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" }),
        createSource({ id: "origin-s2", mediaId: 202, title: "Retained" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-empty", name: "Empty Me" }),
        createFolder({ id: "origin-keep", name: "Keep Me" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-empty", sourceId: "origin-s1" }),
        createMembership({ folderId: "origin-keep", sourceId: "origin-s2" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace",
      sources: []
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "move",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.originSnapshot.sources.map((source) => source.id)).toEqual([
      "origin-s2"
    ])
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources[0]?.mediaId).toBe(101)
    expect(result.newlyEmptiedOriginFolderIds).toEqual(["origin-empty"])
    expect(result.newlyEmptiedOriginFolderIds).not.toContain("origin-keep")
    expect(result.removedOriginSourceIds).toEqual(["origin-s1"])
  })

  it("keys conflicts by mediaId and replaces only transferred memberships when requested", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-evidence", name: " Evidence " })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-evidence", sourceId: "origin-s1" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace",
      sources: [
        createSource({
          id: "dest-existing-s1",
          mediaId: 101,
          title: "Existing destination"
        })
      ],
      sourceFolders: [
        createFolder({ id: "dest-evidence", name: "evidence" }),
        createFolder({ id: "dest-reference", name: "Reference" })
      ],
      sourceFolderMemberships: [
        createMembership({
          folderId: "dest-evidence",
          sourceId: "dest-existing-s1"
        }),
        createMembership({
          folderId: "dest-reference",
          sourceId: "dest-existing-s1"
        })
      ]
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: { 101: "replace-transferred-folders" },
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.conflictsResolved).toEqual([101])
    expect(result.transferredMediaIds).toEqual([101])
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources[0]?.id).toBe("dest-existing-s1")
    expect(result.destinationSnapshot.sourceFolderMemberships).toEqual(
      expect.arrayContaining([
        { folderId: "dest-evidence", sourceId: "dest-existing-s1" },
        { folderId: "dest-reference", sourceId: "dest-existing-s1" }
      ])
    )
    expect(result.originSnapshot.sources).toHaveLength(1)
    expect(result.originSnapshot.sources[0]?.id).toBe("origin-s1")
  })

  it("merges transferred folders into an existing destination source when merge-folders is requested", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-evidence", name: "Evidence" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-evidence", sourceId: "origin-s1" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace",
      sources: [
        createSource({
          id: "dest-existing-s1",
          mediaId: 101,
          title: "Existing destination"
        })
      ],
      sourceFolders: [
        createFolder({ id: "dest-reference", name: "Reference" })
      ],
      sourceFolderMemberships: [
        createMembership({
          folderId: "dest-reference",
          sourceId: "dest-existing-s1"
        })
      ]
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: { 101: "merge-folders" },
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.conflictsResolved).toEqual([101])
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources[0]?.id).toBe("dest-existing-s1")
    expect(result.destinationSnapshot.sourceFolderMemberships).toEqual(
      expect.arrayContaining([
        { folderId: "dest-reference", sourceId: "dest-existing-s1" },
        { folderId: "generated-folder-1", sourceId: "dest-existing-s1" }
      ])
    )
    expect(result.destinationSnapshot.sourceFolderMemberships).toHaveLength(2)
  })

  it("skips conflicting sources by mediaId when the skip policy is requested", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace",
      sources: [
        createSource({
          id: "dest-existing-s1",
          mediaId: 101,
          title: "Existing destination"
        })
      ]
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: { 101: "skip" },
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.conflictsSkipped).toEqual([101])
    expect(result.transferredMediaIds).toEqual([])
    expect(result.transferredDestinationSourceIds).toEqual([])
    expect(result.originSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources).toHaveLength(1)
    expect(result.destinationSnapshot.sources[0]?.id).toBe("dest-existing-s1")
  })

  it("reuses matching destination folder paths with trim and case-insensitive sibling semantics", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-parent", name: "  Parent  " }),
        createFolder({
          id: "origin-child",
          name: " Evidence ",
          parentFolderId: "origin-parent"
        })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-child", sourceId: "origin-s1" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace",
      sourceFolders: [
        createFolder({ id: "dest-parent", name: "parent" }),
        createFolder({
          id: "dest-child",
          name: "evidence",
          parentFolderId: "dest-parent"
        })
      ]
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "copy",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.destinationSnapshot.sourceFolders.map((folder) => folder.id)).toEqual(
      ["dest-parent", "dest-child"]
    )
    expect(result.destinationSnapshot.sourceFolderMemberships).toEqual([
      { folderId: "dest-child", sourceId: "generated-source-1" }
    ])
  })

  it("reports only folders newly emptied by the move", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Selected" }),
        createSource({ id: "origin-s2", mediaId: 202, title: "Retained" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-empty", name: "Empty" }),
        createFolder({ id: "origin-stays-full", name: "Full" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-empty", sourceId: "origin-s1" }),
        createMembership({ folderId: "origin-stays-full", sourceId: "origin-s2" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace"
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "move",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "keep",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.newlyEmptiedOriginFolderIds).toEqual(["origin-empty"])
    expect(result.newlyEmptiedOriginFolderIds).not.toContain("origin-stays-full")
  })

  it("deletes emptied origin folders while leaving non-empty ancestors in place", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 101, title: "Moved" }),
        createSource({ id: "origin-s2", mediaId: 202, title: "Retained" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-parent", name: "Parent" }),
        createFolder({
          id: "origin-child-moved",
          name: "Moved Folder",
          parentFolderId: "origin-parent"
        }),
        createFolder({
          id: "origin-child-retained",
          name: "Retained Folder",
          parentFolderId: "origin-parent"
        })
      ],
      sourceFolderMemberships: [
        createMembership({
          folderId: "origin-child-moved",
          sourceId: "origin-s1"
        }),
        createMembership({
          folderId: "origin-child-retained",
          sourceId: "origin-s2"
        })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace"
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "move",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "delete-empty-folders",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.originSnapshot.sourceFolders.map((folder) => folder.id)).toEqual([
      "origin-parent",
      "origin-child-retained"
    ])
    expect(result.originSnapshot.sourceFolders[0]?.parentFolderId).toBeNull()
    expect(result.originSnapshot.sourceFolders[1]?.parentFolderId).toBe(
      "origin-parent"
    )
    expect(result.originSnapshot.sourceFolderMemberships).toEqual([
      { folderId: "origin-child-retained", sourceId: "origin-s2" }
    ])
    expect(result.newlyEmptiedOriginFolderIds).toEqual(["origin-child-moved"])
  })

  it("does not delete newly emptied folders that still contain surviving child folders", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sources: [
        createSource({ id: "origin-s1", mediaId: 301, title: "Moved Parent Source" }),
        createSource({ id: "origin-s2", mediaId: 302, title: "Retained Child Source" })
      ],
      sourceFolders: [
        createFolder({ id: "origin-parent", name: "Parent" }),
        createFolder({
          id: "origin-child",
          name: "Child",
          parentFolderId: "origin-parent"
        })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "origin-parent", sourceId: "origin-s1" }),
        createMembership({ folderId: "origin-child", sourceId: "origin-s2" })
      ]
    })
    const destinationSnapshot = createSnapshot({
      workspaceId: "destination-workspace"
    })

    const result = applyWorkspaceSourceTransfer({
      mode: "move",
      originSnapshot,
      destinationSnapshot,
      selectedSourceIds: ["origin-s1"],
      conflictResolutions: {},
      emptyFolderPolicy: "delete-empty-folders",
      sourceFolderFallbackName,
      generateId: createIdFactory()
    })

    expect(result.originSnapshot.sourceFolders).toEqual([
      expect.objectContaining({ id: "origin-parent", parentFolderId: null }),
      expect.objectContaining({
        id: "origin-child",
        parentFolderId: "origin-parent"
      })
    ])
    expect(result.originSnapshot.sourceFolderMemberships).toEqual([
      { folderId: "origin-child", sourceId: "origin-s2" }
    ])
  })

  it("renames reparented child folders to avoid collisions with later siblings", () => {
    const originSnapshot = createSnapshot({
      workspaceId: "origin-workspace",
      sourceFolders: [
        createFolder({ id: "folder-parent", name: "Parent" }),
        createFolder({
          id: "folder-child-docs",
          name: "Docs",
          parentFolderId: "folder-parent"
        }),
        createFolder({ id: "folder-root-docs", name: "Docs" })
      ]
    })

    deleteSourceFolderForTest(originSnapshot, "folder-parent")

    expect(originSnapshot.sourceFolders).toEqual([
      expect.objectContaining({
        id: "folder-child-docs",
        parentFolderId: null,
        name: "Docs (2)"
      }),
      expect.objectContaining({
        id: "folder-root-docs",
        parentFolderId: null,
        name: "Docs"
      })
    ])
  })
})
