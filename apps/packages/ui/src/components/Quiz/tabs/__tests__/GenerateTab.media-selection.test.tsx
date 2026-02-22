import React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { GenerateTab } from "../GenerateTab"
import { useGenerateQuizMutation } from "../../hooks"
import { tldwClient } from "@/services/tldw"
import { createDeck, createFlashcard, generateFlashcards } from "@/services/flashcards"

const navigationMocks = {
  navigate: vi.fn()
}

const interpolate = (template: string, values: Record<string, unknown> | undefined) => {
  return template.replace(/\{\{\s*([^\s}]+)\s*\}\}/g, (_, key: string) => {
    const value = values?.[key]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      const defaultValue = defaultValueOrOptions?.defaultValue
      if (typeof defaultValue === "string") {
        return interpolate(defaultValue, defaultValueOrOptions)
      }
      return key
    }
  })
}))

vi.mock("../../hooks", () => ({
  useGenerateQuizMutation: vi.fn()
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigationMocks.navigate
}))

vi.mock("@/services/tldw", () => ({
  tldwClient: {
    listMedia: vi.fn(),
    searchMedia: vi.fn(),
    getMediaDetails: vi.fn()
  }
}))

vi.mock("@/services/flashcards", () => ({
  generateFlashcards: vi.fn(),
  createDeck: vi.fn(),
  createFlashcard: vi.fn()
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("GenerateTab scalable media selection and generation flow", () => {
  const renderWithQueryClient = ({
    onNavigateToTake,
    onNavigateToManage
  }: {
    onNavigateToTake?: (intent?: any) => void
    onNavigateToManage?: () => void
  } = {}) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    })

    return render(
      <QueryClientProvider client={queryClient}>
        <GenerateTab onNavigateToTake={onNavigateToTake ?? (() => {})} onNavigateToManage={onNavigateToManage} />
      </QueryClientProvider>
    )
  }

  beforeEach(() => {
    vi.clearAllMocks()
    navigationMocks.navigate.mockReset()

    vi.mocked(tldwClient.getMediaDetails).mockResolvedValue({} as any)
    vi.mocked(generateFlashcards).mockResolvedValue({
      flashcards: [],
      count: 0
    } as any)
    vi.mocked(createDeck).mockResolvedValue({
      id: 100,
      name: "Generated Deck"
    } as any)
    vi.mocked(createFlashcard).mockResolvedValue({
      uuid: "card-1"
    } as any)

    vi.mocked(useGenerateQuizMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({
        quiz: { id: 1, name: "Generated Quiz" },
        questions: [{ id: 1 }]
      })),
      isPending: false
    } as any)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("loads media in pages and keeps selection stable while loading more", async () => {
    vi.mocked(tldwClient.listMedia)
      .mockResolvedValueOnce({
        items: [
          { id: 1, title: "Doc 1", type: "pdf" },
          { id: 2, title: "Doc 2", type: "pdf" }
        ],
        pagination: { total_items: 3 }
      } as any)
      .mockResolvedValueOnce({
        items: [{ id: 3, title: "Doc 3", type: "pdf" }],
        pagination: { total_items: 3 }
      } as any)

    renderWithQueryClient()

    await waitFor(() => {
      expect(screen.getByText("Showing 2 of 3 media items")).toBeInTheDocument()
    })

    const combobox = screen.getAllByRole("combobox")[0]
    fireEvent.mouseDown(combobox)
    fireEvent.click(await screen.findByText("Doc 1 (pdf)"))

    const generateButton = screen.getByRole("button", { name: /Generate Quiz/i })
    expect(generateButton).not.toBeDisabled()

    fireEvent.click(screen.getByTestId("generate-media-load-more"))

    await waitFor(() => {
      expect(screen.getByText("3 media items available")).toBeInTheDocument()
    })

    expect(generateButton).not.toBeDisabled()
    expect(tldwClient.listMedia).toHaveBeenNthCalledWith(1, {
      page: 1,
      results_per_page: 50
    })
    expect(tldwClient.listMedia).toHaveBeenNthCalledWith(2, {
      page: 2,
      results_per_page: 50
    })
  }, 20000)

  it("uses server-side media search when search term is entered", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 1, title: "Doc 1", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)

    vi.mocked(tldwClient.searchMedia).mockResolvedValue({
      items: [{ id: 9, title: "Cell Notes", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)

    renderWithQueryClient()

    await waitFor(() => {
      expect(tldwClient.listMedia).toHaveBeenCalledWith({
        page: 1,
        results_per_page: 50
      })
    })

    const combobox = screen.getAllByRole("combobox")[0]
    fireEvent.mouseDown(combobox)
    fireEvent.change(combobox, { target: { value: "cell" } })

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 400))
    })

    await waitFor(() => {
      expect(tldwClient.searchMedia).toHaveBeenCalledWith(
        { query: "cell" },
        { page: 1, results_per_page: 50 }
      )
    })
  }, 20000)

  it("shows preview-first flow and passes focus topics in generation payload", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 10, title: "Biology Notes", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)

    const onNavigateToTake = vi.fn()
    const mutateAsync = vi.fn(async () => ({
      quiz: { id: 42, name: "Cell Biology Checkpoint" },
      questions: [{ id: 1 }, { id: 2 }, { id: 3 }]
    }))

    vi.mocked(useGenerateQuizMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)

    renderWithQueryClient({ onNavigateToTake })

    await waitFor(() => {
      expect(screen.getByText("1 media items available")).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getAllByRole("combobox")[0])
    fireEvent.click(await screen.findByText("Biology Notes (pdf)"))

    const allComboboxes = screen.getAllByRole("combobox")
    const focusInput = allComboboxes[allComboboxes.length - 1]
    fireEvent.mouseDown(focusInput)
    fireEvent.change(focusInput, { target: { value: "cell membrane" } })
    fireEvent.keyDown(focusInput, { key: "Enter", code: "Enter" })
    fireEvent.change(focusInput, { target: { value: "mitosis" } })
    fireEvent.keyDown(focusInput, { key: "Enter", code: "Enter" })

    fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))

    await waitFor(() => {
      expect(screen.getByTestId("generate-preview-card")).toBeInTheDocument()
    })

    expect(onNavigateToTake).not.toHaveBeenCalled()
    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        request: expect.objectContaining({
          media_id: 10,
          focus_topics: ["cell membrane", "mitosis"]
        }),
        signal: expect.any(AbortSignal)
      })
    )

    fireEvent.click(screen.getByRole("button", { name: /Take Quiz/i }))
    expect(onNavigateToTake).toHaveBeenCalledWith({
      startQuizId: 42,
      highlightQuizId: 42,
      sourceTab: "generate"
    })
  }, 20000)

  it("supports canceling in-flight generation and does not navigate", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 5, title: "Long Transcript", type: "audio" }],
      pagination: { total_items: 1 }
    } as any)

    const onNavigateToTake = vi.fn()
    const mutateAsync = vi.fn(({ signal }: { signal?: AbortSignal }) =>
      new Promise((resolve, reject) => {
        signal?.addEventListener(
          "abort",
          () => {
            const abortError = new Error("aborted")
            abortError.name = "AbortError"
            reject(abortError)
          },
          { once: true }
        )
      })
    )

    vi.mocked(useGenerateQuizMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)

    renderWithQueryClient({ onNavigateToTake })

    await waitFor(() => {
      expect(screen.getByText("1 media items available")).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getAllByRole("combobox")[0])
    fireEvent.click(await screen.findByText("Long Transcript (audio)"))

    fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))

    const cancelButton = await screen.findByTestId("generate-cancel-button")
    fireEvent.click(cancelButton)

    await waitFor(() => {
      expect(screen.queryByTestId("generate-cancel-button")).not.toBeInTheDocument()
    })

    expect(onNavigateToTake).not.toHaveBeenCalled()
    expect(mutateAsync).toHaveBeenCalledTimes(1)
    const mutationCall = mutateAsync.mock.calls[0]?.[0]
    expect(mutationCall?.signal).toBeInstanceOf(AbortSignal)
    expect(mutationCall?.signal?.aborted).toBe(true)
  }, 20000)

  it("shows question-count recommendation guidance tied to selected media length", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 21, title: "Lengthy Source", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)
    vi.mocked(tldwClient.getMediaDetails).mockResolvedValue({
      content: { word_count: 2400 }
    } as any)

    renderWithQueryClient()

    await waitFor(() => {
      expect(screen.getByText("1 media items available")).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getAllByRole("combobox")[0])
    fireEvent.click(await screen.findByText("Lengthy Source (pdf)"))

    await waitFor(() => {
      expect(screen.getByTestId("generate-question-count-guidance")).toHaveTextContent(
        "Estimated source length: ~2,400 words. Recommended: 10-20 questions."
      )
    })

    expect(screen.getByTestId("generate-difficulty-guidance")).toHaveTextContent(
      "Easy: Basic recall and straightforward definitions."
    )
  }, 20000)

  it("can generate quiz and flashcards together and expose both destination links", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 77, title: "Biology Source", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)
    vi.mocked(tldwClient.getMediaDetails).mockImplementation(async (_mediaId, options) => {
      if (options?.include_content) {
        return {
          content: {
            text: "Mitosis and meiosis are core processes in cell division."
          }
        } as any
      }
      return { content: { word_count: 1200 } } as any
    })
    vi.mocked(generateFlashcards).mockResolvedValue({
      flashcards: [
        { front: "Mitosis", back: "Cell division for growth and repair" },
        { front: "Meiosis", back: "Cell division creating gametes" }
      ],
      count: 2
    } as any)
    vi.mocked(createDeck).mockResolvedValue({
      id: 55,
      name: "Biology Source - Flashcards"
    } as any)
    vi.mocked(createFlashcard).mockResolvedValue({
      uuid: "card-1"
    } as any)

    const mutateAsync = vi.fn(async () => ({
      quiz: { id: 99, name: "Biology Mastery" },
      questions: [{ id: 1 }, { id: 2 }]
    }))
    vi.mocked(useGenerateQuizMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)

    renderWithQueryClient()

    await waitFor(() => {
      expect(screen.getByText("1 media items available")).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getAllByRole("combobox")[0])
    fireEvent.click(await screen.findByText("Biology Source (pdf)"))
    fireEvent.click(screen.getByTestId("generate-study-materials-toggle"))
    fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))

    await waitFor(() => {
      expect(screen.getByTestId("generate-preview-card")).toBeInTheDocument()
      expect(screen.getByTestId("generate-study-materials-summary")).toBeInTheDocument()
    })

    expect(generateFlashcards).toHaveBeenCalledWith(
      expect.objectContaining({
        num_cards: 10,
        difficulty: "mixed"
      })
    )
    expect(createDeck).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Biology Mastery - Flashcards"
      })
    )
    expect(createFlashcard).toHaveBeenCalledTimes(2)

    fireEvent.click(screen.getByTestId("generate-open-flashcards-button"))
    expect(navigationMocks.navigate).toHaveBeenCalledWith(
      expect.stringContaining("/flashcards?tab=review&study_source=quiz&quiz_id=99&deck_id=55")
    )
  }, 20000)

  it("surfaces fallback handoff when combined flashcard generation cannot extract source content", async () => {
    vi.mocked(tldwClient.listMedia).mockResolvedValue({
      items: [{ id: 88, title: "Sparse Source", type: "pdf" }],
      pagination: { total_items: 1 }
    } as any)
    vi.mocked(tldwClient.getMediaDetails).mockImplementation(async (_mediaId, options) => {
      if (options?.include_content) {
        return {} as any
      }
      return { content: { word_count: 400 } } as any
    })
    vi.mocked(useGenerateQuizMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({
        quiz: { id: 33, name: "Sparse Quiz" },
        questions: [{ id: 1 }]
      })),
      isPending: false
    } as any)

    renderWithQueryClient()

    await waitFor(() => {
      expect(screen.getByText("1 media items available")).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getAllByRole("combobox")[0])
    fireEvent.click(await screen.findByText("Sparse Source (pdf)"))
    fireEvent.click(screen.getByTestId("generate-study-materials-toggle"))
    fireEvent.click(screen.getByRole("button", { name: /Generate Quiz/i }))

    await waitFor(() => {
      expect(screen.getByTestId("generate-preview-card")).toBeInTheDocument()
      expect(screen.getByTestId("generate-study-materials-summary")).toBeInTheDocument()
    })

    expect(generateFlashcards).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId("generate-continue-flashcards-button"))
    expect(navigationMocks.navigate).toHaveBeenCalledWith("/flashcards?tab=importExport")
  }, 20000)
})
