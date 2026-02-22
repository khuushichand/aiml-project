import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SourceList } from "../SourceList"

const submitExplicitFeedbackMock = vi.fn()
const messageOpenMock = vi.fn()
const trackMetricMock = vi.fn()

const state = {
  results: [
    {
      id: "doc-1",
      content: "Relevant chunk content",
      metadata: {
        title: "Source A",
        chunk_id: "chunk-1",
        source_type: "media_db",
      },
      score: 0.91,
    },
  ] as Array<Record<string, any>>,
  citations: [{ index: 1 }] as Array<{ index: number }>,
  focusedSourceIndex: null as number | null,
  focusSource: vi.fn(),
  setQuery: vi.fn(),
  query: "How is revenue trending?",
  currentThreadId: "thread-feedback",
  messages: [{ id: "assistant-2", role: "assistant" }] as Array<{
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
  getFeedbackSessionId: () => "session-qa",
  submitExplicitFeedback: (...args: unknown[]) => submitExplicitFeedbackMock(...args),
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: messageOpenMock,
  }),
}))

vi.mock("@/utils/knowledge-qa-search-metrics", () => ({
  trackKnowledgeQaSearchMetric: (...args: unknown[]) => trackMetricMock(...args),
}))

describe("SourceList source feedback", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    submitExplicitFeedbackMock.mockResolvedValue({ ok: true })
    trackMetricMock.mockResolvedValue(undefined)
  })

  it("submits per-source relevance feedback with document and chunk ids", async () => {
    render(<SourceList />)

    fireEvent.click(screen.getByRole("button", { name: "Yes" }))

    await waitFor(() => expect(submitExplicitFeedbackMock).toHaveBeenCalledTimes(1))
    expect(submitExplicitFeedbackMock).toHaveBeenCalledWith(
      expect.objectContaining({
        conversation_id: "thread-feedback",
        message_id: "assistant-2",
        query: "How is revenue trending?",
        feedback_type: "relevance",
        relevance_score: 5,
        document_ids: ["doc-1"],
        chunk_ids: ["chunk-1"],
      })
    )
    expect(trackMetricMock).toHaveBeenCalledWith({
      type: "source_feedback_submit",
      relevant: true,
    })
  })

  it("shows retry action when source feedback submission fails", async () => {
    submitExplicitFeedbackMock.mockRejectedValueOnce(new Error("offline"))
    submitExplicitFeedbackMock.mockResolvedValueOnce({ ok: true })

    render(<SourceList />)

    fireEvent.click(screen.getByRole("button", { name: "No" }))

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Retry feedback" })).toBeInTheDocument()
    )

    fireEvent.click(screen.getByRole("button", { name: "Retry feedback" }))

    await waitFor(() => expect(submitExplicitFeedbackMock).toHaveBeenCalledTimes(2))
  })
})
