import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ConnectionPhase } from "@/types/connection"
import { ChatPane } from "../ChatPane"
import { WORKSPACE_SOURCE_DRAG_TYPE } from "../drag-source"

const mockCheckConnectionOnce = vi.fn()
const mockSaveWorkspaceChatSession = vi.fn()
const mockGetWorkspaceChatSession = vi.fn()
const mockFocusSourceById = vi.fn()
const mockFocusSourceByMediaId = vi.fn()
const mockCaptureToCurrentNote = vi.fn()
const mockSetSelectedSourceIds = vi.fn()
const mockClearChatFocusTarget = vi.fn()
const mockSetMessages = vi.fn()
const mockSetHistory = vi.fn()
const mockSetHistoryId = vi.fn()
const mockSetServerChatId = vi.fn()
const mockSetStreaming = vi.fn()
const mockSetIsProcessing = vi.fn()
const mockStopStreamingRequest = vi.fn()
const mockOnSubmit = vi.fn()
const mockRegenerateLastMessage = vi.fn()
const mockDeleteMessage = vi.fn()
const mockEditMessage = vi.fn()
const mockCreateChatBranch = vi.fn()
const mockMessageInfo = vi.fn()

const connectionStoreState = {
  state: {
    phase: ConnectionPhase.CONNECTED,
    isChecking: false,
    lastError: null
  },
  checkOnce: mockCheckConnectionOnce
}

const workspaceStoreState = {
  sources: [] as Array<{
    id: string
    mediaId: number
    title: string
    type: "pdf" | "video" | "audio" | "website" | "document" | "text"
    addedAt?: Date
    url?: string
  }>,
  selectedSourceIds: [] as string[],
  getSelectedSources: () =>
    [] as Array<{ id: string; title: string; mediaId?: number; type?: string }>,
  getSelectedMediaIds: () => [] as number[],
  setSelectedSourceIds: mockSetSelectedSourceIds,
  focusSourceById: mockFocusSourceById,
  focusSourceByMediaId: mockFocusSourceByMediaId,
  chatFocusTarget: null as { messageId: string; token: number } | null,
  clearChatFocusTarget: mockClearChatFocusTarget,
  captureToCurrentNote: mockCaptureToCurrentNote,
  workspaceId: "workspace-a",
  workspaceChatReferenceId: "workspace-a",
  saveWorkspaceChatSession: mockSaveWorkspaceChatSession,
  getWorkspaceChatSession: mockGetWorkspaceChatSession
}

const deriveSelectedSources = () =>
  workspaceStoreState.sources.filter((source) =>
    workspaceStoreState.selectedSourceIds.includes(source.id)
  )

const deriveSelectedMediaIds = () =>
  deriveSelectedSources()
    .map((source) => source.mediaId)
    .filter((mediaId): mediaId is number => Number.isFinite(mediaId))

const messageOptionState = {
  messages: [] as Array<{
    id: string
    isBot: boolean
    name: string
    message: string
    sources: any[]
    generationInfo?: any
  }>,
  setMessages: mockSetMessages,
  history: [] as Array<{ role: "user" | "assistant" | "system"; content: string }>,
  setHistory: mockSetHistory,
  streaming: false,
  setStreaming: mockSetStreaming,
  isProcessing: false,
  setIsProcessing: mockSetIsProcessing,
  onSubmit: mockOnSubmit,
  stopStreamingRequest: mockStopStreamingRequest,
  regenerateLastMessage: mockRegenerateLastMessage,
  deleteMessage: mockDeleteMessage,
  editMessage: mockEditMessage,
  createChatBranch: mockCreateChatBranch,
  historyId: null as string | null,
  setHistoryId: mockSetHistoryId,
  serverChatId: null as string | null,
  setServerChatId: mockSetServerChatId
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
  useMobile: () => false
}))

vi.mock("@/hooks/useSmartScroll", () => ({
  useSmartScroll: () => ({
    containerRef: { current: null },
    isAutoScrollToBottom: true,
    autoScrollToBottom: vi.fn()
  })
}))

vi.mock("@/store/connection", () => ({
  useConnectionStore: (
    selector: (state: typeof connectionStoreState) => unknown
  ) => selector(connectionStoreState)
}))

vi.mock("@/store/workspace", () => ({
  useWorkspaceStore: (
    selector: (state: typeof workspaceStoreState) => unknown
  ) => selector(workspaceStoreState)
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (
    selector: (state: {
      setRagMediaIds: (ids: number[] | null) => void
      setChatMode: (mode: string) => void
      setFileRetrievalEnabled: (enabled: boolean) => void
      ragTopK: number
      setRagTopK: (value: number | null) => void
      ragAdvancedOptions: Record<string, unknown>
      setRagAdvancedOptions: (opts: Record<string, unknown>) => void
    }) => unknown
  ) =>
    selector({
      setRagMediaIds: vi.fn(),
      setChatMode: vi.fn(),
      setFileRetrievalEnabled: vi.fn(),
      ragTopK: 8,
      setRagTopK: vi.fn(),
      ragAdvancedOptions: {},
      setRagAdvancedOptions: vi.fn()
    })
}))

