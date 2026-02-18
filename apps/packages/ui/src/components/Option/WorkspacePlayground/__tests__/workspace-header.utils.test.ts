import { describe, expect, it } from "vitest"
import type { SavedWorkspace } from "@/types/workspace"
import {
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
})
