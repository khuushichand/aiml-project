import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { WorkspaceHeader } from "../WorkspaceHeader"

const mockNavigate = vi.fn()
const mockSwitchWorkspace = vi.fn()
const mockCreateNewWorkspace = vi.fn()
const mockExportWorkspaceBundle = vi.fn()
const mockImportWorkspaceBundle = vi.fn()
const mockDuplicateWorkspace = vi.fn()
const mockArchiveWorkspace = vi.fn()
const mockRestoreArchivedWorkspace = vi.fn()
const mockDeleteWorkspace = vi.fn()
const mockSaveCurrentWorkspace = vi.fn()
const mockSetWorkspaceName = vi.fn()
const mockSetCurrentNote = vi.fn()
const mockCreateWorkspaceExportZipBlob = vi.fn()
const mockCreateWorkspaceExportZipFilename = vi.fn()
const mockParseWorkspaceImportFile = vi.fn()

const now = new Date("2026-02-18T12:00:00.000Z")

const mockStoreState = {
  workspaceName: "Alpha Research",
  workspaceId: "workspace-alpha",
  workspaceTag: "workspace:alpha-research",
  sources: [
    {
      id: "source-1",
      mediaId: 101,
      title: "Alpha Whitepaper",
      type: "pdf",
      addedAt: new Date("2026-02-17T11:00:00.000Z"),
      url: "https://example.com/alpha-whitepaper"
    }
  ],
  setWorkspaceName: mockSetWorkspaceName,
  setCurrentNote: mockSetCurrentNote,
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
  exportWorkspaceBundle: mockExportWorkspaceBundle,
  importWorkspaceBundle: mockImportWorkspaceBundle,
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

vi.mock("@/store/workspace-bundle", async () => {
  const actual = await vi.importActual<typeof import("@/store/workspace-bundle")>(
    "@/store/workspace-bundle"
  )
  return {
    ...actual,
    createWorkspaceExportZipBlob: (...args: unknown[]) =>
      mockCreateWorkspaceExportZipBlob(...args),
    createWorkspaceExportZipFilename: (...args: unknown[]) =>
      mockCreateWorkspaceExportZipFilename(...args),
    parseWorkspaceImportFile: (...args: unknown[]) =>
      mockParseWorkspaceImportFile(...args)
  }
})

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
    mockExportWorkspaceBundle.mockReturnValue({
      format: "tldw.workspace-playground.bundle",
      schemaVersion: 1,
      exportedAt: "2026-02-18T12:00:00.000Z",
      workspace: {
        name: "Alpha Research",
        tag: "workspace:alpha-research",
        createdAt: "2026-02-10T10:00:00.000Z",
        snapshot: {
          workspaceName: "Alpha Research",
          workspaceTag: "workspace:alpha-research",
          workspaceCreatedAt: "2026-02-10T10:00:00.000Z",
          sources: [],
          selectedSourceIds: [],
          generatedArtifacts: [],
          notes: "",
          currentNote: {
            title: "",
            content: "",
            keywords: [],
            isDirty: false
          },
          leftPaneCollapsed: false,
          rightPaneCollapsed: false,
          audioSettings: {
            provider: "tldw",
            model: "kokoro",
            voice: "af_heart",
            speed: 1,
            format: "mp3"
          }
        }
      }
    })
    mockImportWorkspaceBundle.mockReturnValue("workspace-imported")
    mockCreateWorkspaceExportZipBlob.mockResolvedValue(
      new Blob(["zip-bytes"], { type: "application/zip" })
    )
    mockCreateWorkspaceExportZipFilename.mockReturnValue("alpha.workspace.zip")
    mockParseWorkspaceImportFile.mockResolvedValue({
      format: "tldw.workspace-playground.bundle",
      schemaVersion: 1,
      exportedAt: "2026-02-18T12:00:00.000Z",
      workspace: {
        name: "Imported",
        tag: "workspace:imported",
        createdAt: "2026-02-18T10:00:00.000Z",
        snapshot: {
          workspaceName: "Imported",
          workspaceTag: "workspace:imported",
          workspaceCreatedAt: "2026-02-18T10:00:00.000Z",
          sources: [],
          selectedSourceIds: [],
          generatedArtifacts: [],
          notes: "",
          currentNote: {
            title: "",
            content: "",
            keywords: [],
            isDirty: false
          },
          leftPaneCollapsed: false,
          rightPaneCollapsed: false,
          audioSettings: {
            provider: "tldw",
            model: "kokoro",
            voice: "af_heart",
            speed: 1,
            format: "mp3"
          }
        }
      }
    })
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

  it("exports workspace bundle from the workspace menu", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Export Workspace"))

    await waitFor(() => {
      expect(mockExportWorkspaceBundle).toHaveBeenCalledWith("workspace-alpha")
      expect(mockCreateWorkspaceExportZipBlob).toHaveBeenCalledTimes(1)
      expect(mockCreateWorkspaceExportZipFilename).toHaveBeenCalledTimes(1)
    })
  })

  it("falls back to JSON export when ZIP creation fails", async () => {
    mockCreateWorkspaceExportZipBlob.mockRejectedValueOnce(
      new Error("zip unavailable")
    )
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:workspace-export")
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined)

    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Export Workspace"))

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalled()
    })

    const exportedBlob = createObjectUrlSpy.mock.calls[0]?.[0] as Blob
    expect(exportedBlob.type).toContain("application/json")
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:workspace-export")
  })

  it("exports workspace citations in BibTeX format", async () => {
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:workspace-bibtex")
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined)

    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Export Citations (BibTeX)"))

    expect(createObjectUrlSpy).toHaveBeenCalledTimes(1)
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:workspace-bibtex")
  })

  it("creates a workspace from a template and seeds starter note content", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Literature Review"))

    expect(mockCreateNewWorkspace).toHaveBeenCalledWith(
      "Literature Review Workspace"
    )
    expect(mockSetCurrentNote).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Literature Review Plan",
        keywords: expect.arrayContaining(["literature", "evidence"])
      })
    )
  })

  it("imports workspace bundle file from the workspace menu", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    const input = screen.getByTestId("workspace-import-input")
    const file = new File(["{}"], "workspace.json", {
      type: "application/json"
    })

    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(mockParseWorkspaceImportFile).toHaveBeenCalledWith(file)
      expect(mockImportWorkspaceBundle).toHaveBeenCalledTimes(1)
    })
  })

  it("accepts ZIP workspace imports via the hidden file input", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    const input = screen.getByTestId("workspace-import-input")
    expect(input).toHaveAttribute(
      "accept",
      ".json,.workspace.json,.zip,.workspace.zip"
    )

    const zipFile = new File(["zip"], "workspace.workspace.zip", {
      type: "application/zip"
    })
    fireEvent.change(input, { target: { files: [zipFile] } })

    await waitFor(() => {
      expect(mockParseWorkspaceImportFile).toHaveBeenCalledWith(zipFile)
      expect(mockImportWorkspaceBundle).toHaveBeenCalled()
    })
  })
})
