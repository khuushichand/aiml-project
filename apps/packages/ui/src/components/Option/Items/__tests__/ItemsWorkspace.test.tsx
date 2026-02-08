import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { ItemsWorkspace } from "../ItemsWorkspace"

const apiMock = vi.hoisted(() => ({
  getItems: vi.fn(),
  bulkUpdateItems: vi.fn(),
  getOutputTemplates: vi.fn(),
  generateOutput: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useTldwApiClient", () => ({
  useTldwApiClient: () => apiMock
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

describe("ItemsWorkspace", () => {
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

    apiMock.getItems.mockResolvedValue({
      items: [
        {
          id: "101",
          title: "Shared Item",
          tags: ["research"],
          type: "watchlist"
        }
      ],
      total: 1,
      page: 1,
      size: 25
    })
    apiMock.getOutputTemplates.mockResolvedValue({
      items: [{ id: "77", name: "Briefing", format: "md" }],
      total: 1
    })
    apiMock.generateOutput.mockResolvedValue({ id: "501" })
  })

  it("renders items from shared items endpoint", async () => {
    render(<ItemsWorkspace />)

    await waitFor(() => {
      expect(apiMock.getItems).toHaveBeenCalled()
    })
    expect(await screen.findByText("Shared Item")).toBeTruthy()
  })

  it("generates output from selected item ids", async () => {
    render(<ItemsWorkspace />)

    expect(await screen.findByText("Shared Item")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /Select/i }))
    fireEvent.click(screen.getByLabelText("Toggle selection for Shared Item"))
    fireEvent.click(screen.getByRole("button", { name: /Generate output/i }))

    await waitFor(() => {
      expect(apiMock.getOutputTemplates).toHaveBeenCalled()
    })

    const dialog = await screen.findByRole("dialog", {
      name: /Generate output for selected items/i
    })
    const modalGenerateButton = within(dialog).getByRole("button", {
      name: /^Generate output$/
    })
    fireEvent.click(modalGenerateButton)

    await waitFor(() => {
      expect(apiMock.generateOutput).toHaveBeenCalledWith({
        template_id: "77",
        item_ids: ["101"],
        title: undefined
      })
    })
  })
})
