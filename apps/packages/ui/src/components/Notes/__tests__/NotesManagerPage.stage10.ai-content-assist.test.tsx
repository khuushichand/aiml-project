import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import NotesManagerPage from "../NotesManagerPage"

const {
  mockBgRequest,
  mockMessageSuccess,
  mockMessageError,
  mockMessageWarning,
  mockMessageInfo,
  mockNavigate,
  mockConfirmDanger,
  mockGetSetting,
  mockSetSetting,
  mockClearSetting
} = vi.hoisted(() => {
  return {
    mockBgRequest: vi.fn(),
    mockMessageSuccess: vi.fn(),
    mockMessageError: vi.fn(),
    mockMessageWarning: vi.fn(),
    mockMessageInfo: vi.fn(),
    mockNavigate: vi.fn(),
    mockConfirmDanger: vi.fn(),
    mockGetSetting: vi.fn(),
    mockSetSetting: vi.fn(),
    mockClearSetting: vi.fn()
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
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

vi.mock("@/services/background-proxy", () => ({
  bgRequest: mockBgRequest
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/context/demo-mode", () => ({
  useDemoMode: () => ({ demoEnabled: false })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasNotes: true },
    loading: false
  })
}))

vi.mock("@/components/Common/confirm-danger", () => ({
  useConfirmDanger: () => mockConfirmDanger
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    success: mockMessageSuccess,
    error: mockMessageError,
    warning: mockMessageWarning,
    info: mockMessageInfo
  })
}))

vi.mock("@/services/note-keywords", () => ({
  getAllNoteKeywordStats: vi.fn(async () => []),
  searchNoteKeywords: vi.fn(async () => [])
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      setHistory: vi.fn(),
      setMessages: vi.fn(),
      setHistoryId: vi.fn(),
      setServerChatId: vi.fn(),
      setServerChatState: vi.fn(),
      setServerChatTopic: vi.fn(),
      setServerChatClusterId: vi.fn(),
      setServerChatSource: vi.fn(),
      setServerChatExternalRef: vi.fn()
    })
}))

vi.mock("@/services/settings/registry", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/settings/registry")>()
  return {
    ...actual,
    getSetting: mockGetSetting,
    setSetting: mockSetSetting,
    clearSetting: mockClearSetting
  }
})

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    initialize: vi.fn(async () => undefined),
    getChat: vi.fn(async () => null),
    listChatMessages: vi.fn(async () => []),
    getCharacter: vi.fn(async () => null)
  }
}))

vi.mock("@/components/Common/MarkdownPreview", () => ({
  MarkdownPreview: ({ content }: { content: string }) => (
    <div data-testid="markdown-preview-content">{content}</div>
  )
}))

vi.mock("@/components/Notes/NotesListPanel", () => ({
  default: () => <div data-testid="notes-list-panel" />
}))

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <NotesManagerPage />
    </QueryClientProvider>
  )
}

describe("NotesManagerPage stage 10 AI content assist actions", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfirmDanger.mockResolvedValue(true)
    mockGetSetting.mockResolvedValue(null)
    mockSetSetting.mockResolvedValue(undefined)
    mockClearSetting.mockResolvedValue(undefined)
    mockBgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request.path || "")
      const method = String(request.method || "GET").toUpperCase()
      if (path.startsWith("/api/v1/notes/?")) {
        return { items: [], pagination: { total_items: 0, total_pages: 1 } }
      }
      if (path === "/api/v1/admin/notes/title-settings" && method === "GET") {
        return {
          llm_enabled: false,
          default_strategy: "heuristic",
          effective_strategy: "heuristic",
          strategies: ["heuristic", "llm", "llm_fallback"]
        }
      }
      return {}
    })
  })

  it("applies summarize assist only after confirmation and tracks provenance", async () => {
    renderPage()
    const textarea = screen.getByPlaceholderText("Write your note here... (Markdown supported)")

    fireEvent.change(textarea, {
      target: {
        value:
          "Research notes explain baseline outcomes. They compare two model variants. Final section captures open questions."
      }
    })
    fireEvent.click(screen.getByTestId("notes-assist-summarize"))

    await waitFor(() => {
      expect(mockConfirmDanger).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(
        (screen.getByPlaceholderText("Write your note here... (Markdown supported)") as HTMLTextAreaElement).value
      ).toContain("Summary:")
    })
    expect(screen.getByTestId("notes-editor-provenance")).toHaveTextContent(
      "Edit source: Generated (Summarize"
    )

    fireEvent.change(screen.getByPlaceholderText("Write your note here... (Markdown supported)"), {
      target: { value: "manual update after summary" }
    })
    await waitFor(() => {
      expect(screen.getByTestId("notes-editor-provenance")).toHaveTextContent("Edit source: Manual")
    })
  })

  it("does not mutate content when summarize confirmation is rejected", async () => {
    mockConfirmDanger.mockResolvedValueOnce(false)
    renderPage()
    const textarea = screen.getByPlaceholderText(
      "Write your note here... (Markdown supported)"
    ) as HTMLTextAreaElement
    fireEvent.change(textarea, {
      target: { value: "Keep this draft exactly as typed." }
    })

    fireEvent.click(screen.getByTestId("notes-assist-summarize"))

    await waitFor(() => {
      expect(mockConfirmDanger).toHaveBeenCalled()
    })
    expect(textarea.value).toBe("Keep this draft exactly as typed.")
    expect(screen.getByTestId("notes-editor-provenance")).toHaveTextContent("Edit source: Manual")
  })

  it("suggests keywords with explicit selection and marks generated provenance after apply", async () => {
    renderPage()
    fireEvent.change(screen.getByPlaceholderText("Write your note here... (Markdown supported)"), {
      target: {
        value:
          "Quantum models track entanglement and decoherence. Quantum experiments repeat entanglement checks."
      }
    })

    fireEvent.click(screen.getByTestId("notes-assist-suggest-keywords"))

    await waitFor(() => {
      expect(screen.getByTestId("notes-assist-keyword-suggestions-modal")).toBeInTheDocument()
    })

    expect(mockConfirmDanger).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId("notes-assist-keyword-option-checks"))
    fireEvent.click(screen.getByRole("button", { name: "Apply selected" }))

    await waitFor(() => {
      expect(mockMessageSuccess).toHaveBeenCalledWith("Applied suggested keywords.")
    })
    expect(screen.getByTestId("notes-editor-provenance")).toHaveTextContent(
      "Edit source: Generated (Suggest keywords"
    )
    const editorKeywordsControl = screen.getByTestId("notes-keywords-editor")
    expect(within(editorKeywordsControl).getByText("quantum")).toBeInTheDocument()
    expect(within(editorKeywordsControl).queryByText("checks")).not.toBeInTheDocument()
  })

  it("does not attach suggested keywords when the review modal is canceled", async () => {
    renderPage()
    fireEvent.change(screen.getByPlaceholderText("Write your note here... (Markdown supported)"), {
      target: {
        value:
          "Quantum models track entanglement and decoherence. Quantum experiments repeat entanglement checks."
      }
    })

    fireEvent.click(screen.getByTestId("notes-assist-suggest-keywords"))
    const modal = await screen.findByTestId("notes-assist-keyword-suggestions-modal")
    expect(modal).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

    await waitFor(() => {
      expect(screen.getByTestId("notes-editor-provenance")).toHaveTextContent("Edit source: Manual")
    })
    const editorKeywordsControl = screen.getByTestId("notes-keywords-editor")
    expect(within(editorKeywordsControl).queryByText("quantum")).not.toBeInTheDocument()
  })
})
