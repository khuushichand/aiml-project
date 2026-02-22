import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { Modal } from "antd"
import {
  clearWorkspaceUndoActionsForTests,
  getWorkspaceUndoPendingCount
} from "../undo-manager"
import { WorkspaceHeader } from "../WorkspaceHeader"
import {
  FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS,
  FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY
} from "@/utils/feature-rollout"

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
const mockCaptureUndoSnapshot = vi.fn()
const mockRestoreUndoSnapshot = vi.fn()
const mockCreateWorkspaceExportZipBlob = vi.fn()
const mockCreateWorkspaceExportZipFilename = vi.fn()
const mockParseWorkspaceImportFile = vi.fn()
const mockTrackWorkspacePlaygroundTelemetry = vi.fn()
const mockGetWorkspacePlaygroundTelemetryState = vi.fn()
const mockResetWorkspacePlaygroundTelemetryState = vi.fn()

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
  saveCurrentWorkspace: mockSaveCurrentWorkspace,
  captureUndoSnapshot: mockCaptureUndoSnapshot,
  restoreUndoSnapshot: mockRestoreUndoSnapshot
}

const mockConnectionStoreState = {
  state: {
    phase: "connected" as const,
    serverUrl: "http://127.0.0.1:8000",
    lastCheckedAt: Date.now(),
    lastError: null as string | null,
    lastStatusCode: 200 as number | null,
    isConnected: true,
    isChecking: false,
    consecutiveFailures: 0,
    offlineBypass: false,
    knowledgeStatus: "ready" as const,
    knowledgeLastCheckedAt: Date.now(),
    knowledgeError: null as string | null,
    mode: "normal" as const,
    configStep: "none" as const,
    errorKind: "none" as const,
    hasCompletedFirstRun: true,
    lastConfigUpdatedAt: Date.now(),
    checksSinceConfigChange: 0
  }
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

vi.mock("@/store/connection", () => ({
  useConnectionStore: (
    selector: (state: typeof mockConnectionStoreState) => unknown
  ) => selector(mockConnectionStoreState)
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

vi.mock("@/utils/workspace-playground-telemetry", async () => {
  const actual =
    await vi.importActual<typeof import("@/utils/workspace-playground-telemetry")>(
      "@/utils/workspace-playground-telemetry"
    )
  return {
    ...actual,
    trackWorkspacePlaygroundTelemetry: (...args: unknown[]) =>
      mockTrackWorkspacePlaygroundTelemetry(...args),
    getWorkspacePlaygroundTelemetryState: (...args: unknown[]) =>
      mockGetWorkspacePlaygroundTelemetryState(...args),
    resetWorkspacePlaygroundTelemetryState: (...args: unknown[]) =>
      mockResetWorkspacePlaygroundTelemetryState(...args)
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
    window.localStorage.clear()
    clearWorkspaceUndoActionsForTests()
    mockCaptureUndoSnapshot.mockReturnValue({
      workspaceId: "workspace-alpha",
      workspaceName: "Alpha Research"
    })
    mockConnectionStoreState.state = {
      ...mockConnectionStoreState.state,
      phase: "connected",
      isConnected: true,
      isChecking: false,
      errorKind: "none",
      knowledgeStatus: "ready",
      lastError: null,
      knowledgeError: null
    }
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
    mockGetWorkspacePlaygroundTelemetryState.mockResolvedValue({
      version: 1,
      counters: {
        status_viewed: 3,
        citation_provenance_opened: 1,
        token_cost_rendered: 2,
        diagnostics_toggled: 1,
        quota_warning_seen: 0,
        conflict_modal_opened: 1,
        undo_triggered: 2,
        operation_cancelled: 1,
        artifact_rehydrated_failed: 0,
        source_status_polled: 5,
        source_status_ready: 4,
        connectivity_state_changed: 2,
        confusion_retry_burst: 0,
        confusion_refresh_loop: 0,
        confusion_duplicate_submission: 0
      },
      last_event_at: Date.parse("2026-02-20T01:23:45.000Z"),
      recent_events: [
        {
          type: "status_viewed",
          at: Date.parse("2026-02-20T01:22:00.000Z"),
          details: { workspace_id: "workspace-alpha" }
        },
        {
          type: "operation_cancelled",
          at: Date.parse("2026-02-20T01:23:45.000Z"),
          details: { scope: "chat" }
        },
        {
          type: "confusion_retry_burst",
          at: Date.parse("2026-02-20T01:24:12.000Z"),
          details: { retry_count: 3, window_ms: 30000 }
        }
      ]
    })
    mockResetWorkspacePlaygroundTelemetryState.mockResolvedValue(undefined)
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

  it("archives current workspace with undo availability", async () => {
    const confirmSpy = vi
      .spyOn(Modal, "confirm")
      .mockImplementation((config) => {
        config.onOk?.()
        return {
          destroy: vi.fn(),
          update: vi.fn()
        } as any
      })

    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Archive Current Workspace"))

    expect(confirmSpy).toHaveBeenCalled()
    expect(mockArchiveWorkspace).toHaveBeenCalledWith("workspace-alpha")
    expect(getWorkspaceUndoPendingCount()).toBeGreaterThan(0)
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

  it("opens keyboard shortcuts cheat sheet from workspace menu", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Keyboard Shortcuts"))

    const shortcutsModal = await screen.findByRole("dialog", {
      name: "Keyboard Shortcuts"
    })
    expect(shortcutsModal).toBeInTheDocument()
    expect(within(shortcutsModal).getByText("Search workspace")).toBeInTheDocument()
    expect(within(shortcutsModal).getByText("Focus sources")).toBeInTheDocument()
    expect(within(shortcutsModal).getByText("Focus chat")).toBeInTheDocument()
    expect(within(shortcutsModal).getByText("Focus studio")).toBeInTheDocument()
  })

  it("opens telemetry summary modal from workspace menu", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Telemetry summary"))

    const telemetryModal = await screen.findByRole("dialog", {
      name: "Telemetry summary"
    })
    expect(telemetryModal).toBeInTheDocument()
    expect(mockGetWorkspacePlaygroundTelemetryState).toHaveBeenCalledTimes(1)
    expect(
      within(telemetryModal).getByTestId(
        "workspace-telemetry-counter-status_viewed"
      )
    ).toHaveTextContent("3")
    expect(
      within(telemetryModal).getByTestId(
        "workspace-telemetry-counter-connectivity_state_changed"
      )
    ).toHaveTextContent("2")
  })

  it("resets telemetry summary state from the telemetry modal", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Telemetry summary"))

    const telemetryModal = await screen.findByRole("dialog", {
      name: "Telemetry summary"
    })
    fireEvent.click(within(telemetryModal).getByRole("button", { name: "Reset" }))

    await waitFor(() => {
      expect(mockResetWorkspacePlaygroundTelemetryState).toHaveBeenCalledTimes(1)
      expect(mockGetWorkspacePlaygroundTelemetryState).toHaveBeenCalledTimes(2)
    })
  })

  it("exports telemetry summary and confusion CSV from telemetry modal", async () => {
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:workspace-telemetry")
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
    fireEvent.click(await screen.findByText("Telemetry summary"))

    const telemetryModal = await screen.findByRole("dialog", {
      name: "Telemetry summary"
    })
    fireEvent.click(
      within(telemetryModal).getByRole("button", { name: "Export JSON" })
    )
    fireEvent.click(
      within(telemetryModal).getByRole("button", {
        name: "Export confusion CSV"
      })
    )

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalledTimes(2)
    })

    const firstBlob = createObjectUrlSpy.mock.calls[0]?.[0] as Blob
    const secondBlob = createObjectUrlSpy.mock.calls[1]?.[0] as Blob
    expect(firstBlob.type).toContain("application/json")
    expect(secondBlob.type).toContain("text/csv")
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:workspace-telemetry")
  })

  it("loads rollout execution controls from localStorage in telemetry modal", async () => {
    window.localStorage.setItem(
      FEATURE_ROLLOUT_SUBJECT_ID_STORAGE_KEY,
      "subject-ops-42"
    )
    window.localStorage.setItem(
      FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS.research_studio_provenance_v1,
      "10"
    )
    window.localStorage.setItem(
      FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS
        .research_studio_status_guardrails_v1,
      "50"
    )

    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Telemetry summary"))

    const telemetryModal = await screen.findByRole("dialog", {
      name: "Telemetry summary"
    })
    expect(
      within(telemetryModal).getByTestId("workspace-rollout-subject-id")
    ).toHaveTextContent("subject-ops-42")
    expect(
      within(telemetryModal).getByTestId(
        "workspace-rollout-percentage-research_studio_provenance_v1"
      )
    ).toHaveTextContent("10%")
    expect(
      within(telemetryModal).getByTestId(
        "workspace-rollout-percentage-research_studio_status_guardrails_v1"
      )
    ).toHaveTextContent("50%")
  })

  it("persists rollout preset updates from telemetry modal controls", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    fireEvent.click(await screen.findByText("Telemetry summary"))

    const telemetryModal = await screen.findByRole("dialog", {
      name: "Telemetry summary"
    })
    const provenanceControl = within(telemetryModal).getByTestId(
      "workspace-rollout-control-research_studio_provenance_v1"
    )
    fireEvent.click(within(provenanceControl).getByRole("button", { name: "10%" }))

    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          FEATURE_ROLLOUT_PERCENTAGE_STORAGE_KEYS.research_studio_provenance_v1
        )
      ).toBe("10")
    })
    expect(
      within(provenanceControl).getByTestId(
        "workspace-rollout-percentage-research_studio_provenance_v1"
      )
    ).toHaveTextContent("10%")
  })

  it("renders proactive storage usage indicator with formatted capacity", () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        storageUsedBytes={2.1 * 1024 * 1024}
        storageQuotaBytes={5 * 1024 * 1024}
      />
    )

    const indicator = screen.getByTestId("workspace-storage-usage-indicator")
    expect(indicator).toHaveTextContent("Storage WS 2.1/5 MB")
    expect(indicator.className).toContain("text-text-muted")
  })

  it("includes browser profile storage usage when provided", () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        storageUsedBytes={2.1 * 1024 * 1024}
        storageQuotaBytes={5 * 1024 * 1024}
        storageOriginUsedBytes={120 * 1024 * 1024}
        storageOriginQuotaBytes={1000 * 1024 * 1024}
      />
    )

    const indicator = screen.getByTestId("workspace-storage-usage-indicator")
    expect(indicator).toHaveTextContent("Storage WS 2.1/5 MB | Profile 120.0/1000 MB")
  })

  it("includes account storage usage when provided", () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        storageUsedBytes={2.1 * 1024 * 1024}
        storageQuotaBytes={5 * 1024 * 1024}
        storageAccountUsedBytes={300 * 1024 * 1024}
        storageAccountQuotaBytes={1000 * 1024 * 1024}
      />
    )

    const indicator = screen.getByTestId("workspace-storage-usage-indicator")
    expect(indicator).toHaveTextContent("Storage WS 2.1/5 MB | Account 300.0/1000 MB")
  })

  it("shows connection status indicator tone for healthy, degraded, and disconnected states", () => {
    const { rerender } = render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    expect(
      screen.getByTestId("workspace-connection-status-indicator")
    ).toHaveTextContent("Connected")
    expect(
      screen.getByTestId("workspace-connection-status-indicator").className
    ).toContain("text-success")

    mockConnectionStoreState.state = {
      ...mockConnectionStoreState.state,
      phase: "connected",
      isConnected: true,
      errorKind: "partial",
      knowledgeStatus: "offline"
    }

    rerender(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    expect(
      screen.getByTestId("workspace-connection-status-indicator")
    ).toHaveTextContent("Degraded")
    expect(
      screen.getByTestId("workspace-connection-status-indicator").className
    ).toContain("text-warning")

    mockConnectionStoreState.state = {
      ...mockConnectionStoreState.state,
      phase: "error",
      isConnected: false,
      errorKind: "unreachable",
      lastError: "Network timeout"
    }

    rerender(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
      />
    )

    expect(
      screen.getByTestId("workspace-connection-status-indicator")
    ).toHaveTextContent("Disconnected")
    expect(
      screen.getByTestId("workspace-connection-status-indicator").className
    ).toContain("text-error")
  })

  it("highlights storage usage indicator at warning and critical thresholds", () => {
    const { rerender } = render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        storageUsedBytes={4.1 * 1024 * 1024}
        storageQuotaBytes={5 * 1024 * 1024}
      />
    )

    const indicator = screen.getByTestId("workspace-storage-usage-indicator")
    expect(indicator.className).toContain("text-warning")

    rerender(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        storageUsedBytes={4.8 * 1024 * 1024}
        storageQuotaBytes={5 * 1024 * 1024}
      />
    )

    expect(screen.getByTestId("workspace-storage-usage-indicator").className).toContain(
      "text-error"
    )
  })

  it("hides status guardrail indicators and telemetry menu when rollout flags are disabled", async () => {
    render(
      <WorkspaceHeader
        leftPaneOpen={true}
        rightPaneOpen={true}
        onToggleLeftPane={vi.fn()}
        onToggleRightPane={vi.fn()}
        statusGuardrailsEnabled={false}
        provenanceEnabled={false}
      />
    )

    expect(
      screen.queryByTestId("workspace-connection-status-indicator")
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("workspace-storage-usage-indicator")
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }))
    expect(screen.queryByText("Telemetry summary")).not.toBeInTheDocument()
  })
})
