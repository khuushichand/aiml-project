// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { message } from "antd"
import { JobFormModal } from "../JobFormModal"

const servicesMock = vi.hoisted(() => ({
  createWatchlistJob: vi.fn(),
  updateWatchlistJob: vi.fn(),
  fetchWatchlistSources: vi.fn(),
  fetchWatchlistGroups: vi.fn(),
  fetchJobOutputTemplates: vi.fn(),
  fetchWatchlistTemplates: vi.fn(),
  previewWatchlistJob: vi.fn()
}))

const telemetryMock = vi.hoisted(() => ({
  trackWatchlistsPreventionTelemetry: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) => {
  if (!values) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = values[token]
    return value == null ? "" : String(value)
  })
}

const translationMock = vi.hoisted(() => ({
  catalog: {
    "watchlists:jobs.form.scheduleTooFrequent":
      "Schedule is too frequent. Minimum interval is every {{minutes}} minutes.",
    "watchlists:schedule.tooFrequentRemediation":
      "Increase schedule interval to meet the minimum cadence."
  } as Record<string, string>,
  t: (
    key: string,
    fallbackOrOptions?: string | { defaultValue?: string },
    maybeOptions?: Record<string, unknown>
  ) => {
    const templateFromCatalog = translationMock.catalog[key]
    if (typeof fallbackOrOptions === "string") {
      return interpolate(templateFromCatalog || fallbackOrOptions, maybeOptions)
    }
    if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
      const maybeDefault = fallbackOrOptions.defaultValue
      if (typeof maybeDefault === "string") {
        return interpolate(templateFromCatalog || maybeDefault, maybeOptions)
      }
    }
    return templateFromCatalog || key
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: translationMock.t
  })
}))

vi.mock("@/services/watchlists", () => ({
  createWatchlistJob: (...args: unknown[]) => servicesMock.createWatchlistJob(...args),
  updateWatchlistJob: (...args: unknown[]) => servicesMock.updateWatchlistJob(...args),
  fetchWatchlistSources: (...args: unknown[]) => servicesMock.fetchWatchlistSources(...args),
  fetchWatchlistGroups: (...args: unknown[]) => servicesMock.fetchWatchlistGroups(...args),
  fetchJobOutputTemplates: (...args: unknown[]) => servicesMock.fetchJobOutputTemplates(...args),
  fetchWatchlistTemplates: (...args: unknown[]) => servicesMock.fetchWatchlistTemplates(...args),
  previewWatchlistJob: (...args: unknown[]) => servicesMock.previewWatchlistJob(...args)
}))

vi.mock("@/utils/watchlists-prevention-telemetry", () => ({
  trackWatchlistsPreventionTelemetry: (...args: unknown[]) =>
    telemetryMock.trackWatchlistsPreventionTelemetry(...args)
}))

vi.mock("../ScopeSelector", () => ({
  ScopeSelector: ({ onChange }: { onChange: (value: unknown) => void }) => (
    <button
      type="button"
      data-testid="scope-setter"
      onClick={() => onChange({ sources: [1], tags: ["tech"] })}
    >
      Set scope
    </button>
  )
}))

vi.mock("../SchedulePicker", () => ({
  SchedulePicker: ({ onChange }: { onChange: (value: string) => void }) => (
    <button
      type="button"
      data-testid="schedule-setter"
      onClick={() => onChange("0 9 * * *")}
    >
      Set schedule
    </button>
  )
}))

vi.mock("../FilterBuilder", () => ({
  FilterBuilder: ({ onChange }: { onChange: (value: unknown) => void }) => (
    <button
      type="button"
      data-testid="filters-setter"
      onClick={() =>
        onChange([
          {
            type: "keyword",
            action: "include",
            value: { keywords: ["ai"], match: "any" },
            is_active: true
          }
        ])
      }
    >
      Set filters
    </button>
  )
}))

