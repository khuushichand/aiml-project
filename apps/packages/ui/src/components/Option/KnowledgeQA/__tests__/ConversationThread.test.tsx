import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ConversationThread } from "../ConversationThread"

const state = {
  messages: [] as Array<any>,
  setQuery: vi.fn(),
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    messages: state.messages,
    setQuery: state.setQuery,
  }),
}))

vi.mock("@/hooks/useFeatureFlags", () => ({
  useKnowledgeQaBranching: () => [false],
}))

describe("ConversationThread", () => {
  beforeEach(() => {
    state.messages = []
    state.setQuery.mockReset()
  })

  it("renders prior turns and omits the latest turn shown in the main panel", () => {
    state.messages = [
      {
        id: "u1",
        role: "user",
        content: "What changed in Q1?",
        timestamp: "2026-02-18T08:00:00.000Z",
      },
      {
        id: "a1",
        role: "assistant",
        content: "Q1 revenue increased by 12%.",
        timestamp: "2026-02-18T08:00:05.000Z",
        ragContext: {
          retrieved_documents: [{ id: "d1" }, { id: "d2" }],
          citations: [{ text: "Q1 evidence" }, { text: "Q1 backup" }],
        },
      },
      {
        id: "u2",
        role: "user",
        content: "How does that compare with Q2?",
        timestamp: "2026-02-18T08:01:00.000Z",
      },
      {
        id: "a2",
        role: "assistant",
        content: "Q2 rose by 9%, so Q1 was higher.",
        timestamp: "2026-02-18T08:01:06.000Z",
        ragContext: {
          retrieved_documents: [{ id: "d3" }],
        },
      },
    ]

    render(<ConversationThread />)

    expect(screen.getByLabelText("Conversation thread")).toBeInTheDocument()
    expect(screen.getByText("What changed in Q1?")).toBeInTheDocument()
    expect(screen.queryByText("How does that compare with Q2?")).not.toBeInTheDocument()
    expect(screen.getByText("2 sources")).toBeInTheDocument()
    expect(screen.getByText("2 citations")).toBeInTheDocument()
  })

  it("returns null when there are no prior turns", () => {
    state.messages = [
      {
        id: "u1",
        role: "user",
        content: "Only one question",
        timestamp: "2026-02-18T08:00:00.000Z",
      },
      {
        id: "a1",
        role: "assistant",
        content: "Only one answer",
        timestamp: "2026-02-18T08:00:03.000Z",
      },
    ]

    const { container } = render(<ConversationThread />)

    expect(container).toBeEmptyDOMElement()
  })

  it("allows reusing a previous question by loading it into the main search input", async () => {
    state.messages = [
      {
        id: "u1",
        role: "user",
        content: "Original research question",
        timestamp: "2026-02-18T08:00:00.000Z",
      },
      {
        id: "a1",
        role: "assistant",
        content: "Original answer",
        timestamp: "2026-02-18T08:00:03.000Z",
      },
      {
        id: "u2",
        role: "user",
        content: "Latest question",
        timestamp: "2026-02-18T08:01:00.000Z",
      },
      {
        id: "a2",
        role: "assistant",
        content: "Latest answer",
        timestamp: "2026-02-18T08:01:03.000Z",
      },
    ]
    render(
      <>
        <input id="knowledge-search-input" defaultValue="draft" />
        <ConversationThread />
      </>
    )

    await userEvent.click(screen.getByRole("button", { name: "Reuse Question" }))
    expect(state.setQuery).toHaveBeenCalledWith("Original research question")
    expect(document.getElementById("knowledge-search-input")).toHaveFocus()
  })
})
