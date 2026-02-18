import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { JobFormModal } from "../JobFormModal"

const servicesMock = vi.hoisted(() => ({
  createWatchlistJob: vi.fn(),
  updateWatchlistJob: vi.fn(),
  fetchJobOutputTemplates: vi.fn(),
  fetchWatchlistTemplates: vi.fn()
}))

const translationMock = vi.hoisted(() => ({
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
    t: translationMock.t
  })
}))

vi.mock("@/services/watchlists", () => ({
  createWatchlistJob: (...args: unknown[]) => servicesMock.createWatchlistJob(...args),
  updateWatchlistJob: (...args: unknown[]) => servicesMock.updateWatchlistJob(...args),
  fetchJobOutputTemplates: (...args: unknown[]) => servicesMock.fetchJobOutputTemplates(...args),
  fetchWatchlistTemplates: (...args: unknown[]) => servicesMock.fetchWatchlistTemplates(...args)
}))

vi.mock("../ScopeSelector", () => ({
  ScopeSelector: () => <div>Scope Selector</div>
}))

vi.mock("../FilterBuilder", () => ({
  FilterBuilder: () => <div>Filter Builder</div>
}))

vi.mock("../SchedulePicker", () => ({
  SchedulePicker: () => <div>Schedule Picker</div>
}))

describe("JobFormModal template source options", () => {
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

    servicesMock.fetchJobOutputTemplates.mockResolvedValue({
      items: [
        {
          id: "11",
          name: "briefing_markdown",
          format: "md",
          updated_at: "2026-01-15T00:00:00Z"
        }
      ],
      total: 1
    })
    servicesMock.fetchWatchlistTemplates.mockResolvedValue({
      items: [
        {
          name: "briefing_markdown",
          format: "md",
          content: "legacy duplicate"
        },
        {
          name: "legacy_only",
          format: "md",
          content: "legacy unique"
        }
      ]
    })
  })

  it("prefers outputs templates over legacy duplicates and labels source correctly", async () => {
    render(
      <JobFormModal
        open
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(servicesMock.fetchJobOutputTemplates).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistTemplates).toHaveBeenCalled()
    })

    fireEvent.click(screen.getByText("Output & Delivery"))

    await screen.findByText("Template name")
    const selectorPlaceholder = await screen.findByText("Select a template")
    fireEvent.mouseDown(selectorPlaceholder)

    expect(await screen.findByText("briefing_markdown (MD) · Outputs template")).toBeTruthy()
    expect(await screen.findByText("legacy_only · Legacy watchlists template")).toBeTruthy()
    expect(screen.queryByText("briefing_markdown · Legacy watchlists template")).toBeNull()
  })
})
