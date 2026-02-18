import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import {
  WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS,
  WORKSPACE_STORAGE_KEY,
  WORKSPACE_STORAGE_QUOTA_EVENT
} from "@/store/workspace-events"
import { WorkspacePlayground } from "../index"

const { mockGetMediaDetails, useWorkspaceStoreMock } = vi.hoisted(() => ({
  mockGetMediaDetails: vi.fn(),
  useWorkspaceStoreMock: vi.fn()
}))

const testState = {
  isMobile: false,
  storeHydrated: true,
  leftPaneCollapsed: false,
  rightPaneCollapsed: false,
  workspaceId: "workspace-1",
  initializeWorkspace: vi.fn(),
  addSources: vi.fn(),
  setSelectedSourceIds: vi.fn(),
  captureToCurrentNote: vi.fn(),
  selectedSourceIds: [] as string[],
  generatedArtifacts: [] as Array<{ id: string }>,
  setLeftPaneCollapsed: vi.fn(),
  setRightPaneCollapsed: vi.fn(),
  focusSourceById: vi.fn(() => true),
  focusChatMessageById: vi.fn(() => true),
  focusWorkspaceNote: vi.fn(),
  setSourceStatusByMediaId: vi.fn(),
  sources: [] as Array<{
    id: string
    mediaId: number
    title: string
    type: "pdf" | "video" | "audio" | "website" | "document" | "text"
    addedAt: Date
    status?: "processing" | "ready" | "error"
    url?: string
  }>,
  workspaceChatSessions: {} as Record<string, { messages: any[] }>,
  currentNote: {
    id: 9,
    title: "",
    content: "",
    keywords: [] as string[],
    isDirty: false
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

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => testState.isMobile
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: useWorkspaceStoreMock
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getMediaDetails: mockGetMediaDetails
  }
}))

vi.mock("@/utils/workspace-playground-prefill", () => ({
  consumeWorkspacePlaygroundPrefill: vi.fn().mockResolvedValue(null),
  buildKnowledgeQaSeedNote: vi.fn().mockReturnValue("")
}))

vi.mock("../WorkspaceHeader", () => ({
  WorkspaceHeader: () => <div data-testid="workspace-header" />
}))

vi.mock("../SourcesPane", () => ({
  SourcesPane: () => <div data-testid="workspace-sources-pane">Sources</div>
}))

vi.mock("../ChatPane", () => ({
  ChatPane: () => <div data-testid="workspace-chat-pane">Chat</div>
}))

vi.mock("../StudioPane", () => ({
  StudioPane: () => <div data-testid="workspace-studio-pane">Studio</div>
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("WorkspacePlayground stage 9 persistence resilience", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("min-width: 1024px"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn()
      }))
    })
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    useWorkspaceStoreMock.mockImplementation(
      (selector: (state: typeof testState) => unknown) => selector(testState)
    )
    testState.storeHydrated = true
    testState.workspaceId = "workspace-1"
    testState.sources = []
    testState.selectedSourceIds = []
    testState.workspaceChatSessions = {}
    testState.currentNote = {
      id: 9,
      title: "",
      content: "",
      keywords: [],
      isDirty: false
    }
    mockGetMediaDetails.mockResolvedValue({})
  })

  const dispatchWorkspaceStorageUpdate = (
    oldValue = '{"version":1}',
    newValue = '{"version":2}'
  ) => {
    const event = new Event("storage") as StorageEvent
    Object.defineProperties(event, {
      key: { value: WORKSPACE_STORAGE_KEY },
      oldValue: { value: oldValue },
      newValue: { value: newValue },
      storageArea: { value: window.localStorage }
    })
    window.dispatchEvent(event)
  }

  it("shows a cross-tab sync banner and reload action on storage updates", async () => {
    render(<WorkspacePlayground />)

    dispatchWorkspaceStorageUpdate()

    expect(
      await screen.findByTestId("workspace-storage-sync-banner")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument()
  })

  it("throttles repeated storage conflict prompts", async () => {
    let now = 1708257600000
    const nowSpy = vi.spyOn(Date, "now").mockImplementation(() => now)

    render(<WorkspacePlayground />)
    dispatchWorkspaceStorageUpdate('{"version":0}', '{"version":1}')
    expect(
      await screen.findByTestId("workspace-storage-sync-banner")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Later" }))
    expect(
      screen.queryByTestId("workspace-storage-sync-banner")
    ).not.toBeInTheDocument()

    dispatchWorkspaceStorageUpdate('{"version":1}', '{"version":2}')
    expect(
      screen.queryByTestId("workspace-storage-sync-banner")
    ).not.toBeInTheDocument()

    now += WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS + 1000
    dispatchWorkspaceStorageUpdate('{"version":2}', '{"version":3}')
    expect(
      await screen.findByTestId("workspace-storage-sync-banner")
    ).toBeInTheDocument()

    nowSpy.mockRestore()
  })

  it("shows storage quota warning from persistence quota event", async () => {
    render(<WorkspacePlayground />)

    window.dispatchEvent(
      new CustomEvent(WORKSPACE_STORAGE_QUOTA_EVENT, {
        detail: {
          key: WORKSPACE_STORAGE_KEY,
          reason: "Quota exceeded"
        }
      })
    )

    expect(
      await screen.findByTestId("workspace-storage-quota-banner")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
    await waitFor(() => {
      expect(
        screen.queryByTestId("workspace-storage-quota-banner")
      ).not.toBeInTheDocument()
    })
  })
})
