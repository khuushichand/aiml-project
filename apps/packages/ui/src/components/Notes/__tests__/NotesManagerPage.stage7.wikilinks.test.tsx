import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
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

vi.mock("@/components/Common/MarkdownPreview", () => ({
  MarkdownPreview: ({ content }: { content: string }) => {
    const hrefMatch = content.match(/note:\/\/[^\)\s]+/)
    if (hrefMatch) {
      return (
        <a data-testid="markdown-preview-note-link" href={hrefMatch[0]}>
          wikilink
        </a>
      )
    }
    return <div data-testid="markdown-preview-content">{content}</div>
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

describe("NotesManagerPage stage 7 wikilinks", () => {
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
          items: [{ id: "note-b", title: "Linked note", content: "Linked body", version: 1 }],
          pagination: { total_items: 1, total_pages: 1 }
        }
      }
      if (path.startsWith("/api/v1/notes/note-b/neighbors")) {
        return {
          nodes: [{ id: "note-b", type: "note", label: "Linked note" }],
          edges: []
        }
      }
      if (path === "/api/v1/notes/note-b" && method === "GET") {
        return {
          id: "note-b",
          title: "Linked note",
          content: "Loaded linked content",
          metadata: { keywords: [] },
          version: 2,
          last_modified: "2026-02-18T11:00:00.000Z"
        }
      }
      return {}
    })
  })

  it("shows wikilink suggestions and inserts selected title", async () => {
    renderPage()

    const textarea = screen.getByPlaceholderText("Write your note here... (Markdown supported)")
    fireEvent.change(textarea, { target: { value: "See [[Li" } })

    const suggestions = await screen.findByTestId("notes-wikilink-suggestions")
    expect(suggestions).toHaveTextContent("Linked note")

    fireEvent.keyDown(textarea, { key: "Enter" })

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Write your note here... (Markdown supported)")
      ).toHaveValue("See [[Linked note]]")
    })
  })

  it("opens resolved wikilink when clicked in preview mode", async () => {
    renderPage()

    const textarea = screen.getByPlaceholderText("Write your note here... (Markdown supported)")
    fireEvent.change(textarea, { target: { value: "[[Linked note]]" } })

    fireEvent.click(screen.getByRole("button", { name: "Preview" }))
    fireEvent.click(await screen.findByTestId("markdown-preview-note-link"))

    await waitFor(() => {
      const openedLinkedNote = mockBgRequest.mock.calls.some(([request]) => {
        const path = String(request?.path || "")
        const method = String(request?.method || "GET").toUpperCase()
        return path === "/api/v1/notes/note-b" && method === "GET"
      })
      expect(openedLinkedNote).toBe(true)
    })
  })

  it("opens resolved wikilink when clicked in split preview", async () => {
    renderPage()

    const textarea = screen.getByPlaceholderText("Write your note here... (Markdown supported)")
    fireEvent.change(textarea, { target: { value: "Reference [[Linked note]] here" } })

    fireEvent.click(screen.getByRole("button", { name: "Split" }))
    fireEvent.click(await screen.findByTestId("markdown-preview-note-link"))

    await waitFor(() => {
      const openedLinkedNote = mockBgRequest.mock.calls.some(([request]) => {
        const path = String(request?.path || "")
        const method = String(request?.method || "GET").toUpperCase()
        return path === "/api/v1/notes/note-b" && method === "GET"
      })
      expect(openedLinkedNote).toBe(true)
    })
  })
})
