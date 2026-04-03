import { fireEvent, render, screen, waitFor, act } from "@testing-library/react"
import { beforeEach, describe, expect, afterEach, it, vi } from "vitest"
import { FlashcardDeckReferenceSection } from "../FlashcardDeckReferenceSection"
import {
  useFlashcardDeckRecentCardsQuery,
  useFlashcardDeckSearchQuery
} from "../../hooks"

vi.mock("../../hooks", () => ({
  useFlashcardDeckRecentCardsQuery: vi.fn(),
  useFlashcardDeckSearchQuery: vi.fn()
}))

vi.mock("../MarkdownWithBoundary", () => ({
  MarkdownWithBoundary: ({ content }: { content: string }) => <div>{content}</div>
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    }))
  })
}

type MockFlashcard = {
  uuid: string
  deck_id: number
  front: string
  back: string
  is_cloze: boolean
  tags: string[]
  ef: number
  interval_days: number
  repetitions: number
  lapses: number
  queue_state: "new"
  deleted: boolean
  client_id: string
  version: number
  model_type: "basic"
  reverse: boolean
}

const makeCard = (overrides: Partial<MockFlashcard> = {}): MockFlashcard => ({
  uuid: "card-1",
  deck_id: 1,
  front: "Front 1",
  back: "Back 1",
  is_cloze: false,
  tags: [],
  ef: 2.5,
  interval_days: 1,
  repetitions: 0,
  lapses: 0,
  queue_state: "new",
  deleted: false,
  client_id: "test",
  version: 1,
  model_type: "basic",
  reverse: false,
  ...overrides
})

