import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useCollectionsStore } from "@/store/collections"
import { ReadingItemDetail } from "../ReadingItemDetail"

const apiMock = vi.hoisted(() => ({
  getReadingItem: vi.fn(),
  getHighlights: vi.fn(),
  listReadingItemNoteLinks: vi.fn(),
  unlinkReadingItemNote: vi.fn(),
  updateReadingItem: vi.fn(),
  summarizeReadingItem: vi.fn(),
  generateReadingItemTts: vi.fn(),
  deleteReadingItem: vi.fn(),
  createHighlight: vi.fn(),
  updateHighlight: vi.fn(),
  deleteHighlight: vi.fn(),
  linkReadingItemToNote: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => apiMock
}))

describe("ReadingItemDetail linked notes panel", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (!window.matchMedia) {
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

    useCollectionsStore.getState().resetStore()
    useCollectionsStore.getState().openItemDetail("1")

    apiMock.getReadingItem.mockResolvedValue({
      id: "1",
      title: "Linked Notes Item",
      status: "saved",
      favorite: false,
      tags: [],
      notes: "",
      summary: null,
      domain: "example.org",
      url: "https://example.org",
      canonical_url: "https://example.org",
      archive_requested: false,
      has_archive_copy: false,
      last_fetch_error: null
    })
    apiMock.getHighlights.mockResolvedValue([])
    apiMock.listReadingItemNoteLinks.mockResolvedValue([
      {
        item_id: "1",
        note_id: "note-1",
        created_at: "2026-03-02T00:00:00Z"
      }
    ])
    apiMock.unlinkReadingItemNote.mockResolvedValue({ ok: true })
  })

  it("renders linked notes and supports unlink", async () => {
    render(<ReadingItemDetail />)

    fireEvent.click(await screen.findByRole("tab", { name: /Notes/i }))

    expect(await screen.findByText("Linked Notes")).toBeTruthy()
    expect(await screen.findByText("note-1")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Unlink/i }))

    await waitFor(() => {
      expect(apiMock.unlinkReadingItemNote).toHaveBeenCalledWith("1", "note-1")
    })
  })
})
