import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ConversationThread } from "../ConversationThread"

const state = {
  messages: [] as Array<any>,
  setQuery: vi.fn(),
  branchFromTurn: vi.fn().mockResolvedValue(undefined),
  searchHistory: [] as Array<any>,
  currentThreadId: "thread-current" as string | null,
}

const fetchWithAuthMock = vi.fn()
let branchingEnabled = true

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    messages: state.messages,
    setQuery: state.setQuery,
    branchFromTurn: state.branchFromTurn,
    searchHistory: state.searchHistory,
    currentThreadId: state.currentThreadId,
  }),
}))

vi.mock("@/hooks/useFeatureFlags", () => ({
  useKnowledgeQaBranching: () => [branchingEnabled],
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    fetchWithAuth: (...args: unknown[]) => fetchWithAuthMock(...args),
  },
}))

describe("ConversationThread", () => {
  beforeEach(() => {
    state.messages = []
    state.searchHistory = []
    state.currentThreadId = "thread-current"
    state.setQuery.mockReset()
    state.branchFromTurn.mockReset().mockResolvedValue(undefined)
    fetchWithAuthMock.mockReset().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
      text: async () => "",
    })
    branchingEnabled = true
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

  it("branches from a selected historical turn", async () => {
    state.messages = [
      {
        id: "u1",
        role: "user",
        content: "What happened in quarter one?",
        timestamp: "2026-02-18T08:00:00.000Z",
      },
      {
        id: "a1",
        role: "assistant",
        content: "Quarter one answer.",
        timestamp: "2026-02-18T08:00:03.000Z",
      },
      {
        id: "u2",
        role: "user",
        content: "What happened in quarter two?",
        timestamp: "2026-02-18T08:01:00.000Z",
      },
      {
        id: "a2",
        role: "assistant",
        content: "Quarter two answer.",
        timestamp: "2026-02-18T08:01:03.000Z",
      },
    ]

    render(<ConversationThread />)

    await userEvent.click(screen.getByRole("button", { name: "Start Branch" }))

    expect(state.branchFromTurn).toHaveBeenCalledWith("u1")
  })

  it("supports side-by-side comparison using arbitrary thread selectors", async () => {
    state.messages = [
      {
        id: "u1",
        role: "user",
        content: "How did Q1 perform?",
        timestamp: "2026-02-18T08:00:00.000Z",
      },
      {
        id: "a1",
        role: "assistant",
        content: "Q1 increased by 12% [1].",
        timestamp: "2026-02-18T08:00:03.000Z",
      },
      {
        id: "u2",
        role: "user",
        content: "How did Q2 perform?",
        timestamp: "2026-02-18T08:01:00.000Z",
      },
      {
        id: "a2",
        role: "assistant",
        content: "Q2 increased by 9% [2].",
        timestamp: "2026-02-18T08:01:03.000Z",
      },
    ]
    state.searchHistory = [
      {
        id: "history-1",
        query: "Historical baseline thread",
        timestamp: "2026-02-17T10:00:00.000Z",
        conversationId: "thread-history",
      },
    ]
    fetchWithAuthMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [
        {
          id: "h-u1",
          role: "user",
          content: "How did Q4 perform?",
          created_at: "2026-02-17T08:00:00.000Z",
        },
        {
          id: "h-a1",
          role: "assistant",
          content: "Q4 increased by 6% [3].",
          created_at: "2026-02-17T08:00:03.000Z",
        },
      ],
      text: async () => "",
    })

    render(<ConversationThread />)

    await userEvent.click(screen.getByRole("button", { name: "Compare turns" }))
    await userEvent.selectOptions(
      screen.getByLabelText("Right thread"),
      "thread-history"
    )

    await waitFor(() =>
      expect(fetchWithAuthMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/chat/conversations/thread-history/messages-with-context")
      )
    )

    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: "Side-by-side query comparison" })
      ).toBeInTheDocument()
    )
    expect(screen.getAllByText("How did Q1 perform?").length).toBeGreaterThan(0)
    expect(screen.getAllByText("How did Q4 perform?").length).toBeGreaterThan(0)
  })
})