vi.mock("@/hooks/useMessageOption", () => ({
  useMessageOption: () => messageOptionState
}))

vi.mock("@/components/Common/Playground/Message", () => ({
  PlaygroundMessage: ({
    message,
    onSourceClick,
    sources,
    onSwipePrev,
    onSwipeNext,
    onNewBranch
  }: {
    message: string
    onSourceClick?: (source: any) => void
    sources?: any[]
    onSwipePrev?: () => void
    onSwipeNext?: () => void
    onNewBranch?: () => void
  }) => (
    <div data-testid="playground-message">
      <div>{message}</div>
      {sources && sources.length > 0 && (
        <button
          type="button"
          onClick={() => onSourceClick?.(sources[0])}
          aria-label="Open citation"
        >
          Open citation
        </button>
      )}
      {onSwipePrev && (
        <button
          type="button"
          onClick={onSwipePrev}
          aria-label="Variant previous"
        >
          Variant previous
        </button>
      )}
      {onSwipeNext && (
        <button
          type="button"
          onClick={onSwipeNext}
          aria-label="Variant next"
        >
          Variant next
        </button>
      )}
      {onNewBranch && (
        <button
          type="button"
          onClick={onNewBranch}
          aria-label="Create branch"
        >
          Create branch
        </button>
      )}
    </div>
  )
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  default: ({ title }: { title: string }) => <div>{title}</div>
}))

vi.mock("../source-location-copy", () => ({
  getWorkspaceChatNoSourcesHint: () =>
    "Select sources from the Sources pane, then ask questions."
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getChatLorebookDiagnostics: vi.fn(async () => ({
      chat_id: "chat",
      total_turns_with_diagnostics: 0,
      turns: [],
      page: 1,
      size: 8
    }))
  }
}))

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd")
  return {
    ...actual,
    message: {
      useMessage: () => [
        {
          info: mockMessageInfo,
          error: vi.fn(),
          success: vi.fn(),
          warning: vi.fn(),
          open: vi.fn(),
          destroy: vi.fn()
        },
        <></>
      ]
    }
  }
})

