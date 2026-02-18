import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ExportDialog } from "../ExportDialog"

const { messageOpenMock, createNoteMock } = vi.hoisted(() => ({
  messageOpenMock: vi.fn(),
  createNoteMock: vi.fn(),
}))
const state = {
  messages: [] as Array<{ role: string; content: string }>,
  currentThreadId: "thread-1" as string | null,
  results: [] as Array<{ id: string }>,
  answer: "Test answer" as string | null,
  query: "What does this source say?"
}

vi.mock("../KnowledgeQAProvider", () => ({
  useKnowledgeQA: () => ({
    messages: state.messages,
    currentThreadId: state.currentThreadId,
    results: state.results,
    answer: state.answer,
    query: state.query
  })
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    open: messageOpenMock,
  }),
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    createNote: createNoteMock,
  },
}))

describe("ExportDialog accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal("fetch", vi.fn())
    createNoteMock.mockResolvedValue({ id: 1 })
    state.messages = []
    state.currentThreadId = "thread-1"
    state.results = []
    state.answer = "Test answer"
    state.query = "What does this source say?"
  })

  it("exposes modal dialog semantics", () => {
    render(<ExportDialog open onClose={vi.fn()} />)

    const dialog = screen.getByRole("dialog", { name: "Export Conversation" })
    expect(dialog).toHaveAttribute("aria-modal", "true")
    expect(dialog).toHaveAttribute("aria-labelledby", "export-dialog-title")
    expect(screen.getByText("Export Conversation")).toHaveAttribute(
      "id",
      "export-dialog-title"
    )
  })

  it("traps keyboard focus and closes on Escape", async () => {
    const onClose = vi.fn()
    render(<ExportDialog open onClose={onClose} />)

    const closeButton = screen.getByRole("button", {
      name: "Close export dialog"
    })
    const exportButton = screen.getByRole("button", { name: "Export" })

    await waitFor(() => expect(closeButton).toHaveFocus())

    exportButton.focus()
    fireEvent.keyDown(document, { key: "Tab" })
    expect(closeButton).toHaveFocus()

    closeButton.focus()
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true })
    expect(exportButton).toHaveFocus()

    fireEvent.keyDown(document, { key: "Escape" })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("shows actionable error feedback when chatbook export fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => "thread not found",
      })
    )

    render(<ExportDialog open onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: /Chatbook/i }))
    fireEvent.click(screen.getByRole("button", { name: "Export" }))

    await waitFor(() =>
      expect(messageOpenMock).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
        })
      )
    )

    expect(screen.getByText(/Chatbook export failed/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry export" })).toBeInTheDocument()
  })

  it("shows citation transparency guidance and staged share-link control", () => {
    render(<ExportDialog open onClose={vi.fn()} />)

    expect(
      screen.getByText(/Citation formatting is approximate/i)
    ).toBeInTheDocument()

    const shareButton = screen.getByRole("button", {
      name: "Copy thread link (coming soon)"
    })
    expect(shareButton).toBeDisabled()
    expect(
      screen.getByText(/staged behind server access controls/i)
    ).toBeInTheDocument()
  })

  it("saves the active conversation to Notes from workflow actions", async () => {
    state.results = [
      {
        id: "source-1",
        content: "Important excerpt content",
        metadata: {
          title: "Source A",
          url: "https://example.com/source-a",
        },
      } as any,
    ]

    render(<ExportDialog open onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: "Save to Notes" }))

    await waitFor(() => expect(createNoteMock).toHaveBeenCalledTimes(1))

    const [noteContent, noteMetadata] = createNoteMock.mock.calls[0]
    expect(noteContent).toContain("# Knowledge QA Export")
    expect(noteContent).toContain("## Bibliography")
    expect(noteMetadata).toEqual(
      expect.objectContaining({
        title: expect.stringContaining("Knowledge QA:"),
        metadata: expect.objectContaining({
          origin: "knowledge_qa",
          source: "knowledge_export",
          thread_id: "thread-1",
        }),
      })
    )
    expect(messageOpenMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "success",
        content: "Saved to Notes.",
      })
    )
  })

  it("shows a user-visible error when Save to Notes fails", async () => {
    createNoteMock.mockRejectedValueOnce(new Error("notes backend unavailable"))

    render(<ExportDialog open onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: "Save to Notes" }))

    await waitFor(() =>
      expect(messageOpenMock).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          content: expect.stringContaining("Failed to save to Notes."),
        })
      )
    )
  })

  it("preserves format defaults and preview copy feedback behavior", async () => {
    state.answer = "A".repeat(2205)
    Object.defineProperty(globalThis.navigator, "clipboard", {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
      configurable: true,
    })

    render(<ExportDialog open onClose={vi.fn()} />)

    expect(
      screen.getByRole("button", { name: /Markdown/i })
    ).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByLabelText("Source excerpts")).toBeChecked()
    expect(screen.getByLabelText("Settings snapshot")).not.toBeChecked()

    fireEvent.click(screen.getByRole("button", { name: "Export" }))

    await waitFor(() => expect(screen.getByText("Preview")).toBeInTheDocument())
    expect(screen.getByText(/\.\.\. \(truncated\)/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /^Copy$/ }))

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument()
    )
  })
})
