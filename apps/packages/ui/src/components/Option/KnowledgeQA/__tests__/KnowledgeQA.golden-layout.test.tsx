import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgeQA } from "../index"

const state = {
  settingsPanelOpen: false,
  setSettingsPanelOpen: vi.fn(),
  results: [] as Array<{ id: string }>,
  answer: null as string | null
}

vi.mock("../KnowledgeQAProvider", () => ({
  KnowledgeQAProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useKnowledgeQA: () => state
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: false,
    capabilities: { hasRag: true }
  })
}))

vi.mock("../SearchBar", () => ({
  SearchBar: () => <div data-testid="knowledge-search-bar" />
}))

vi.mock("../HistorySidebar", () => ({
  HistorySidebar: () => <div data-testid="knowledge-history-sidebar" />
}))

vi.mock("../AnswerPanel", () => ({
  AnswerPanel: () => <div data-testid="knowledge-answer-panel" />
}))

vi.mock("../SourceList", () => ({
  SourceList: () => <div data-testid="knowledge-source-list" />
}))

vi.mock("../FollowUpInput", () => ({
  FollowUpInput: () => <div data-testid="knowledge-followup-input" />
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
    state.settingsPanelOpen = false
    state.results = []
    state.answer = null
  })

  it("keeps hero + search-first layout when there are no results", () => {
    render(<KnowledgeQA />)

    expect(screen.getByTestId("knowledge-history-sidebar")).toBeInTheDocument()
    expect(screen.getByText("Knowledge QA")).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-search-bar")).toBeInTheDocument()
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
    expect(screen.queryByText("Knowledge QA")).not.toBeInTheDocument()
  })
})
