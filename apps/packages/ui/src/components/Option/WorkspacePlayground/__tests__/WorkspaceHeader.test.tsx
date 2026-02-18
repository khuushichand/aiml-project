import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { WorkspaceHeader } from "../WorkspaceHeader"

const mockNavigate = vi.fn()
const mockSwitchWorkspace = vi.fn()
const mockCreateNewWorkspace = vi.fn()
const mockDuplicateWorkspace = vi.fn()
const mockArchiveWorkspace = vi.fn()
const mockRestoreArchivedWorkspace = vi.fn()
const mockDeleteWorkspace = vi.fn()
const mockSaveCurrentWorkspace = vi.fn()
const mockSetWorkspaceName = vi.fn()

const now = new Date("2026-02-18T12:00:00.000Z")

const mockStoreState = {
  workspaceName: "Alpha Research",
  workspaceId: "workspace-alpha",
  setWorkspaceName: mockSetWorkspaceName,
  savedWorkspaces: [
    {
      id: "workspace-alpha",
      name: "Alpha Research",
      tag: "workspace:alpha-research",
      createdAt: new Date("2026-02-10T10:00:00.000Z"),
      lastAccessedAt: now,
      sourceCount: 3
    },
    {
      id: "workspace-beta",
      name: "Beta Deep Dive",
      tag: "workspace:beta-deep-dive",
      createdAt: new Date("2026-02-09T10:00:00.000Z"),
      lastAccessedAt: new Date("2026-02-18T11:00:00.000Z"),
      sourceCount: 5
    },
    {
      id: "workspace-gamma",
      name: "Gamma Notes",
      tag: "workspace:gamma-notes",
      createdAt: new Date("2026-02-08T10:00:00.000Z"),
      lastAccessedAt: new Date("2026-02-18T09:00:00.000Z"),
      sourceCount: 2
    }
  ],
  archivedWorkspaces: [],
  createNewWorkspace: mockCreateNewWorkspace,
  switchWorkspace: mockSwitchWorkspace,
  duplicateWorkspace: mockDuplicateWorkspace,
  archiveWorkspace: mockArchiveWorkspace,
  restoreArchivedWorkspace: mockRestoreArchivedWorkspace,
  deleteWorkspace: mockDeleteWorkspace,
  saveCurrentWorkspace: mockSaveCurrentWorkspace
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof mockStoreState) => unknown
  ) => selector(mockStoreState)
}))

if (!(globalThis as unknown as { ResizeObserver?: unknown }).ResizeObserver) {
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("WorkspaceHeader workspace browser modal", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("opens view-all modal and filters workspaces by search query", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("View all workspaces"))

    const modal = await screen.findByRole("dialog", {
      name: "All Workspaces"
    })
    expect(modal).toBeInTheDocument()
    expect(within(modal).getByText("Beta Deep Dive")).toBeInTheDocument()
    expect(within(modal).getByText("Gamma Notes")).toBeInTheDocument()

    const searchInput = within(modal).getByPlaceholderText(
      "Search workspaces by name or tag"
    )
    fireEvent.change(searchInput, { target: { value: "gamma" } })

    await waitFor(() => {
      expect(within(modal).queryByText("Beta Deep Dive")).not.toBeInTheDocument()
      expect(within(modal).getByText("Gamma Notes")).toBeInTheDocument()
    })
  })

  it("switches workspace when selecting from view-all modal", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("View all workspaces"))

    const modal = await screen.findByRole("dialog", {
      name: "All Workspaces"
    })
    const targetWorkspaceRow = await within(modal).findByRole("button", {
      name: /Beta Deep Dive/
    })
    fireEvent.click(targetWorkspaceRow)

    expect(mockSwitchWorkspace).toHaveBeenCalledWith("workspace-beta")
  })
})
