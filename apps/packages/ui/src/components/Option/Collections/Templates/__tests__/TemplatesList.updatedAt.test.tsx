import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { useCollectionsStore } from "@/store/collections"
import { TemplatesList } from "../TemplatesList"

const apiMock = vi.hoisted(() => ({
  getOutputTemplates: vi.fn()
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
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return interpolate(fallbackOrOptions, maybeOptions)
      }
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        const maybeDefault = fallbackOrOptions.defaultValue
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

describe("TemplatesList updated timestamp rendering", () => {
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
    apiMock.getOutputTemplates.mockResolvedValue({
      items: [
        {
          id: "tpl-1",
          name: "Template A",
          description: "Valid timestamp template",
          type: "briefing_markdown",
          format: "md",
          body: "Body A",
          is_default: false,
          created_at: "2026-01-15T08:30:00Z",
          updated_at: "2026-01-15T08:30:00Z"
        },
        {
          id: "tpl-2",
          name: "Template B",
          description: "Invalid timestamp template",
          type: "newsletter_markdown",
          format: "md",
          body: "Body B",
          is_default: false,
          created_at: "2026-01-15T08:30:00Z",
          updated_at: "not-a-date"
        }
      ],
      total: 2
    })
  })

  it("shows updated timestamp label only for parseable updated_at values", async () => {
    render(<TemplatesList />)

    expect(await screen.findByText("Template A")).toBeTruthy()
    expect(await screen.findByText("Template B")).toBeTruthy()

    await waitFor(() => {
      const labels = screen.getAllByText(/Updated /)
      expect(labels).toHaveLength(1)
      expect(labels[0].textContent).toContain("Updated")
    })
  })
})
