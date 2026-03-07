import React from "react"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQA } from "../index"
import { MemoryRouter } from "react-router-dom"

const state = {
  settingsPanelOpen: false,
  setSettingsPanelOpen: vi.fn(),
  results: [] as Array<{ id: string }>,
  answer: null as string | null,
  citations: [] as Array<{ id: string }>,
  hasSearched: false,
  isSearching: false,
  error: null as string | null,
  queryStage: "idle" as string,
  preset: "balanced" as string,
  setPreset: vi.fn(),
  settings: {
    sources: [] as string[],
    enable_web_fallback: true,
    top_k: 10,
    include_media_ids: [] as string[],
    include_note_ids: [] as string[],
  },
  updateSetting: vi.fn(),
  setQuery: vi.fn(),
  currentThreadId: null as string | null,
  selectThread: vi.fn(),
  selectSharedThread: vi.fn(),
  searchHistory: [] as Array<{
    id: string
    query: string
    timestamp: string
    sourcesCount: number
    hasAnswer: boolean
    keywords?: string[]
    conversationId?: string
  }>,
  restoreFromHistory: vi.fn(),
  messages: [] as Array<{ role: string; content: string }>,
  evidenceRailOpen: false,
  setEvidenceRailOpen: vi.fn(),
  evidenceRailTab: "sources" as string,
  setEvidenceRailTab: vi.fn(),
  lastSearchScope: null as null | {
    preset: string
    webFallback: boolean
    sources: string[]
  },
  focusSource: vi.fn(),
}
const connectivity = {
  online: true,
  isChecking: false,
  lastCheckedAt: Date.now(),
  checkOnce: vi.fn(),
}
const capabilitiesState = {
  loading: false,
  capabilities: { hasRag: true },
  refresh: vi.fn(),
}

const layoutModeState = {
  mode: "simple" as "simple" | "research" | "expert",
  isSimple: true,
  isResearch: false,
  showPromotionToast: false,
}

vi.mock("../KnowledgeQAProvider", () => ({
  KnowledgeQAProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useKnowledgeQA: () => state
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => connectivity.online
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: capabilitiesState.loading,
    capabilities: capabilitiesState.capabilities,
    refresh: capabilitiesState.refresh,
  })
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionActions: () => ({
    checkOnce: connectivity.checkOnce,
  }),
  useConnectionState: () => ({
    isChecking: connectivity.isChecking,
    lastCheckedAt: connectivity.lastCheckedAt,
  }),
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => false,
  useDesktop: () => true,
}))

vi.mock("../hooks/useLayoutMode", () => ({
  useLayoutMode: () => ({
    mode: layoutModeState.mode,
    setLayoutMode: vi.fn(),
    isSimple: layoutModeState.isSimple,
    isResearch: layoutModeState.isResearch,
    showPromotionToast: layoutModeState.showPromotionToast,
    dismissPromotion: vi.fn(),
    acceptPromotion: vi.fn(),
  }),
}))

vi.mock("../SearchBar", () => ({
  SearchBar: () => (
    <input
      id="knowledge-search-input"
      aria-label="Search your knowledge base"
      data-testid="knowledge-search-bar"
    />
  )
}))

vi.mock("../HistorySidebar", () => ({
  HistorySidebar: () => <div data-testid="knowledge-history-sidebar" />
}))

vi.mock("../AnswerPanel", () => ({
  AnswerPanel: () => <div data-testid="knowledge-answer-panel" />
}))

vi.mock("../SearchDetailsPanel", () => ({
  SearchDetailsPanel: () => <div data-testid="knowledge-search-details-panel" />
}))

vi.mock("../SourceList", () => ({
  SourceList: () => <div data-testid="knowledge-source-list" />
}))

vi.mock("../FollowUpInput", () => ({
  FollowUpInput: () => <div data-testid="knowledge-followup-input" />
}))

vi.mock("../ConversationThread", () => ({
  ConversationThread: () => <div data-testid="knowledge-conversation-thread" />
}))

vi.mock("../SettingsPanel", () => ({
  SettingsPanel: () => <div data-testid="knowledge-settings-panel" />
}))

vi.mock("../ExportDialog", () => ({
  ExportDialog: () => <div data-testid="knowledge-export-dialog" />
}))

function setSimpleMode() {
  layoutModeState.mode = "simple"
  layoutModeState.isSimple = true
  layoutModeState.isResearch = false
}

function setResearchMode() {
  layoutModeState.mode = "research"
  layoutModeState.isSimple = false
  layoutModeState.isResearch = true
}

