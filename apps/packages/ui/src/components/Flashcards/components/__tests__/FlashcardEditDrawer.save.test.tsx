import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { FlashcardEditDrawer } from "../FlashcardEditDrawer"
import type { Flashcard } from "@/services/flashcards"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
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

const sampleCard: Flashcard = {
  uuid: "card-1",
  deck_id: 1,
  front: "Front text",
  back: "Back text",
  notes: null,
  extra: null,
  is_cloze: false,
  tags: [],
  ef: 2.5,
  interval_days: 0,
  repetitions: 0,
  lapses: 0,
  due_at: null,
  last_reviewed_at: null,
  last_modified: null,
  deleted: false,
  client_id: "1",
  version: 3,
  model_type: "basic",
  reverse: false
}

describe("FlashcardEditDrawer save handling", () => {
  it("awaits async save callback and handles save errors", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("save failed"))
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined)

    render(
      <FlashcardEditDrawer
        open
        onClose={vi.fn()}
        card={sampleCard}
        onSave={onSave}
        onDelete={vi.fn()}
        decks={[
          {
            id: 1,
            name: "Deck 1",
            description: null,
            deleted: false,
            client_id: "1",
            version: 1
          }
        ]}
      />
    )

    await waitFor(() => {
      expect(screen.getByDisplayValue("Front text")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith("Save error:", expect.any(Error))
    })

    consoleErrorSpy.mockRestore()
  })
})
