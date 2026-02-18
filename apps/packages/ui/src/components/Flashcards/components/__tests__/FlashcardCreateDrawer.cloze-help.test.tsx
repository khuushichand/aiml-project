import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { FlashcardCreateDrawer } from "../FlashcardCreateDrawer"
import { useCreateFlashcardMutation, useCreateDeckMutation, useDecksQuery } from "../../hooks"
import { FLASHCARDS_DRAWER_WIDTH_PX } from "../../constants"

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
      if (defaultValueOrOptions?.defaultValue) {
        return defaultValueOrOptions.defaultValue.replace(
          /\{\{(\w+)\}\}/g,
          (_match, token: string) =>
            String((defaultValueOrOptions as Record<string, unknown>)[token] ?? `{{${token}}}`)
        )
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useAntdMessage", () => ({
  useAntdMessage: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
    open: vi.fn(),
    destroy: vi.fn()
  })
}))

vi.mock("../../hooks", () => ({
  useDecksQuery: vi.fn(),
  useCreateFlashcardMutation: vi.fn(),
  useCreateDeckMutation: vi.fn(),
  useDebouncedFormField: vi.fn(() => undefined)
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

describe("FlashcardCreateDrawer cloze helper and validation", () => {
  const mutateAsync = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDecksQuery).mockReturnValue({
      data: [
        {
          id: 1,
          name: "Biology",
          description: null,
          deleted: false,
          client_id: "test",
          version: 1
        }
      ],
      isLoading: false
    } as any)
    vi.mocked(useCreateFlashcardMutation).mockReturnValue({
      mutateAsync,
      isPending: false
    } as any)
    vi.mocked(useCreateDeckMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)
  })

  it("shows template guidance and blocks invalid cloze front syntax", async () => {
    render(
      <FlashcardCreateDrawer
        open
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    const wrapper = document.querySelector(".ant-drawer-content-wrapper") as HTMLElement | null
    expect(wrapper?.style.width).toBe(`${FLASHCARDS_DRAWER_WIDTH_PX}px`)

    expect(
      screen.getByText(
        "Choose Basic for direct question and answer cards (facts, definitions, short prompts)."
      )
    ).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByLabelText("Card template"))
    fireEvent.click(screen.getByText("Cloze (Fill in the blank)"))

    await waitFor(() => {
      expect(
        screen.getByText(
          "Choose Cloze when you want to hide key words inside a sentence or paragraph."
        )
      ).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(
        screen.getByText("Cloze syntax: add at least one deletion like {{c1::answer}} in Front text.")
      ).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText("Question or prompt..."), {
      target: { value: "This front has no cloze pattern" }
    })
    fireEvent.change(screen.getByPlaceholderText("Answer..."), {
      target: { value: "Back content" }
    })

    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(
        screen.getByText(
          "For Cloze cards, include at least one deletion like {{c1::answer}}."
        )
      ).toBeInTheDocument()
    })
    expect(mutateAsync).not.toHaveBeenCalled()
  })
})
