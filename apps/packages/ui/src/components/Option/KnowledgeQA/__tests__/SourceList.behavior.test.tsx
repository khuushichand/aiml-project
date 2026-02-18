import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SourceList } from "../SourceList"

const state = {
  results: [] as Array<Record<string, any>>,
  citations: [] as Array<{ index: number }>,
  focusedSourceIndex: null as number | null,
  focusSource: vi.fn(),
  setQuery: vi.fn(),
  query: "source test query",
  currentThreadId: "thread-source-test" as string | null,
  messages: [{ id: "assistant-1", role: "assistant" }] as Array<{
    id: string
    role: string
  }>,
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    results: state.results,
    citations: state.citations,
    focusedSourceIndex: state.focusedSourceIndex,
    focusSource: state.focusSource,
    setQuery: state.setQuery,
    query: state.query,
    currentThreadId: state.currentThreadId,
    messages: state.messages,
  }),
}))

vi.mock("@/services/feedback", () => ({
  getFeedbackSessionId: () => "session-source-test",
  submitExplicitFeedback: vi.fn().mockResolvedValue({ ok: true }),
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: vi.fn(),
  }),
}))

vi.mock("@/utils/knowledge-qa-search-metrics", () => ({
  trackKnowledgeQaSearchMetric: vi.fn().mockResolvedValue(undefined),
}))

function makeResult(index: number, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: `source-${index}`,
    content: `Body for source ${index}`,
    metadata: {
      title: `Source ${index}`,
      source_type: index % 2 === 0 ? "media_db" : "notes",
      created_at: `2026-02-${String(10 + index).padStart(2, "0")}T12:00:00.000Z`,
      page_number: index,
      url: `https://example.com/source-${index}`,
      chunk_id: `chunk_${index}_of_20`,
    },
    score: 1 - index * 0.02,
    ...overrides,
  }
}

describe("SourceList researcher workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.focusedSourceIndex = null
    state.results = Array.from({ length: 12 }, (_, idx) => makeResult(idx + 1))
    state.citations = [{ index: 3 }, { index: 8 }]
  })

  it("supports source-type filter chips with counts", () => {
    render(<SourceList />)

    expect(screen.getByRole("button", { name: /All\s*12/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Notes\s*6/i }))

    const list = screen.getByRole("list", { name: "Retrieved sources" })
    const headings = within(list).getAllByRole("heading", { level: 4 })
    expect(headings.every((heading) => /Source (1|3|5|7|9|11)/.test(heading.textContent || ""))).toBe(
      true
    )
  })

  it("uses compact source-card defaults for mobile density", () => {
    render(<SourceList />)

    const sourceCard = document.getElementById("source-card-0")
    expect(sourceCard).not.toBeNull()

    const headerRow = sourceCard!.querySelector("div.flex.items-start")
    expect(headerRow).not.toBeNull()
    expect(headerRow!.className).toContain("p-3")
    expect(headerRow!.className).toContain("sm:p-4")

    const excerpt = screen.getByText("Body for source 1")
    expect(excerpt.className).toContain("text-xs")
    expect(excerpt.className).toContain("sm:text-sm")
  })

  it("adds sort modes including date and cited-first", () => {
    render(<SourceList />)

    const sortSelect = screen.getByLabelText("Sort sources")
    fireEvent.change(sortSelect, { target: { value: "cited" } })

    const list = screen.getByRole("list", { name: "Retrieved sources" })
    const titles = within(list)
      .getAllByRole("heading", { level: 4 })
      .map((heading) => heading.textContent)

    expect(titles[0]).toBe("Source 3")
    expect(titles[1]).toBe("Source 8")

    fireEvent.change(sortSelect, { target: { value: "date" } })
    const resortedTitles = within(list)
      .getAllByRole("heading", { level: 4 })
      .map((heading) => heading.textContent)
    expect(resortedTitles[0]).toBe("Source 12")
  })

  it("paginates large result sets with show-more progression", async () => {
    render(<SourceList />)

    expect(screen.getByText("Showing 10 of 12 sources")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Show more \(2 remaining\)/i }))

    await waitFor(() =>
      expect(screen.getByText("Showing 12 of 12 sources")).toBeInTheDocument()
    )
  })

  it("supports ask-template variants and populates the query", () => {
    render(<SourceList />)

    const templateSelect = screen.getByLabelText("Ask template for Source 1")
    fireEvent.change(templateSelect, { target: { value: "summary" } })
    fireEvent.click(screen.getByRole("button", { name: "Ask about Source 1" }))

    expect(state.setQuery).toHaveBeenCalledWith("Summarize Source 1")
  })

  it("copies citation-formatted output for individual sources", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    render(<SourceList />)
    fireEvent.click(screen.getAllByRole("button", { name: "Copy citation" })[0])

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        "Source 1 (Page 1) - https://example.com/source-1"
      )
    )
  })

  it("opens keyboard shortcut legend via ? and closes on escape", async () => {
    render(<SourceList />)

    fireEvent.keyDown(window, { key: "?" })
    expect(
      screen.getByRole("dialog", { name: "Source keyboard shortcuts" })
    ).toBeInTheDocument()

    fireEvent.keyDown(window, { key: "Escape" })
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Source keyboard shortcuts" })
      ).not.toBeInTheDocument()
    )
  })
})
