import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AnswerPanel } from "../AnswerPanel"

const submitExplicitFeedbackMock = vi.fn()
const messageOpenMock = vi.fn()
const navigateMock = vi.fn()
const trackMetricMock = vi.fn()

const state = {
  answer: null as string | null,
  citations: [] as Array<{ index: number }>,
  isSearching: false,
  error: null as string | null,
  results: [] as Array<{ id: string; metadata?: { title?: string } }>,
  setSettingsPanelOpen: vi.fn(),
  settings: {
    max_generation_tokens: 800,
  } as { max_generation_tokens: number },
  preset: "balanced" as "fast" | "balanced" | "thorough" | "custom",
  rerunWithTokenLimit: vi.fn(),
  searchDetails: null as
    | {
        tokensUsed?: number | null
        estimatedCostUsd?: number | null
        webFallbackTriggered?: boolean
        webFallbackEngine?: string | null
      }
    | null,
  query: "What does this source say?",
  currentThreadId: "thread-1" as string | null,
  messages: [] as Array<{ id: string; role: string }>,
  scrollToSource: vi.fn(),
}

vi.mock("@/services/feedback", () => ({
  getFeedbackSessionId: () => "session-1",
  submitExplicitFeedback: (...args: unknown[]) => submitExplicitFeedbackMock(...args),
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: messageOpenMock,
  }),
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom")
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

vi.mock("@/utils/workspace-playground-prefill", () => ({
  buildKnowledgeQaWorkspacePrefill: vi.fn((payload) => payload),
  queueWorkspacePlaygroundPrefill: vi.fn().mockResolvedValue(undefined),
}))

vi.mock("@/utils/knowledge-qa-search-metrics", () => ({
  trackKnowledgeQaSearchMetric: (...args: unknown[]) => trackMetricMock(...args),
}))

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    answer: state.answer,
    citations: state.citations,
    isSearching: state.isSearching,
    error: state.error,
    results: state.results,
    searchDetails: state.searchDetails,
    query: state.query,
    currentThreadId: state.currentThreadId,
    messages: state.messages,
    setSettingsPanelOpen: state.setSettingsPanelOpen,
    settings: state.settings,
    preset: state.preset,
    rerunWithTokenLimit: state.rerunWithTokenLimit,
    scrollToSource: state.scrollToSource,
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
    state.setSettingsPanelOpen = vi.fn()
    state.settings.max_generation_tokens = 800
    state.preset = "balanced"
    state.rerunWithTokenLimit = vi.fn().mockResolvedValue(undefined)
    state.searchDetails = null
    state.query = "What does this source say?"
    state.currentThreadId = "thread-1"
    state.messages = []
    submitExplicitFeedbackMock.mockResolvedValue({ ok: true })
    trackMetricMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.useRealTimers()
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
    fireEvent.click(screen.getByRole("button", { name: "Enable in Settings" }))
    expect(state.setSettingsPanelOpen).toHaveBeenCalledWith(true)
  })

  it("keeps citation jump interaction wired to source focus", () => {
    state.answer = "Use method [1] for better recall."
    state.citations = [{ index: 1 }]
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]

    render(<AnswerPanel />)
    const jumpButton = screen.getAllByRole("button", { name: "Jump to source 1" })[0]
    fireEvent.click(jumpButton)

    expect(state.scrollToSource).toHaveBeenCalledWith(0)
    expect(jumpButton.className).toContain("min-w-8")
    expect(jumpButton.className).toContain("h-8")
    expect(jumpButton.className).toContain("dark:text-slate-900")
  })

  it("collapses very long answers with a show-more toggle", () => {
    state.answer = Array.from({ length: 1005 })
      .map((_, index) => `word${index}`)
      .join(" ")
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]

    render(<AnswerPanel />)

    const content = screen.getByTestId("knowledge-answer-content")
    expect(content.className).toContain("max-h-[28rem]")
    expect(screen.getByRole("button", { name: "Show full answer" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Show full answer" }))
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument()
    expect(content.className).not.toContain("max-h-[28rem]")
  })

  it("shows token usage summary and sends answer feedback", async () => {
    state.answer = "Grounded answer"
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]
    state.searchDetails = { tokensUsed: 1234, estimatedCostUsd: 0.0042 }
    state.messages = [{ id: "assistant-1", role: "assistant" }]

    render(<AnswerPanel />)

    expect(screen.getByText(/Used ~1,234 tokens/)).toBeInTheDocument()
    expect(screen.getByText(/Estimated cost \$0.0042/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Helpful" }))

    await waitFor(() =>
      expect(submitExplicitFeedbackMock).toHaveBeenCalledWith(
        expect.objectContaining({
          conversation_id: "thread-1",
          message_id: "assistant-1",
          feedback_type: "helpful",
          helpful: true,
        })
      )
    )
    await waitFor(() =>
      expect(trackMetricMock).toHaveBeenCalledWith({
        type: "answer_feedback_submit",
        helpful: true,
      })
    )
  })

  it("renders markdown structures and keeps inline citation buttons accessible", () => {
    state.answer = [
      "Key points:",
      "",
      "- Item one",
      "- Item two",
      "",
      "```ts",
      "const value = 1",
      "```",
      "",
      "| Column | Value |",
      "| --- | --- |",
      "| A | 1 |",
      "",
      "Evidence [1]",
    ].join("\n")
    state.citations = [{ index: 1 }]
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]

    render(<AnswerPanel />)

    expect(screen.getByRole("list")).toBeInTheDocument()
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("const value = 1")).toBeInTheDocument()
    expect(
      screen.getByText(
        /This answer includes inline citation buttons\. Press Tab to move between citation controls and source links\./i
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId("knowledge-answer-content")).toHaveAttribute(
      "aria-describedby",
      "knowledge-answer-citation-guidance"
    )

    const inlineCitationButton = screen.getByTitle("Jump to source 1")
    expect(inlineCitationButton).toHaveAttribute("aria-label", "Jump to source 1")
    inlineCitationButton.focus()
    expect(document.activeElement).toBe(inlineCitationButton)

    fireEvent.click(inlineCitationButton)
    expect(state.scrollToSource).toHaveBeenCalledWith(0)
  })

  it("shows staged loading text with elapsed seconds", () => {
    vi.useFakeTimers()
    state.isSearching = true
    state.preset = "thorough"

    render(<AnswerPanel />)
    expect(screen.getByText(/Searching documents/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Thorough preset may take up to 30 seconds/i)
    ).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(6000)
    })
    expect(screen.getByText(/Reranking results/i)).toBeInTheDocument()
    expect(screen.getByText(/\(6s\)/)).toBeInTheDocument()
  })

  it("classifies timeout errors with targeted guidance", () => {
    state.error = "Search timed out. Try the Fast preset or reduce sources."

    render(<AnswerPanel />)

    expect(screen.getByText("Search timed out")).toBeInTheDocument()
    expect(
      screen.getByText("Try the Fast preset or reduce the scope of your query.")
    ).toBeInTheDocument()
  })

  it("shows web fallback indicator in answer header when triggered", () => {
    state.answer = "Answer with mixed sources"
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]
    state.searchDetails = {
      webFallbackTriggered: true,
      webFallbackEngine: "duckduckgo",
    }

    render(<AnswerPanel />)

    expect(screen.getByText("Includes web sources (duckduckgo)")).toBeInTheDocument()
  })

  it("copies the full answer with citations", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: { writeText },
    })
    state.answer = "Result with source [1]"
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]
    state.citations = [{ index: 1 }]

    render(<AnswerPanel />)

    fireEvent.click(screen.getByRole("button", { name: "Copy answer" }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("Result with source [1]"))
  })

  it("reruns with adjusted token limits from summarize/show-more controls", async () => {
    state.answer = "Long answer"
    state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]
    state.settings.max_generation_tokens = 1000

    render(<AnswerPanel />)

    fireEvent.click(screen.getByRole("button", { name: "Summarize" }))
    await waitFor(() => expect(state.rerunWithTokenLimit).toHaveBeenCalledWith(600))

    fireEvent.click(screen.getByRole("button", { name: "Show more" }))
    await waitFor(() => expect(state.rerunWithTokenLimit).toHaveBeenCalledWith(1500))
  })
})