describe("ChatPane Stage 2 citation traceability and retrieval transparency", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    connectionStoreState.state.phase = ConnectionPhase.CONNECTED
    connectionStoreState.state.isChecking = false
    connectionStoreState.state.lastError = null

    workspaceStoreState.workspaceId = "workspace-a"
    workspaceStoreState.workspaceChatReferenceId = "workspace-a"
    workspaceStoreState.sources = []
    workspaceStoreState.selectedSourceIds = []
    workspaceStoreState.getSelectedSources = deriveSelectedSources
    workspaceStoreState.getSelectedMediaIds = deriveSelectedMediaIds
    workspaceStoreState.chatFocusTarget = null

    mockFocusSourceById.mockReturnValue(true)
    mockFocusSourceByMediaId.mockReturnValue(true)
    mockSetSelectedSourceIds.mockReset()
    mockSetSelectedSourceIds.mockImplementation((ids: string[]) => {
      workspaceStoreState.selectedSourceIds = [...ids]
    })
    mockGetWorkspaceChatSession.mockReturnValue(null)

    messageOptionState.messages = []
    messageOptionState.history = []
    messageOptionState.historyId = null
    messageOptionState.serverChatId = null
    messageOptionState.streaming = false
    messageOptionState.isProcessing = false
    mockOnSubmit.mockResolvedValue(undefined)
  })

  it("shows +N more source summary and expands on click", () => {
    workspaceStoreState.selectedSourceIds = [
      "s1",
      "s2",
      "s3",
      "s4",
      "s5",
      "s6",
      "s7"
    ]
    workspaceStoreState.getSelectedSources = () =>
      workspaceStoreState.selectedSourceIds.map((id, index) => ({
        id,
        title: `Source ${index + 1}`
      }))

    render(<ChatPane />)

    const moreButton = screen.getByRole("button", {
      name: "Show more sources"
    })
    expect(moreButton.textContent).toContain("+2")

    fireEvent.click(moreButton)
    expect(screen.getByRole("button", { name: "Show fewer sources" })).toBeInTheDocument()
  })

  it("routes citation clicks to media-id source focus action", () => {
    workspaceStoreState.sources = [
      {
        id: "source-42",
        mediaId: 42,
        title: "Primary Source",
        type: "pdf"
      }
    ]
    messageOptionState.messages = [
      {
        id: "bot-1",
        isBot: true,
        name: "Assistant",
        message: "Here is a grounded answer",
        sources: [
          {
            name: "Primary Source",
            metadata: { media_id: 42 }
          }
        ]
      }
    ]

    render(<ChatPane />)
    fireEvent.click(screen.getByRole("button", { name: "Open citation" }))

    expect(mockFocusSourceByMediaId).toHaveBeenCalledWith(42)
    expect(mockFocusSourceById).not.toHaveBeenCalled()
  })

  it("falls back to title-based source matching when citation media id is missing", () => {
    mockFocusSourceByMediaId.mockReturnValue(false)
    workspaceStoreState.sources = [
      {
        id: "source-alpha",
        mediaId: 101,
        title: "Alpha Source",
        type: "pdf"
      }
    ]
    messageOptionState.messages = [
      {
        id: "bot-2",
        isBot: true,
        name: "Assistant",
        message: "Citation by title",
        sources: [{ name: "Alpha Source" }]
      }
    ]

    render(<ChatPane />)
    fireEvent.click(screen.getByRole("button", { name: "Open citation" }))

    expect(mockFocusSourceById).toHaveBeenCalledWith("source-alpha")
  })

  it("shows retrieval diagnostics from generation metadata", () => {
    messageOptionState.messages = [
      {
        id: "bot-3",
        isBot: true,
        name: "Assistant",
        message: "Diagnostics response",
        sources: [{ name: "Doc A", metadata: { media_id: 10, score: 0.71 } }],
        generationInfo: {
          retrieval: {
            chunks_retrieved: 4,
            source_count: 1,
            avg_relevance_score: 0.87
          }
        }
      }
    ]

    render(<ChatPane />)

    expect(screen.getByText("Retrieval info")).toBeInTheDocument()
    expect(screen.getByText(/Chunks retrieved/i)).toBeInTheDocument()
    expect(screen.getByText(/Sources used/i)).toBeInTheDocument()
    expect(screen.getByText(/Avg relevance score/i)).toBeInTheDocument()
  })

  it("handles partial retrieval metadata by inferring diagnostics from sources", () => {
    messageOptionState.messages = [
      {
        id: "bot-4",
        isBot: true,
        name: "Assistant",
        message: "Partial diagnostics response",
        sources: [
          { name: "Doc A", metadata: { score: 0.5 } },
          { name: "Doc B", metadata: { score: 0.7 } }
        ]
      }
    ]

    render(<ChatPane />)

    expect(screen.getByText("Retrieval info")).toBeInTheDocument()
    expect(screen.getByText("0.600")).toBeInTheDocument()
  })

  it("scopes chat to dropped source and seeds a prompt template", () => {
    workspaceStoreState.sources = [
      {
        id: "source-drag",
        mediaId: 77,
        title: "Dragged Source",
        type: "pdf"
      }
    ]

    render(<ChatPane />)

    const dropZone = screen.getByTestId("chat-drop-zone")
    const dataTransfer = {
      types: [WORKSPACE_SOURCE_DRAG_TYPE],
      getData: (type: string) =>
        type === WORKSPACE_SOURCE_DRAG_TYPE
          ? JSON.stringify({
              sourceId: "source-drag",
              mediaId: 77,
              title: "Dragged Source",
              type: "pdf"
            })
          : "",
      dropEffect: ""
    }

    fireEvent.dragOver(dropZone, { dataTransfer })
    fireEvent.drop(dropZone, { dataTransfer })

    expect(mockSetSelectedSourceIds).toHaveBeenCalledWith(["source-drag"])
    const input = screen.getByPlaceholderText(
      "Ask about your sources..."
    ) as HTMLTextAreaElement
    expect(input.value).toContain("Dragged Source")
    expect(
      screen.getByRole("button", { name: "Restore previous selection" })
    ).toBeInTheDocument()
    expect(mockMessageInfo).toHaveBeenCalled()
  })

  it("restores previous source selection with explicit restore action", () => {
    workspaceStoreState.selectedSourceIds = ["source-a", "source-b"]
    workspaceStoreState.sources = [
      {
        id: "source-a",
        mediaId: 71,
        title: "Source A",
        type: "pdf"
      },
      {
        id: "source-b",
        mediaId: 72,
        title: "Source B",
        type: "pdf"
      },
      {
        id: "source-drag",
        mediaId: 77,
        title: "Dragged Source",
        type: "pdf"
      }
    ]

    render(<ChatPane />)

    const dropZone = screen.getByTestId("chat-drop-zone")
    const dataTransfer = {
      types: [WORKSPACE_SOURCE_DRAG_TYPE],
      getData: (type: string) =>
        type === WORKSPACE_SOURCE_DRAG_TYPE
          ? JSON.stringify({
              sourceId: "source-drag",
              mediaId: 77,
              title: "Dragged Source",
              type: "pdf"
            })
          : "",
      dropEffect: ""
    }

    fireEvent.dragOver(dropZone, { dataTransfer })
    fireEvent.drop(dropZone, { dataTransfer })
    fireEvent.click(
      screen.getByRole("button", { name: "Restore previous selection" })
    )

    expect(mockSetSelectedSourceIds).toHaveBeenNthCalledWith(1, ["source-drag"])
    expect(mockSetSelectedSourceIds).toHaveBeenNthCalledWith(2, [
      "source-a",
      "source-b"
    ])
  })

  it("auto-restores previous source selection after sending with temporary scope", async () => {
    workspaceStoreState.selectedSourceIds = ["source-a", "source-b"]
    workspaceStoreState.sources = [
      {
        id: "source-a",
        mediaId: 71,
        title: "Source A",
        type: "pdf"
      },
      {
        id: "source-b",
        mediaId: 72,
        title: "Source B",
        type: "pdf"
      },
      {
        id: "source-drag",
        mediaId: 77,
        title: "Dragged Source",
        type: "pdf"
      }
    ]
    workspaceStoreState.getSelectedSources = () => [
      {
        id: "source-a",
        mediaId: 71,
        title: "Source A",
        type: "pdf"
      },
      {
        id: "source-b",
        mediaId: 72,
        title: "Source B",
        type: "pdf"
      }
    ]
    workspaceStoreState.getSelectedMediaIds = () => [71, 72]
    messageOptionState.messages = [
      {
        id: "m1",
        isBot: true,
        name: "Assistant",
        message: "Previous response",
        sources: []
      }
    ]

    render(<ChatPane />)

    const dropZone = screen.getByTestId("chat-drop-zone")
    const dataTransfer = {
      types: [WORKSPACE_SOURCE_DRAG_TYPE],
      getData: (type: string) =>
        type === WORKSPACE_SOURCE_DRAG_TYPE
          ? JSON.stringify({
              sourceId: "source-drag",
              mediaId: 77,
              title: "Dragged Source",
              type: "pdf"
            })
          : "",
      dropEffect: ""
    }

    fireEvent.dragOver(dropZone, { dataTransfer })
    fireEvent.drop(dropZone, { dataTransfer })

    const input = screen.getByPlaceholderText("Ask about your sources...")
    fireEvent.change(input, { target: { value: "Question scoped to dropped source" } })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        message: "Question scoped to dropped source",
        image: ""
      })
    })

    await waitFor(() => {
      expect(mockSetSelectedSourceIds).toHaveBeenLastCalledWith([
        "source-a",
        "source-b"
      ])
    })

    expect(mockMessageInfo).not.toHaveBeenCalledWith(
      expect.objectContaining({
        key: "workspace-playground:source-context-warning"
      })
    )
  })

  it("shows a context change warning when sources are deselected mid-thread", () => {
    workspaceStoreState.selectedSourceIds = ["source-1", "source-2"]
    messageOptionState.messages = [
      {
        id: "m1",
        isBot: true,
        name: "Assistant",
        message: "Earlier answer",
        sources: []
      }
    ]

    const { rerender } = render(<ChatPane />)

    workspaceStoreState.selectedSourceIds = ["source-1"]
    rerender(<ChatPane />)

    expect(mockMessageInfo).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "workspace-playground:source-context-warning"
      })
    )
  })

  it("routes message branch actions to createChatBranch", () => {
    messageOptionState.messages = [
      {
        id: "bot-branch",
        isBot: true,
        name: "Assistant",
        message: "Branch me",
        sources: []
      }
    ]

    render(<ChatPane />)
    fireEvent.click(screen.getByRole("button", { name: "Create branch" }))

    expect(mockCreateChatBranch).toHaveBeenCalledWith(0)
  })

  it("switches assistant variants using swipe handlers", () => {
    messageOptionState.messages = [
      {
        id: "bot-variant",
        isBot: true,
        name: "Assistant",
        message: "Variant A",
        sources: [],
        variants: [
          { id: "variant-a", message: "Variant A", sources: [] },
          { id: "variant-b", message: "Variant B", sources: [] }
        ],
        activeVariantIndex: 0
      }
    ]

    render(<ChatPane />)
    fireEvent.click(screen.getByRole("button", { name: "Variant next" }))

    const updater = mockSetMessages.mock.calls.at(-1)?.[0]
    expect(typeof updater).toBe("function")
    if (typeof updater === "function") {
      const updatedMessages = updater(messageOptionState.messages)
      expect(updatedMessages[0]?.activeVariantIndex).toBe(1)
      expect(updatedMessages[0]?.message).toBe("Variant B")
    }
  })
})
