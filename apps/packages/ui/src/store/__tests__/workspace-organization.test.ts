import { describe, expect, it } from "vitest"
import type {
  WorkspaceSource,
  WorkspaceSourceFolder,
  WorkspaceSourceFolderMembership
} from "@/types/workspace"
import {
  collectDescendantFolderIds,
  createWorkspaceOrganizationIndex,
  deriveEffectiveSelectedSourceIds,
  getFolderSelectionState,
  getSourceSelectionOrigin
} from "../workspace-organization"

const now = new Date("2026-03-11T12:00:00.000Z")

const createSource = (
  overrides: Partial<WorkspaceSource> & Pick<WorkspaceSource, "id" | "mediaId" | "title">
): WorkspaceSource => ({
  id: overrides.id,
  mediaId: overrides.mediaId,
  title: overrides.title,
  type: overrides.type || "pdf",
  status: overrides.status || "ready",
  addedAt: overrides.addedAt || now
})

const createFolder = (
  overrides: Partial<WorkspaceSourceFolder> & Pick<WorkspaceSourceFolder, "id" | "name">
): WorkspaceSourceFolder => ({
  id: overrides.id,
  workspaceId: overrides.workspaceId || "workspace-1",
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

describe("workspace organization selectors", () => {
  it("includes descendant folders recursively and deduplicates ready sources", () => {
    const index = createWorkspaceOrganizationIndex({
      sourceFolders: [
        createFolder({ id: "root", name: "Root" }),
        createFolder({ id: "child", name: "Child", parentFolderId: "root" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "root", sourceId: "s1" }),
        createMembership({ folderId: "child", sourceId: "s2" }),
        createMembership({ folderId: "child", sourceId: "s1" })
      ],
      sources: [
        createSource({ id: "s1", mediaId: 1, title: "One" }),
        createSource({ id: "s2", mediaId: 2, title: "Two" })
      ]
    })

    expect(collectDescendantFolderIds(index, "root")).toEqual(["root", "child"])
    expect(deriveEffectiveSelectedSourceIds(index, ["s2"], ["root"])).toEqual([
      "s1",
      "s2"
    ])
    expect(getFolderSelectionState(index, "root", ["s2"], [])).toBe(
      "indeterminate"
    )
    expect(getSourceSelectionOrigin("s1", ["s1"], ["root"], index)).toBe("both")
  })

  it("ignores unknown folders, processing sources, and duplicate memberships", () => {
    const index = createWorkspaceOrganizationIndex({
      sourceFolders: [
        createFolder({ id: "root", name: "Root" }),
        createFolder({ id: "child", name: "Child", parentFolderId: "root" }),
        createFolder({ id: "empty", name: "Empty" })
      ],
      sourceFolderMemberships: [
        createMembership({ folderId: "child", sourceId: "s1" }),
        createMembership({ folderId: "child", sourceId: "s1" }),
        createMembership({ folderId: "child", sourceId: "missing-source" }),
        createMembership({ folderId: "missing-folder", sourceId: "s1" }),
        createMembership({ folderId: "root", sourceId: "s2" })
      ],
      sources: [
        createSource({ id: "s1", mediaId: 1, title: "Ready Source" }),
        createSource({
          id: "s2",
          mediaId: 2,
          title: "Processing Source",
          status: "processing"
        })
      ]
    })

    expect(collectDescendantFolderIds(index, "missing-folder")).toEqual([])
    expect(deriveEffectiveSelectedSourceIds(index, [], ["root"])).toEqual(["s1"])
    expect(getFolderSelectionState(index, "empty", [], [])).toBe("unchecked")
    expect(getSourceSelectionOrigin("s2", ["s2"], ["root"], index)).toBe("none")
  })
})