describe("KnowledgeQA golden layout guardrails", () => {
  const renderKnowledgeQa = (initialEntries: string[] = ["/knowledge"]) =>
    render(
      <MemoryRouter initialEntries={initialEntries}>
        <KnowledgeQA />
      </MemoryRouter>
    )

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    state.settingsPanelOpen = false
    state.results = []
    state.answer = null
    state.citations = []
    state.hasSearched = false
    state.isSearching = false
    state.error = null
    state.queryStage = "idle"
    state.preset = "balanced"
    state.settings.sources = []
    state.settings.enable_web_fallback = true
    state.settings.top_k = 10
    state.settings.include_media_ids = []
    state.settings.include_note_ids = []
    state.currentThreadId = null
    state.searchHistory = []
    state.restoreFromHistory = vi.fn()
    state.messages = []
    state.evidenceRailOpen = false
    state.evidenceRailTab = "sources"
    state.lastSearchScope = null
    connectivity.online = true
    connectivity.isChecking = false
    connectivity.lastCheckedAt = Date.now()
    capabilitiesState.loading = false
    capabilitiesState.capabilities = { hasRag: true }
    setSimpleMode()
    layoutModeState.showPromotionToast = false
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("keeps hero + search-first layout when there are no results (simple mode)", () => {
    renderKnowledgeQa()

    expect(screen.getByText("Ask Your Library")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-bar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-shell").className).toContain("pt-6")
    expect(screen.getByTestId("knowledge-search-shell").className).not.toContain(
      "items-center"
    )
    expect(
      screen.queryByTestId("knowledge-answer-panel")
    ).not.toBeInTheDocument()
    // Simple mode hides history sidebar
    expect(
      screen.queryByTestId("knowledge-history-sidebar")
    ).not.toBeInTheDocument()
  })

  it("shows history sidebar in research mode empty state", () => {
    setResearchMode()

    renderKnowledgeQa()

    expect(screen.getByTestId("knowledge-history-sidebar")).toBeInTheDocument()
    expect(screen.getByText("Ask Your Library")).toBeInTheDocument()
  })

  it("shows onboarding guide and no-source recovery copy on first run", () => {
    renderKnowledgeQa()

    expect(screen.getByText("How it works")).toBeInTheDocument()
    expect(
      screen.getByText(
        /No sources are selected\. Start by choosing source categories/i
      )
    ).toBeInTheDocument()
    expect(screen.getByText("How do I add my first source?")).toBeInTheDocument()
  })

  it("switches ready-state suggestions when sources are selected", () => {
    state.settings.sources = ["media_db"]

    renderKnowledgeQa()

    expect(
      screen.getByText("Explain the methodology used in this study")
    ).toBeInTheDocument()
    expect(screen.queryByText("How do I add my first source?")).not.toBeInTheDocument()
  })

  it("opens settings panel from ready-state source action in simple mode", () => {
    renderKnowledgeQa()

    fireEvent.click(screen.getByRole("button", { name: "No sources selected" }))

    expect(state.setSettingsPanelOpen).toHaveBeenCalledWith(true)
  })

  it("restores the newest restorable knowledge session from ready-state", () => {
    state.searchHistory = [
      {
        id: "history-non-knowledge",
        query: "Not a knowledge entry",
        timestamp: "2026-02-19T10:00:00.000Z",
        sourcesCount: 0,
        hasAnswer: false,
        keywords: ["random"],
        conversationId: "wrong-thread",
      },
      {
        id: "history-knowledge-old",
        query: "Older knowledge session",
        timestamp: "2026-02-18T10:00:00.000Z",
        sourcesCount: 4,
        hasAnswer: true,
        keywords: ["__knowledge_QA__"],
        conversationId: "knowledge-thread-old",
      },
      {
        id: "history-knowledge-new",
        query: "Newest knowledge session",
        timestamp: "2026-02-19T12:00:00.000Z",
        sourcesCount: 2,
        hasAnswer: true,
        keywords: ["__knowledge_QA__"],
        conversationId: "knowledge-thread-new",
      },
    ]

    renderKnowledgeQa()

    fireEvent.click(screen.getByRole("button", { name: "Continue recent session" }))

    expect(state.restoreFromHistory).toHaveBeenCalledTimes(1)
    expect(state.restoreFromHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "history-knowledge-new",
        conversationId: "knowledge-thread-new",
      })
    )
  })

  it("continues from query-only knowledge history entries", () => {
    state.searchHistory = [
      {
        id: "history-knowledge-local",
        query: "Local only",
        timestamp: "2026-02-19T12:00:00.000Z",
        sourcesCount: 2,
        hasAnswer: true,
        keywords: ["__knowledge_QA__"],
      },
    ]

    renderKnowledgeQa()

    fireEvent.click(screen.getByRole("button", { name: "Continue recent session" }))

    expect(state.restoreFromHistory).toHaveBeenCalledTimes(1)
    expect(state.restoreFromHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "history-knowledge-local",
        query: "Local only",
      })
    )
  })

  it("falls back to restorable legacy history entries without knowledge keywords", () => {
    state.searchHistory = [
      {
        id: "legacy-history-entry",
        query: "Legacy session",
        timestamp: "2026-02-19T12:00:00.000Z",
        sourcesCount: 1,
        hasAnswer: true,
        conversationId: "legacy-thread",
      },
    ]

    renderKnowledgeQa()

    fireEvent.click(screen.getByRole("button", { name: "Continue recent session" }))

    expect(state.restoreFromHistory).toHaveBeenCalledTimes(1)
    expect(state.restoreFromHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "legacy-history-entry",
        conversationId: "legacy-thread",
      })
    )
  })

  it("switches to results layout while preserving search shell", () => {
    state.results = [{ id: "r1" }]

    renderKnowledgeQa()

    expect(screen.getByTestId("knowledge-search-bar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-answer-panel")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-followup-input")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-shell").className).toContain("pt-6 pb-4")
    expect(screen.getByTestId("knowledge-search-shell").className).not.toContain("flex-1")
    expect(screen.getByTestId("knowledge-results-shell").className).toContain(
      "animate-in fade-in duration-200"
    )
    expect(screen.getByTestId("knowledge-results-shell").className).toContain("pb-24")
    expect(screen.queryByText("Ask Your Library")).not.toBeInTheDocument()
  })

  it("shows history sidebar alongside results in research mode", () => {
    setResearchMode()
    state.results = [{ id: "r1" }]

    renderKnowledgeQa()

    expect(screen.getByTestId("knowledge-history-sidebar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-answer-panel")).toBeInTheDocument()
  })

  it("shows explicit no-results guidance after an empty completed search", () => {
    state.hasSearched = true
    state.results = []
    state.answer = null
    state.error = null

    renderKnowledgeQa()

    expect(screen.getByText("No results found")).toBeInTheDocument()
    expect(screen.getByText(/Confirm your sources were ingested and indexed/i)).toBeInTheDocument()
  })

  it("keeps results shell visible during active search to support queued follow-ups", () => {
    state.isSearching = true
    state.results = []
    state.answer = null
    state.error = null

    renderKnowledgeQa()

    expect(screen.getByTestId("knowledge-followup-input")).toBeInTheDocument()
    expect(screen.queryByText("Ask Your Library")).not.toBeInTheDocument()
  })

  it("exposes skip navigation and landmark regions", () => {
    setResearchMode()

    renderKnowledgeQa()

    const skipLink = screen.getByRole("link", { name: "Skip to search" })
    expect(skipLink).toHaveAttribute("href", "#knowledge-search-input")

    expect(screen.getByRole("complementary", { name: "Search history" })).toBeInTheDocument()
    expect(screen.getByRole("main")).toBeInTheDocument()
  })

  it("shows offline recovery actions with retry button and countdown", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-02-18T00:00:00.000Z"))
    connectivity.online = false
    connectivity.lastCheckedAt = Date.now()

    renderKnowledgeQa()

    expect(screen.getByText("Server Offline")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry connection" })).toBeInTheDocument()
    expect(screen.getByText("Retrying automatically in 10s...")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }))
    expect(connectivity.checkOnce).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(2_000)
    })
    expect(screen.getByText("Retrying automatically in 8s...")).toBeInTheDocument()
  })

  it("shows actionable RAG guidance with docs link and retry", () => {
    capabilitiesState.capabilities = { hasRag: false }

    renderKnowledgeQa()

    expect(screen.getByText("RAG Not Available")).toBeInTheDocument()
    expect(
      screen.getByText(/Configure embedding models and enable RAG/i)
    ).toBeInTheDocument()

    const docsLink = screen.getByRole("link", { name: "Open setup guide" })
    expect(docsLink).toHaveAttribute(
      "href",
      "https://github.com/rmusser01/tldw_server2#readme"
    )

    fireEvent.click(screen.getByRole("button", { name: "Retry capability check" }))
    expect(capabilitiesState.refresh).toHaveBeenCalledTimes(1)
  })

  it("hydrates the selected thread from permalink routes", () => {
    renderKnowledgeQa(["/knowledge/thread/thread-42"])

    expect(state.selectThread).toHaveBeenCalledWith("thread-42")
  })

  it("hydrates shared conversations from tokenized permalink routes", () => {
    renderKnowledgeQa(["/knowledge/shared/share-token-abc"])

    expect(state.selectSharedThread).toHaveBeenCalledWith("share-token-abc")
  })
})
