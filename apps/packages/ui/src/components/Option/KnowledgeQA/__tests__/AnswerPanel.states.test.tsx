import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AnswerPanel } from "../AnswerPanel"

const state = {
  answer: null as string | null,
  citations: [] as Array<{ index: number }>,
  isSearching: false,
  error: null as string | null,
  results: [] as Array<{ id: string; metadata?: { title?: string } }>,
  scrollToSource: vi.fn()
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    answer: state.answer,
    citations: state.citations,
    isSearching: state.isSearching,
    error: state.error,
    results: state.results,
    scrollToSource: state.scrollToSource
  })
}))

describe("AnswerPanel state guardrails", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.answer = null
    state.citations = []
    state.isSearching = false
    state.error = null
    state.results = []
  })

  it("renders nothing when there is no answer and no results", () => {
    const { container } = render(<AnswerPanel />)
    expect(container.firstChild).toBeNull()
  })

  it("renders no-answer guidance when results exist but answer generation is off", () => {
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]

    render(<AnswerPanel />)
    expect(
      screen.getByText(
        "Found 1 relevant source. Enable answer generation in settings to get a synthesized response."
      )
    ).toBeInTheDocument()
  })

  it("keeps citation jump interaction wired to source focus", () => {
    state.answer = "Use method [1] for better recall."
    state.citations = [{ index: 1 }]
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]

    render(<AnswerPanel />)
    const jumpButton = screen.getAllByRole("button", { name: "Jump to source 1" })[0]
    fireEvent.click(jumpButton)

    expect(state.scrollToSource).toHaveBeenCalledWith(0)
  })
})
