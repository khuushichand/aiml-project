import { describe, expect, it } from "vitest"
import type { SavedWorkspace, WorkspaceSource } from "@/types/workspace"
import {
  WORKSPACE_TEMPLATE_PRESETS,
  buildWorkspaceBibtex,
  createWorkspaceBibtexFilename,
  filterSavedWorkspaces,
  formatWorkspaceLastAccessed
} from "../workspace-header.utils"

const baseNow = new Date("2026-02-18T12:00:00.000Z")

const createWorkspace = (
  overrides: Partial<SavedWorkspace>
): SavedWorkspace => ({
  id: overrides.id || "workspace-1",
  name: overrides.name || "Workspace",
  tag: overrides.tag || "workspace:workspace",
  createdAt: overrides.createdAt || new Date("2026-02-01T00:00:00.000Z"),
  lastAccessedAt:
    overrides.lastAccessedAt || new Date("2026-02-18T11:59:30.000Z"),
  sourceCount: overrides.sourceCount ?? 0
})

describe("workspace header utils", () => {
  it("formats relative last accessed time for recent ranges", () => {
    expect(
      formatWorkspaceLastAccessed(
        new Date("2026-02-18T11:59:40.000Z"),
        baseNow
      )
    ).toBe("just now")

    expect(
      formatWorkspaceLastAccessed(
        new Date("2026-02-18T11:30:00.000Z"),
        baseNow
      )
    ).toBe("30m ago")

    expect(
      formatWorkspaceLastAccessed(
        new Date("2026-02-18T09:00:00.000Z"),
        baseNow
      )
    ).toBe("3h ago")

    expect(
      formatWorkspaceLastAccessed(
        new Date("2026-02-16T12:00:00.000Z"),
        baseNow
      )
    ).toBe("2d ago")
  })

  it("formats older last accessed time as date", () => {
    const oldDate = new Date(2026, 0, 15, 12, 0, 0)
    const value = formatWorkspaceLastAccessed(oldDate, baseNow)
    const expected = new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric"
    }).format(oldDate)
    expect(value).toBe(expected)
  })

  it("filters workspaces by name and tag", () => {
    const workspaces: SavedWorkspace[] = [
      createWorkspace({
        id: "alpha",
        name: "Alpha Research",
        tag: "workspace:alpha-research"
      }),
      createWorkspace({
        id: "beta",
        name: "Beta Notes",
        tag: "workspace:beta-notes"
      }),
      createWorkspace({
        id: "gamma",
        name: "Gamma Review",
        tag: "workspace:gamma-review"
      })
    ]

    expect(filterSavedWorkspaces(workspaces, "")).toHaveLength(3)
    expect(filterSavedWorkspaces(workspaces, "beta")).toHaveLength(1)
    expect(filterSavedWorkspaces(workspaces, "workspace:gamma")).toHaveLength(1)
    expect(filterSavedWorkspaces(workspaces, "missing")).toHaveLength(0)
  })

  it("ships at least three workspace templates", () => {
    expect(WORKSPACE_TEMPLATE_PRESETS.length).toBeGreaterThanOrEqual(3)
    expect(WORKSPACE_TEMPLATE_PRESETS.map((template) => template.id)).toEqual(
      expect.arrayContaining([
        "literature_review",
        "interview_analysis",
        "product_brief"
      ])
    )
  })

  it("builds BibTeX entries from workspace sources", () => {
    const sources: WorkspaceSource[] = [
      {
        id: "source-1",
        mediaId: 101,
        title: "Climate Report 2026",
        type: "pdf",
        addedAt: new Date("2026-02-18T10:00:00.000Z"),
        url: "https://example.com/climate-report"
      },
      {
        id: "source-2",
        mediaId: 202,
        title: "Interview Notes",
        type: "document",
        addedAt: new Date("2026-02-17T12:00:00.000Z")
      }
    ]

    const bibtex = buildWorkspaceBibtex(sources, {
      workspaceTag: "workspace:climate-research",
      now: new Date("2026-02-18T12:00:00.000Z")
    })

    expect(bibtex).toContain("@misc{workspaceclimateresearch202601")
    expect(bibtex).toContain("title = {Climate Report 2026}")
    expect(bibtex).toContain("url = {https://example.com/climate-report}")
    expect(bibtex).toContain("urldate = {2026-02-18}")
    expect(bibtex).toContain("note = {media_id=202; type=document}")
  })

  it("builds a deterministic BibTeX filename", () => {
    expect(
      createWorkspaceBibtexFilename(
        "Alpha Research",
        new Date("2026-02-18T12:00:00.000Z")
      )
    ).toBe("alpha-research-citations-20260218.bib")
  })
})
