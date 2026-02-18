import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SearchDetailsPanel } from "../SearchDetailsPanel"

const state = {
  searchDetails: null as any,
  isSearching: false,
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    searchDetails: state.searchDetails,
    isSearching: state.isSearching,
  }),
}))

describe("SearchDetailsPanel", () => {
  beforeEach(() => {
    state.searchDetails = null
    state.isSearching = false
  })

  it("does not render without search detail data", () => {
    const { container } = render(<SearchDetailsPanel />)
    expect(container).toBeEmptyDOMElement()
  })

  it("renders collapsible runtime search details", () => {
    state.searchDetails = {
      expandedQueries: ["q1 variation", "q1 synonym"],
      rerankingEnabled: true,
      rerankingStrategy: "hybrid",
      averageRelevance: 0.84,
      webFallbackEnabled: true,
      webFallbackTriggered: true,
      webFallbackEngine: "duckduckgo",
      whyTheseSources: {
        topicality: 0.91,
        diversity: 0.45,
        freshness: null,
      },
    }

    render(<SearchDetailsPanel />)

    expect(screen.getByText("Search details")).toBeInTheDocument()
    expect(screen.getByText(/q1 variation, q1 synonym/)).toBeInTheDocument()
    expect(screen.getByText(/Enabled \(hybrid\)/)).toBeInTheDocument()
    expect(screen.getByText("84%")).toBeInTheDocument()
    expect(screen.getByText(/Triggered \(duckduckgo\)/)).toBeInTheDocument()
  })
})
