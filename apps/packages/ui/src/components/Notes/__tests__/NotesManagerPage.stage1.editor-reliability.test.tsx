import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import NotesManagerPage from "../NotesManagerPage"

const {
  mockBgRequest,
  mockMessageSuccess,
  mockMessageError,
  mockMessageWarning,
  mockNavigate,
  mockConfirmDanger,
  mockGetSetting,
  mockClearSetting
} = vi.hoisted(() => {
  return {
    mockBgRequest: vi.fn(),
    mockMessageSuccess: vi.fn(),
    mockMessageError: vi.fn(),
    mockMessageWarning: vi.fn(),
    mockNavigate: vi.fn(),
    mockConfirmDanger: vi.fn(),
    mockGetSetting: vi.fn(),
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
    info: vi.fn()
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

const createCalls = () =>
  mockBgRequest.mock.calls.filter(([request]) => {
    const path = String(request?.path || "")
    const method = String(request?.method || "GET").toUpperCase()
    return path === "/api/v1/notes/" && method === "POST"
  })

const updateCalls = () =>
  mockBgRequest.mock.calls.filter(([request]) => {
    const path = String(request?.path || "")
    const method = String(request?.method || "GET").toUpperCase()
    return path.startsWith("/api/v1/notes/11?expected_version=") && method === "PUT"
  })

describe("NotesManagerPage stage 1 editor reliability", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfirmDanger.mockResolvedValue(true)
    mockGetSetting.mockResolvedValue(null)
    mockClearSetting.mockResolvedValue(undefined)

    mockBgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request.path || "")
      const method = String(request.method || "GET").toUpperCase()

      if (path.startsWith("/api/v1/notes/?")) {
        return {
          items: [],
          pagination: { total_items: 0, total_pages: 1 }
        }
      }

      if (path === "/api/v1/notes/" && method === "POST") {
        return { id: 11, version: 1 }
      }

      if (path === "/api/v1/notes/11" && method === "GET") {
        return {
          id: 11,
          title: "Shortcut note",
          content: "Saved from keyboard",
          metadata: { keywords: [] },
          version: 1
        }
      }

      if (path.startsWith("/api/v1/notes/11?expected_version=") && method === "PUT") {
        return { id: 11, version: 2 }
      }

      return {}
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("saves with Ctrl+S and Cmd+S keyboard shortcuts", async () => {
    renderPage()

    const titleInput = screen.getByPlaceholderText("Title")
    const contentInput = screen.getByPlaceholderText(
      "Write your note here... (Markdown supported)"
    )

    fireEvent.change(titleInput, {
      target: { value: "Shortcut note" }
    })
    fireEvent.change(contentInput, {
      target: { value: "Saved from keyboard" }
    })

    fireEvent.focus(contentInput)
    fireEvent.keyDown(contentInput, { key: "s", ctrlKey: true })

    await waitFor(() => {
      expect(createCalls()).toHaveLength(1)
    })

    expect(mockMessageSuccess).toHaveBeenCalledWith("Note created")

    fireEvent.change(contentInput, {
      target: { value: "Updated via cmd shortcut" }
    })

    fireEvent.focus(titleInput)
    fireEvent.keyDown(titleInput, { key: "s", metaKey: true })

    await waitFor(() => {
      expect(updateCalls()).toHaveLength(1)
    })
  })

  it("does not save when Ctrl/Cmd+S is pressed outside the editor region", async () => {
    renderPage()

    fireEvent.change(screen.getByPlaceholderText("Title"), {
      target: { value: "Shortcut note" }
    })
    fireEvent.change(
      screen.getByPlaceholderText("Write your note here... (Markdown supported)"),
      {
        target: { value: "Saved from keyboard" }
      }
    )

    const searchInput = screen.getByPlaceholderText("Search notes... (use quotes for exact match)")
    fireEvent.focus(searchInput)
    fireEvent.keyDown(searchInput, { key: "s", ctrlKey: true })
    fireEvent.keyDown(searchInput, { key: "s", metaKey: true })

    await waitFor(() => {
      expect(createCalls()).toHaveLength(0)
    })
  })

  it("hides the welcome state after starting a new draft", async () => {
    renderPage()

    expect(screen.getByTestId("notes-editor-empty-state")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("notes-editor-empty-create"))

    await waitFor(() => {
      expect(screen.queryByTestId("notes-editor-empty-state")).not.toBeInTheDocument()
    })
  })

  it("preserves the pending last-note setting when note hydration fails", async () => {
    mockGetSetting.mockResolvedValue("pending-note")
    mockBgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request.path || "")
      const method = String(request.method || "GET").toUpperCase()

      if (path.startsWith("/api/v1/notes/?")) {
        return {
          items: [
            {
              id: "pending-note",
              title: "Pending note",
              content: "Preview",
              metadata: { keywords: [] },
              version: 1
            }
          ],
          pagination: { total_items: 1, total_pages: 1 }
        }
      }

      if (path === "/api/v1/notes/pending-note" && method === "GET") {
        throw new Error("load failed")
      }

      return {}
    })

    renderPage()

    await waitFor(() => {
      expect(mockMessageError).toHaveBeenCalledWith("Failed to load note")
    })
    expect(mockClearSetting).not.toHaveBeenCalled()
  })

  it("blocks study-pack launch while the selected note has unsaved edits", async () => {
    mockGetSetting.mockResolvedValue("11")
    mockBgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request.path || "")
      const method = String(request.method || "GET").toUpperCase()

      if (path.startsWith("/api/v1/notes/?")) {
        return {
          items: [
            {
              id: "11",
              title: "Saved note",
              content: "Original saved content",
              metadata: { keywords: [] },
              version: 1
            }
          ],
          pagination: { total_items: 1, total_pages: 1 }
        }
      }

      if (path === "/api/v1/notes/11" && method === "GET") {
        return {
          id: 11,
          title: "Saved note",
          content: "Original saved content",
          metadata: { keywords: [] },
          version: 1
        }
      }

      return {}
    })

    renderPage()

    const contentInput = await screen.findByPlaceholderText(
      "Write your note here... (Markdown supported)"
    )
    await waitFor(() => {
      expect(screen.getByDisplayValue("Saved note")).toBeInTheDocument()
    })

    fireEvent.change(contentInput, {
      target: { value: "Unsaved update for study pack launch" }
    })

    const createStudyPackButton = screen.getByTestId("notes-create-study-pack-button")
    await waitFor(() => {
      expect(createStudyPackButton).toBeDisabled()
    })

    fireEvent.click(createStudyPackButton)

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it("autosaves after idle delay without success toast spam", async () => {
    vi.useFakeTimers()
    renderPage()

    fireEvent.change(screen.getByPlaceholderText("Title"), {
      target: { value: "Autosave note" }
    })
    fireEvent.change(
      screen.getByPlaceholderText("Write your note here... (Markdown supported)"),
      {
        target: { value: "Autosaved content" }
      }
    )

    expect(createCalls()).toHaveLength(0)

    vi.advanceTimersByTime(4900)
    expect(createCalls()).toHaveLength(0)

    await act(async () => {
      vi.advanceTimersByTime(100)
      await Promise.resolve()
    })

    expect(createCalls()).toHaveLength(1)
    expect(mockMessageSuccess).not.toHaveBeenCalledWith("Note created")
  })
})