describe("FlashcardDeckReferenceSection", () => {
  const recentRefetch = vi.fn()
  const searchRefetch = vi.fn()
  let recentState: Record<string, unknown>
  let searchState: Record<string, unknown>

  beforeEach(() => {
    vi.clearAllMocks()
    recentRefetch.mockReset()
    searchRefetch.mockReset()
    recentState = {
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: recentRefetch
    }
    searchState = {
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: searchRefetch
    }
    vi.mocked(useFlashcardDeckRecentCardsQuery).mockImplementation(() => recentState as any)
    vi.mocked(useFlashcardDeckSearchQuery).mockImplementation(() => searchState as any)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders nothing when deckId is null", () => {
    const { container } = render(
      <FlashcardDeckReferenceSection open deckId={null} deckName="Biology" />
    )

    expect(container).toBeEmptyDOMElement()
  })

  it("is collapsed by default and keeps the body out of the DOM until expanded", async () => {
    recentState = {
      ...recentState,
      data: [makeCard()]
    }

    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)

    expect(screen.queryByPlaceholderText("Search this deck")).not.toBeInTheDocument()
    expect(screen.queryByText("Front 1")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    expect(screen.getByText("Existing cards in this deck")).toBeInTheDocument()
    expect(await screen.findByText("Front 1")).toBeInTheDocument()
    expect(screen.getByText("Back 1")).toBeInTheDocument()
  })

  it("renders both front and back for each recent reference card", async () => {
    recentState = {
      ...recentState,
      data: [makeCard({ uuid: "card-1", front: "Alpha", back: "Beta" }), makeCard({ uuid: "card-2", front: "Gamma", back: "Delta" })]
    }

    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    expect(await screen.findByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
    expect(screen.getByText("Gamma")).toBeInTheDocument()
    expect(screen.getByText("Delta")).toBeInTheDocument()
  })

  it("shows a compact message when the recent list is empty", async () => {
    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    expect(await screen.findByText("No recent cards in this deck yet.")).toBeInTheDocument()
  })

  it("waits 300ms before sending the debounced search term to the search hook", async () => {
    vi.useFakeTimers()
    recentState = {
      ...recentState,
      data: [makeCard()]
    }

    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    const input = screen.getByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "mitochondria" } })

    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[0]
    ).toEqual(expect.objectContaining({ query: "" }))

    await act(async () => {
      vi.advanceTimersByTime(299)
    })

    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.some(
        ([params]) => (params as { query: string }).query === "mitochondria"
      )
    ).toBe(false)

    await act(async () => {
      vi.advanceTimersByTime(1)
    })

    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[0]
    ).toEqual(expect.objectContaining({ query: "mitochondria" }))
    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[0]
    ).not.toHaveProperty("limit")
  })

  it("keeps queries disabled for a new deck until it is re-expanded", async () => {
    recentState = {
      ...recentState,
      data: [makeCard({ uuid: "deck-a-1", front: "Deck A front", back: "Deck A back" })]
    }

    const { rerender } = render(
      <FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />
    )
    fireEvent.click(screen.getByRole("button", { name: /existing cards in this deck/i }))

    const input = await screen.findByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "alpha" } })

    expect(
      screen.getByPlaceholderText("Search this deck")
    ).toBeInTheDocument()

    rerender(<FlashcardDeckReferenceSection open deckId={2} deckName="Physics" />)

    expect(
      vi.mocked(useFlashcardDeckRecentCardsQuery).mock.calls.at(-1)?.[1]
    ).toEqual(expect.objectContaining({ enabled: false }))
    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[1]
    ).toEqual(expect.objectContaining({ enabled: false }))

    fireEvent.click(screen.getByRole("button", { name: /existing cards in this deck/i }))
  })

  it("treats whitespace-only search as inactive", async () => {
    vi.useFakeTimers()
    recentState = {
      ...recentState,
      data: [makeCard()]
    }

    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)
    fireEvent.click(screen.getByRole("button", { name: /existing cards in this deck/i }))

    const input = screen.getByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "   " } })

    await act(async () => {
      vi.advanceTimersByTime(300)
    })

    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[0]
    ).toEqual(expect.objectContaining({ query: "" }))
    expect(
      vi.mocked(useFlashcardDeckSearchQuery).mock.calls.at(-1)?.[1]
    ).toEqual(expect.objectContaining({ enabled: false }))
    expect(screen.queryByText("No matching cards.")).not.toBeInTheDocument()
  })

  it("shows compact inline messages for empty recent, no-results, and error states", async () => {
    recentState = {
      ...recentState,
      data: [makeCard({ uuid: "recent-1", front: "Recent front", back: "Recent back" })]
    }
    const { rerender } = render(
      <FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />
    )
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    searchState = {
      ...searchState,
      data: [
        makeCard({ uuid: "match-1", front: "Matched front", back: "Matched back" })
      ]
    }

    const input = await screen.findByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "matching-term" } })

    await waitFor(() => {
      expect(screen.getByText("Recent front")).toBeInTheDocument()
      expect(screen.getByText("Recent back")).toBeInTheDocument()
      expect(screen.getByText("Matched front")).toBeInTheDocument()
      expect(screen.getByText("Matched back")).toBeInTheDocument()
    })

    searchState = {
      ...searchState,
      data: []
    }

    fireEvent.change(input, { target: { value: "missing-term" } })

    await waitFor(() => {
      expect(screen.getByText("No matching cards.")).toBeInTheDocument()
      expect(screen.getByText("Recent front")).toBeInTheDocument()
      expect(screen.getByText("Recent back")).toBeInTheDocument()
    })

    recentState = {
      ...recentState,
      isError: true,
      error: new Error("recent failed")
    }

    rerender(<FlashcardDeckReferenceSection open deckId={2} deckName="Physics" />)
    fireEvent.click(screen.getByRole("button", { name: /physics/i }))

    expect(await screen.findByText("Unable to load reference cards.")).toBeInTheDocument()
  })

  it("wires the retry button to the recent query refetch", async () => {
    recentState = {
      ...recentState,
      isError: true,
      error: new Error("recent failed")
    }

    render(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }))

    expect(recentRefetch).toHaveBeenCalledTimes(1)
  })

  it("clears the rendered search input when deckId changes", async () => {
    recentState = {
      ...recentState,
      data: [makeCard()]
    }

    const { rerender } = render(
      <FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />
    )
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    const input = await screen.findByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "mitochondria" } })

    expect((screen.getByPlaceholderText("Search this deck") as HTMLInputElement).value).toBe(
      "mitochondria"
    )

    rerender(<FlashcardDeckReferenceSection open deckId={2} deckName="Physics" />)
    fireEvent.click(screen.getByRole("button", { name: /physics/i }))

    await waitFor(() => {
      expect((screen.getByPlaceholderText("Search this deck") as HTMLInputElement).value).toBe(
        ""
      )
    })
  })

  it("clears the rendered search input when the drawer closes and reopens", async () => {
    recentState = {
      ...recentState,
      data: [makeCard()]
    }

    const { rerender } = render(
      <FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />
    )
    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    const input = await screen.findByPlaceholderText("Search this deck")
    fireEvent.change(input, { target: { value: "mitochondria" } })

    rerender(<FlashcardDeckReferenceSection open={false} deckId={1} deckName="Biology" />)
    rerender(<FlashcardDeckReferenceSection open deckId={1} deckName="Biology" />)

    fireEvent.click(screen.getByRole("button", { name: /biology/i }))

    await waitFor(() => {
      expect((screen.getByPlaceholderText("Search this deck") as HTMLInputElement).value).toBe(
        ""
      )
    })
  })
})