describe("JobFormModal live summary", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    telemetryMock.trackWatchlistsPreventionTelemetry.mockResolvedValue(undefined)
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

    servicesMock.fetchWatchlistSources.mockResolvedValue({
      items: [
        {
          id: 1,
          name: "Source One",
          url: "https://example.com/rss.xml",
          source_type: "rss",
          active: true,
          tags: ["tech"],
          created_at: "2026-01-15T00:00:00Z",
          updated_at: "2026-01-15T00:00:00Z",
          last_scraped_at: null,
          status: "healthy"
        }
      ],
      total: 1,
      page: 1,
      size: 500,
      has_more: false
    })
    servicesMock.fetchWatchlistGroups.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      size: 500,
      has_more: false
    })
    servicesMock.fetchJobOutputTemplates.mockResolvedValue({
      items: [],
      total: 0
    })
    servicesMock.fetchWatchlistTemplates.mockResolvedValue({
      items: []
    })
    servicesMock.previewWatchlistJob.mockResolvedValue({
      items: [],
      total: 0,
      ingestable: 0,
      filtered: 0
    })
  })

  it("updates the live summary as authoring fields change", async () => {
    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
      expect(servicesMock.fetchJobOutputTemplates).toHaveBeenCalled()
    })

    expect(screen.getByTestId("job-form-summary-name")).toHaveTextContent("Untitled monitor")
    expect(screen.getByTestId("job-form-summary-scope")).toHaveTextContent("No feeds selected")
    expect(screen.getByTestId("job-form-summary-schedule")).toHaveTextContent("Not scheduled")
    expect(screen.getByTestId("job-form-summary-filters")).toHaveTextContent("No filters configured")
    expect(screen.getByTestId("job-form-summary-preview")).toHaveTextContent(
      "Save this monitor once to load sample candidates for live filter preview."
    )

    fireEvent.change(
      screen.getByPlaceholderText("e.g., Daily Tech News"),
      { target: { value: "Morning Brief" } }
    )
    fireEvent.click(screen.getByTestId("scope-setter"))
    const collapseHeaders = Array.from(document.querySelectorAll(".ant-collapse-header"))
    fireEvent.click(collapseHeaders[1] as Element)
    fireEvent.click(screen.getByTestId("schedule-setter"))
    fireEvent.click(collapseHeaders[2] as Element)
    fireEvent.click(screen.getByTestId("filters-setter"))

    await waitFor(() => {
      expect(screen.getByTestId("job-form-summary-name")).toHaveTextContent("Morning Brief")
      expect(screen.getByTestId("job-form-summary-scope")).toHaveTextContent("1 feed, 1 tag")
      expect(screen.getByTestId("job-form-summary-schedule")).toHaveTextContent("Daily at 09:00")
      expect(screen.getByTestId("job-form-summary-filters")).toHaveTextContent("1 filters configured")
      expect(screen.getByTestId("job-form-summary-scope-lines")).toHaveTextContent("Source One")
      expect(screen.getByTestId("job-form-summary-scope-lines")).toHaveTextContent("tech")
    })
  })

  it("shows localized remediation for structured watchlists validation errors", async () => {
    const messageErrorSpy = vi
      .spyOn(message, "error")
      .mockImplementation(() => () => undefined)
    servicesMock.createWatchlistJob.mockRejectedValueOnce(
      Object.assign(new Error("Request failed"), {
        status: 422,
        details: {
          detail: {
            code: "watchlists_validation_error",
            rule: "schedule_too_frequent",
            message_key: "watchlists:jobs.form.scheduleTooFrequent",
            message: "Schedule is too frequent. Minimum interval is every 5 minutes.",
            remediation_key: "watchlists:schedule.tooFrequentRemediation",
            remediation: "Increase schedule interval to meet the minimum cadence.",
            meta: {
              minimum_minutes: 7
            }
          }
        }
      })
    )

    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
      target: { value: "Morning Brief" }
    })
    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(servicesMock.createWatchlistJob).toHaveBeenCalledTimes(1)
      expect(messageErrorSpy).toHaveBeenCalled()
    })

    const renderedError = String(messageErrorSpy.mock.calls.at(-1)?.[0] || "")
    expect(renderedError).toContain("every 7 minutes")
    expect(renderedError).toContain("Increase schedule interval to meet the minimum cadence.")
    expect(telemetryMock.trackWatchlistsPreventionTelemetry).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "watchlists_validation_blocked",
        surface: "job_form",
        rule: "schedule_too_frequent"
      })
    )

    messageErrorSpy.mockRestore()
  })
})
