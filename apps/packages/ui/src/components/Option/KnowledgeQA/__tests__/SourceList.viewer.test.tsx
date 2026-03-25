import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SourceList } from "../SourceList"

const state = {
  results: [
    {
      id: "r1",
      content:
        "Full source content line 1.\nFull source content line 2.\nFull source content line 3.",
      metadata: {
        title: "Quarterly Financial Review",
        source_type: "notes",
        page_number: 12,
        url: "https://example.com/source/r1",
      },
      score: 0.92,
    },
  ] as Array<Record<string, any>>,
  citations: [{ index: 1 }] as Array<{ index: number }>,
  focusedSourceIndex: null as number | null,
  focusSource: vi.fn(),
  setQuery: vi.fn(),
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    results: state.results,
    citations: state.citations,
    focusedSourceIndex: state.focusedSourceIndex,
    focusSource: state.focusSource,
    setQuery: state.setQuery,
  }),
}))

describe("SourceList full-source viewer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.focusedSourceIndex = null
    vi.stubGlobal("open", vi.fn())
  })

  it("opens and closes full source preview modal from source actions", async () => {
    render(<SourceList />)

    fireEvent.click(screen.getByRole("button", { name: "View full source 1" }))

    const dialog = await screen.findByRole("dialog", {
      name: /Source 1: Quarterly Financial Review/i,
    })
    expect(dialog).toBeInTheDocument()
    expect(
      within(dialog).getByText(/Full source content line 2\./)
    ).toBeInTheDocument()
    expect(within(dialog).getByText(/Note • Page 12/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Close source preview" }))

    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: /Source 1: Quarterly Financial Review/i })
      ).not.toBeInTheDocument()
    )
  })
})
