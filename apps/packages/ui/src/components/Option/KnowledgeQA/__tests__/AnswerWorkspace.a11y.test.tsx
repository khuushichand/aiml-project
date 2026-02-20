import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AnswerWorkspace } from "../panels/AnswerWorkspace"

const state = {
  results: [] as Array<{ id: string }>,
  error: null as string | null,
  messages: [] as Array<{
    id: string
    role: "user" | "assistant" | "system"
    content?: string
  }>,
  currentThreadId: null as string | null,
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    results: state.results,
    error: state.error,
    messages: state.messages,
    currentThreadId: state.currentThreadId,
  }),
}))

vi.mock("../ConversationThread", () => ({
  ConversationThread: () => <div data-testid="knowledge-conversation-thread" />,
}))

vi.mock("../AnswerPanel", () => ({
  AnswerPanel: () => <div data-testid="knowledge-answer-panel" />,
}))

vi.mock("../FollowUpInput", () => ({
  FollowUpInput: () => <div data-testid="knowledge-followup-input" />,
}))

describe("AnswerWorkspace accessibility announcements", () => {
  beforeEach(() => {
    state.results = []
    state.error = null
    state.messages = []
    state.currentThreadId = null
  })

  it("announces active and completed search stages through live regions", () => {
    const { rerender } = render(<AnswerWorkspace queryStage="searching" />)

    expect(screen.getByText("Searching your selected sources.")).toBeInTheDocument()

    state.results = [{ id: "r1" }, { id: "r2" }]
    rerender(<AnswerWorkspace queryStage="complete" />)

    expect(screen.getByText("Search complete. 2 sources found.")).toBeInTheDocument()
  })

  it("announces search errors through assertive live region", () => {
    state.error = "Search timed out"

    render(<AnswerWorkspace queryStage="error" />)

    expect(screen.getByText("Search error. Search timed out")).toBeInTheDocument()
  })

  it("shows persistent thread context summary", () => {
    state.currentThreadId = "thread-1"
    state.messages = [
      { id: "m1", role: "user", content: "What changed in this release?" },
      {
        id: "m2",
        role: "assistant",
        content: "The release improves indexing speed and citation quality.",
      },
      { id: "m3", role: "user", content: "What should I test first?" },
    ]

    render(<AnswerWorkspace queryStage="idle" />)

    expect(screen.getByText("Conversation • 2 turns")).toBeInTheDocument()
    expect(screen.getByText("Using context from turn 1.")).toBeInTheDocument()
    expect(screen.getByText("Context previews (1)")).toBeInTheDocument()
    expect(screen.getByText("Turn 1")).toBeInTheDocument()
    expect(
      screen.getByText("What changed in this release?")
    ).toBeInTheDocument()
    expect(
      screen.getByText("The release improves indexing speed and citation quality.")
    ).toBeInTheDocument()
  })
})
