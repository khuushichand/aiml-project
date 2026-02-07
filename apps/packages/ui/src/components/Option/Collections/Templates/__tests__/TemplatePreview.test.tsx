import { describe, expect, it, beforeEach, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useCollectionsStore } from "@/store/collections"
import { TemplatePreview } from "../TemplatePreview"

const apiMock = vi.hoisted(() => ({
  getReadingList: vi.fn(),
  previewTemplate: vi.fn(),
  generateOutput: vi.fn(),
  downloadOutput: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) => {
  if (!values) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = values[token]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string } | Record<string, unknown>,
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return interpolate(fallbackOrOptions, maybeOptions)
      }
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        const maybeDefault = (fallbackOrOptions as { defaultValue?: string }).defaultValue
        if (typeof maybeDefault === "string") {
          return interpolate(maybeDefault, maybeOptions)
        }
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => apiMock
}))

describe("TemplatePreview", () => {
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
    apiMock.getReadingList.mockResolvedValue({
      items: [
        {
          id: "11",
          title: "Item A",
          tags: [],
          favorite: false
        }
      ],
      total: 1,
      page: 1,
      size: 50
    })
    apiMock.previewTemplate.mockResolvedValue({
      rendered: "Rendered preview body",
      format: "md"
    })
  })

  it("renders markdown preview after selecting an item", async () => {
    render(<TemplatePreview templateId="7" onClose={vi.fn()} />)

    await screen.findByText("Item A")
    fireEvent.click(screen.getByText("Item A"))
    fireEvent.click(screen.getByRole("button", { name: "Generate Preview" }))

    await screen.findByText("Rendered preview body")
    expect(apiMock.previewTemplate).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: "7"
      })
    )
    await waitFor(() => {
      const state = useCollectionsStore.getState()
      expect(state.selectedItemsForGeneration).toEqual(["11"])
    })
  })
})
