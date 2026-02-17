import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { HistorySidebar } from "../HistorySidebar"

const state = {
  isMobile: false,
  historySidebarOpen: true,
  searchHistory: [] as Array<{
    id: string
    query: string
    timestamp: string
    keywords: string[]
    sourcesCount: number
    hasAnswer: boolean
  }>,
  setHistorySidebarOpen: vi.fn(),
  restoreFromHistory: vi.fn(),
  deleteHistoryItem: vi.fn(),
  setSettingsPanelOpen: vi.fn()
}

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => state.isMobile
}))

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    searchHistory: state.searchHistory,
    historySidebarOpen: state.historySidebarOpen,
    setHistorySidebarOpen: state.setHistorySidebarOpen,
    restoreFromHistory: state.restoreFromHistory,
    deleteHistoryItem: state.deleteHistoryItem,
    preset: "balanced",
    setSettingsPanelOpen: state.setSettingsPanelOpen
  })
}))

describe("HistorySidebar responsive layout", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.isMobile = false
    state.historySidebarOpen = true
    state.searchHistory = []
  })

  it("renders desktop sidebar as fixed-width panel when open", () => {
    render(<HistorySidebar />)
    expect(screen.getByTestId("knowledge-history-desktop-open")).toBeInTheDocument()
  })

  it("uses mobile overlay drawer when history is open on mobile", () => {
    state.isMobile = true
    state.historySidebarOpen = true

    render(<HistorySidebar />)
    expect(screen.getByTestId("knowledge-history-mobile-overlay")).toBeInTheDocument()
    expect(
      screen.queryByTestId("knowledge-history-desktop-open")
    ).not.toBeInTheDocument()
  })

  it("shows mobile open button when history is collapsed on mobile", () => {
    state.isMobile = true
    state.historySidebarOpen = false

    render(<HistorySidebar />)
    expect(screen.getByTestId("knowledge-history-mobile-open")).toBeInTheDocument()
    expect(
      screen.queryByTestId("knowledge-history-mobile-overlay")
    ).not.toBeInTheDocument()
  })

  it("restores a history item when selected", async () => {
    state.searchHistory = [
      {
        id: "h1",
        query: "How does retrieval ranking work?",
        timestamp: new Date().toISOString(),
        keywords: ["__knowledge_QA__"],
        sourcesCount: 2,
        hasAnswer: true
      }
    ]

    const { findByText } = render(<HistorySidebar />)
    const item = await findByText("How does retrieval ranking work?")
    item.click()

    expect(state.restoreFromHistory).toHaveBeenCalledTimes(1)
    expect(state.restoreFromHistory).toHaveBeenCalledWith(state.searchHistory[0])
  })
})
