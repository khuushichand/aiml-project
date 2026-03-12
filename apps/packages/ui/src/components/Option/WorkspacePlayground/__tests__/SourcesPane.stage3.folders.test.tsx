import { fireEvent, render, screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SourcesPane } from "../SourcesPane"

const mockToggleSourceSelection = vi.fn()
const mockSelectAllSources = vi.fn()
const mockDeselectAllSources = vi.fn()
const mockSetSourceSearchQuery = vi.fn()
const mockClearSourceFocusTarget = vi.fn()
const mockOpenAddSourceModal = vi.fn()
const mockAddSource = vi.fn()
const mockRemoveSource = vi.fn()
const mockRemoveSources = vi.fn()
const mockRestoreSource = vi.fn()
const mockReorderSource = vi.fn()
const mockSetActiveFolder = vi.fn()
const mockToggleSourceFolderSelection = vi.fn()
const mockAssignSourceToFolders = vi.fn()
const mockGetEffectiveSelectedSources = vi.fn()
const mockGetEffectiveSelectedMediaIds = vi.fn()

const workspaceStoreState = {
  sources: [
    {
      id: "s1",
      mediaId: 101,
      title: "Source One",
      type: "pdf" as const,
      status: "ready" as const,
      addedAt: new Date("2026-03-11T00:00:00.000Z")
    },
    {
      id: "s2",
      mediaId: 102,
      title: "Source Two",
      type: "pdf" as const,
      status: "ready" as const,
      addedAt: new Date("2026-03-11T00:00:00.000Z")
    }
  ],
  selectedSourceIds: ["s1"],
  selectedSourceFolderIds: ["folder-evidence"],
  sourceFolders: [
    {
      id: "folder-evidence",
      workspaceId: "workspace-1",
      name: "Evidence",
      parentFolderId: null,
      createdAt: new Date("2026-03-11T00:00:00.000Z"),
      updatedAt: new Date("2026-03-11T00:00:00.000Z")
    },
    {
      id: "folder-quotes",
      workspaceId: "workspace-1",
      name: "Quotes",
      parentFolderId: "folder-evidence",
      createdAt: new Date("2026-03-11T00:00:00.000Z"),
      updatedAt: new Date("2026-03-11T00:00:00.000Z")
    }
  ],
  sourceFolderMemberships: [
    { folderId: "folder-evidence", sourceId: "s1" },
    { folderId: "folder-quotes", sourceId: "s2" }
  ],
  activeFolderId: null as string | null,
  sourceSearchQuery: "",
  sourceFocusTarget: null as { sourceId: string; token: number } | null,
  toggleSourceSelection: mockToggleSourceSelection,
  selectAllSources: mockSelectAllSources,
  deselectAllSources: mockDeselectAllSources,
  setSourceSearchQuery: mockSetSourceSearchQuery,
  clearSourceFocusTarget: mockClearSourceFocusTarget,
  openAddSourceModal: mockOpenAddSourceModal,
  addSource: mockAddSource,
  removeSource: mockRemoveSource,
  removeSources: mockRemoveSources,
  restoreSource: mockRestoreSource,
  reorderSource: mockReorderSource,
  setActiveFolder: mockSetActiveFolder,
  toggleSourceFolderSelection: mockToggleSourceFolderSelection,
  assignSourceToFolders: mockAssignSourceToFolders,
  getEffectiveSelectedSources: mockGetEffectiveSelectedSources,
  getEffectiveSelectedMediaIds: mockGetEffectiveSelectedMediaIds
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return _key
    }
  })
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof workspaceStoreState) => unknown
  ) => selector(workspaceStoreState)
}))

vi.mock("../SourcesPane/AddSourceModal", () => ({
  AddSourceModal: () => <div data-testid="add-source-modal" />
}))

describe("SourcesPane Stage 3 source folders", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workspaceStoreState.activeFolderId = null
    mockGetEffectiveSelectedSources.mockReturnValue([
      workspaceStoreState.sources[0],
      workspaceStoreState.sources[1]
    ])
    mockGetEffectiveSelectedMediaIds.mockReturnValue([101, 102])
  })

  it("renders nested folders with separate focus and selection controls", () => {
    render(<SourcesPane />)

    expect(screen.getByText("Evidence")).toBeInTheDocument()
    expect(screen.getByText("Quotes")).toBeInTheDocument()

    fireEvent.click(
      screen.getByRole("button", { name: "Focus folder Evidence" })
    )
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select folder Evidence" })
    )

    expect(mockSetActiveFolder).toHaveBeenCalledWith("folder-evidence")
    expect(mockToggleSourceFolderSelection).toHaveBeenCalledWith(
      "folder-evidence"
    )
  })

  it("shows direct and inherited selection states separately on source rows", () => {
    render(<SourcesPane />)

    expect(screen.getByText("Direct + folder")).toBeInTheDocument()
    expect(screen.getByText("From folder")).toBeInTheDocument()
  })

  it("adds a source to multiple folders from the membership menu", () => {
    render(<SourcesPane />)

    fireEvent.click(
      screen.getByRole("button", { name: "Add Source One to folders" })
    )

    const menu = screen.getByRole("menu", { name: "Folders for Source One" })
    fireEvent.click(within(menu).getByRole("checkbox", { name: "Folder Quotes" }))

    expect(mockAssignSourceToFolders).toHaveBeenCalledWith("s1", [
      "folder-evidence",
      "folder-quotes"
    ])
  })
})
