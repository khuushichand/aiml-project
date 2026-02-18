import React from "react"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQA } from "../index"

const state = {
  settingsPanelOpen: false,
  setSettingsPanelOpen: vi.fn(),
  results: [] as Array<{ id: string }>,
  answer: null as string | null,
  hasSearched: false,
  isSearching: false,
  error: null as string | null,
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

describe("KnowledgeQA golden layout guardrails", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    state.settingsPanelOpen = false
    state.results = []
    state.answer = null
    state.hasSearched = false
    state.isSearching = false
    state.error = null
    connectivity.online = true
    connectivity.isChecking = false
    connectivity.lastCheckedAt = Date.now()
    capabilitiesState.loading = false
    capabilitiesState.capabilities = { hasRag: true }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("keeps hero + search-first layout when there are no results", () => {
    render(<KnowledgeQA />)

    expect(screen.getByTestId("knowledge-history-sidebar")).toBeInTheDocument()
    expect(screen.getByText("Knowledge QA")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-bar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-shell").className).toContain("flex-1")
    expect(
      screen.queryByTestId("knowledge-answer-panel")
    ).not.toBeInTheDocument()
  })

  it("switches to results layout while preserving history and search shell", () => {
    state.results = [{ id: "r1" }]

    render(<KnowledgeQA />)

    expect(screen.getByTestId("knowledge-history-sidebar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-bar")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-answer-panel")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-source-list")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-followup-input")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-shell").className).toContain("pt-6 pb-4")
    expect(screen.getByTestId("knowledge-search-shell").className).not.toContain("flex-1")
    expect(screen.getByTestId("knowledge-results-shell").className).toContain(
      "animate-in fade-in duration-200"
    )
    expect(screen.queryByText("Knowledge QA")).not.toBeInTheDocument()
  })

  it("shows explicit no-results guidance after an empty completed search", () => {
    state.hasSearched = true
    state.results = []
    state.answer = null
    state.error = null

    render(<KnowledgeQA />)

    expect(screen.getByText("No results found")).toBeInTheDocument()
    expect(screen.getByText(/Confirm your sources were ingested and indexed/i)).toBeInTheDocument()
  })

  it("keeps results shell visible during active search to support queued follow-ups", () => {
    state.isSearching = true
    state.results = []
    state.answer = null
    state.error = null

    render(<KnowledgeQA />)

    expect(screen.getByTestId("knowledge-followup-input")).toBeInTheDocument()
    expect(screen.queryByText("Knowledge QA")).not.toBeInTheDocument()
  })

  it("exposes skip navigation and landmark regions", () => {
    render(<KnowledgeQA />)

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

    render(<KnowledgeQA />)

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

    render(<KnowledgeQA />)

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
})
