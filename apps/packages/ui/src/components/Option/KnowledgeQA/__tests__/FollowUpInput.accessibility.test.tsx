import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { FollowUpInput } from "../FollowUpInput"

const state = {
  askFollowUp: vi.fn(),
  isSearching: false,
  createNewThread: vi.fn(),
  results: [{ id: "r1" }] as Array<{ id: string }>,
  answer: null as string | null,
  isMobile: false,
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    askFollowUp: state.askFollowUp,
    isSearching: state.isSearching,
    createNewThread: state.createNewThread,
    results: state.results,
    answer: state.answer,
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => state.isMobile,
}))

describe("FollowUpInput accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.isSearching = false
    state.results = [{ id: "r1" }]
    state.answer = null
    state.isMobile = false
  })

  it("provides an explicit accessible name for the follow-up input", () => {
    render(<FollowUpInput />)

    expect(
      screen.getByRole("textbox", { name: "Ask a follow-up question" })
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Follow-up questions maintain context. Click "New Topic" to start fresh.'
      )
    ).toBeInTheDocument()
  })

  it("shows explicit New Topic text alongside the icon action", () => {
    render(<FollowUpInput />)
    expect(screen.getByRole("button", { name: "Start new topic" })).toHaveTextContent(
      "New Topic"
    )
  })

  it("renders queued follow-up state while an initial search is in progress", () => {
    state.isSearching = true
    state.results = []
    state.answer = null

    render(<FollowUpInput />)

    const input = screen.getByRole("textbox", { name: "Ask a follow-up question" })
    expect(input).toBeDisabled()
    expect(input).toHaveAttribute("placeholder", "Type your next question...")
    expect(
      screen.getByText(/queue your next question while the current search completes/i)
    ).toBeInTheDocument()
  })

  it("uses a sticky mobile layout with safe-area padding while keeping actions visible", () => {
    state.isMobile = true

    render(<FollowUpInput />)

    const stickyContainer = screen.getByTestId("knowledge-followup-sticky")
    expect(stickyContainer.className).toContain("fixed inset-x-0 bottom-0")
    expect(stickyContainer.className).toContain("env(safe-area-inset-bottom)")
    expect(screen.getByRole("button", { name: "Start new topic" })).toBeInTheDocument()
    expect(
      screen.getByRole("textbox", { name: "Ask a follow-up question" })
    ).toBeInTheDocument()
  })
})
