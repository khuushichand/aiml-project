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
    <div>
      <button
        type="button"
        data-testid="scope-setter"
        onClick={() => onChange({ sources: [1], tags: ["tech"] })}
      >
        Set scope
      </button>
      <button
        type="button"
        data-testid="scope-setter-10"
        onClick={() =>
          onChange({
            sources: Array.from({ length: 10 }, (_value, index) => index + 1),
            tags: ["tech"]
          })}
      >
        Set scope 10
      </button>
      <button
        type="button"
        data-testid="scope-setter-50"
        onClick={() =>
          onChange({
            sources: Array.from({ length: 50 }, (_value, index) => index + 1),
            tags: ["tech"]
          })}
      >
        Set scope 50
      </button>
    </div>
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
    fireEvent.click(screen.getByTestId("job-form-mode-advanced"))
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

  it("shows mapped remediation copy for non-validation save failures", async () => {
    const messageErrorSpy = vi
      .spyOn(message, "error")
      .mockImplementation(() => () => undefined)

    servicesMock.createWatchlistJob.mockRejectedValueOnce(
      Object.assign(new Error("upstream unavailable"), {
        status: 503
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
    expect(renderedError).toContain("Could not save monitor.")
    expect(renderedError).toContain("Retry in a moment")

    messageErrorSpy.mockRestore()
  })

  it("includes audio defaults in create payload when audio briefing is enabled", async () => {
    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
      target: { value: "Audio Morning Brief" }
    })
    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByTestId("job-form-mode-advanced"))
    fireEvent.click(screen.getByText("Output & Delivery"))
    fireEvent.click(screen.getByTestId("job-form-audio-enabled-switch"))
    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(servicesMock.createWatchlistJob).toHaveBeenCalledTimes(1)
    })

    expect(servicesMock.createWatchlistJob).toHaveBeenCalledWith(
      expect.objectContaining({
        output_prefs: expect.objectContaining({
          generate_audio: true,
          audio_voice: "alloy",
          audio_speed: 1,
          target_audio_minutes: 8
        })
      })
    )
  })

  it("guides basic mode through scope and schedule before review step", async () => {
    const messageErrorSpy = vi
      .spyOn(message, "error")
      .mockImplementation(() => () => undefined)

    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    expect(screen.getByTestId("job-form-basic-stepper")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("job-form-basic-next"))

    expect(messageErrorSpy).toHaveBeenCalledWith(
      "Please select at least one feed, group, or tag"
    )

    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByTestId("job-form-basic-next"))
    expect(screen.getByTestId("job-form-basic-step-schedule")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("job-form-basic-next"))
    expect(messageErrorSpy).toHaveBeenCalledWith(
      "Set a schedule before continuing to review."
    )

    fireEvent.click(screen.getByTestId("schedule-setter"))
    fireEvent.click(screen.getByTestId("job-form-basic-next"))
    fireEvent.click(screen.getByTestId("job-form-basic-next"))

    expect(screen.getByTestId("job-form-basic-review")).toBeInTheDocument()
    expect(screen.getByTestId("job-form-basic-review")).toHaveTextContent("1 feed, 1 tag")

    messageErrorSpy.mockRestore()
  })

  it.each([
    {
      scenario: "1-feed baseline",
      scopeButton: "scope-setter",
      expectedScopeSummary: "1 feed, 1 tag"
    },
    {
      scenario: "10-feed mid-density",
      scopeButton: "scope-setter-10",
      expectedScopeSummary: "10 feeds, 1 tag"
    },
    {
      scenario: "50-feed high-density",
      scopeButton: "scope-setter-50",
      expectedScopeSummary: "50 feeds, 1 tag"
    }
  ])(
    "maintains readable basic review summary for $scenario monitor setup",
    async ({ scopeButton, expectedScopeSummary }) => {
      render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

      await waitFor(() => {
        expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
        expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
      })

      fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
        target: { value: "Scaled Monitor" }
      })
      fireEvent.click(screen.getByTestId(scopeButton))
      expect(screen.getByTestId("job-form-summary-scope")).toHaveTextContent(
        expectedScopeSummary
      )

      fireEvent.click(screen.getByTestId("job-form-basic-next"))
      fireEvent.click(screen.getByTestId("schedule-setter"))
      fireEvent.click(screen.getByTestId("job-form-basic-next"))
      fireEvent.click(screen.getByTestId("job-form-basic-next"))

      expect(screen.getByTestId("job-form-basic-review")).toHaveTextContent(
        expectedScopeSummary
      )
    }
  )

  it("hydrates audio preferences for edits and clears audio fields when disabled", async () => {
    servicesMock.updateWatchlistJob.mockResolvedValueOnce({
      id: 77
    })

    render(
      <JobFormModal
        open
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        initialValues={{
          id: 77,
          name: "Existing audio monitor",
          description: "existing",
          scope: { sources: [1] },
          schedule_expr: "0 9 * * *",
          timezone: "UTC",
          active: true,
          output_prefs: {
            template: { default_name: "briefing_markdown" },
            generate_audio: true,
            audio_voice: "nova",
            audio_speed: 1.25,
            target_audio_minutes: 12
          },
          job_filters: null,
          created_at: "2026-01-15T00:00:00Z"
        }}
      />
    )

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
      expect(servicesMock.previewWatchlistJob).toHaveBeenCalledWith(77, {
        limit: 60,
        per_source: 12
      })
    })

    fireEvent.click(screen.getByText("Output & Delivery"))

    const audioSwitch = screen.getByTestId("job-form-audio-enabled-switch")
    expect(audioSwitch).toHaveAttribute("aria-checked", "true")
    expect(screen.getByDisplayValue("1.25")).toBeInTheDocument()
    expect(screen.getByDisplayValue("12")).toBeInTheDocument()
    fireEvent.click(audioSwitch)

    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => {
      expect(servicesMock.updateWatchlistJob).toHaveBeenCalledTimes(1)
    })

    const [, payload] = servicesMock.updateWatchlistJob.mock.calls[0]
    expect(payload.output_prefs).toEqual(
      expect.objectContaining({
        generate_audio: false,
        template: { default_name: "briefing_markdown" }
      })
    )
    expect(payload.output_prefs).not.toHaveProperty("audio_voice")
    expect(payload.output_prefs).not.toHaveProperty("audio_speed")
    expect(payload.output_prefs).not.toHaveProperty("target_audio_minutes")
  })

  it("persists advanced audio settings when provided", async () => {
    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
      target: { value: "Advanced Audio Brief" }
    })
    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByTestId("job-form-mode-advanced"))
    fireEvent.click(screen.getByText("Output & Delivery"))
    fireEvent.click(screen.getByTestId("job-form-audio-enabled-switch"))
    fireEvent.click(screen.getByRole("button", { name: "Show advanced audio options" }))
    fireEvent.change(screen.getByPlaceholderText("file:///path/to/bed.mp3"), {
      target: { value: "file:///tmp/news-bed.mp3" }
    })
    fireEvent.change(
      screen.getByPlaceholderText('{ "HOST": "af_heart", "REPORTER": "am_adam" }'),
      { target: { value: '{ "HOST": "af_heart", "REPORTER": "am_adam" }' } }
    )

    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(servicesMock.createWatchlistJob).toHaveBeenCalledTimes(1)
    })

    expect(servicesMock.createWatchlistJob).toHaveBeenCalledWith(
      expect.objectContaining({
        output_prefs: expect.objectContaining({
          generate_audio: true,
          background_audio_uri: "file:///tmp/news-bed.mp3",
          voice_map: {
            HOST: "af_heart",
            REPORTER: "am_adam"
          }
        })
      })
    )
  }, 10000)

  it("blocks save when advanced audio voice map JSON is invalid", async () => {
    const messageErrorSpy = vi
      .spyOn(message, "error")
      .mockImplementation(() => () => undefined)

    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
      target: { value: "Invalid Audio Map" }
    })
    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByTestId("job-form-mode-advanced"))
    fireEvent.click(screen.getByText("Output & Delivery"))
    fireEvent.click(screen.getByTestId("job-form-audio-enabled-switch"))
    fireEvent.click(screen.getByRole("button", { name: "Show advanced audio options" }))
    fireEvent.change(
      screen.getByPlaceholderText('{ "HOST": "af_heart", "REPORTER": "am_adam" }'),
      { target: { value: "{invalid json}" } }
    )

    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(messageErrorSpy).toHaveBeenCalledWith(
        "Voice map must be valid JSON with marker-to-voice string pairs."
      )
    })
    expect(servicesMock.createWatchlistJob).not.toHaveBeenCalled()

    messageErrorSpy.mockRestore()
  }, 10000)

  it("preserves advanced settings when switching back to basic mode", async () => {
    const messageInfoSpy = vi
      .spyOn(message, "info")
      .mockImplementation(() => () => undefined)

    render(<JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(servicesMock.fetchWatchlistSources).toHaveBeenCalled()
      expect(servicesMock.fetchWatchlistGroups).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech News"), {
      target: { value: "Mode Preservation Monitor" }
    })
    fireEvent.click(screen.getByTestId("scope-setter"))
    fireEvent.click(screen.getByTestId("job-form-mode-advanced"))
    fireEvent.click(screen.getByText("Output & Delivery"))
    fireEvent.change(screen.getByPlaceholderText("Defaults to output title"), {
      target: { value: "Ops Digest" }
    })
    fireEvent.click(screen.getByTestId("job-form-mode-basic"))
    fireEvent.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(servicesMock.createWatchlistJob).toHaveBeenCalledTimes(1)
    })
    expect(messageInfoSpy).toHaveBeenCalledWith(
      "Advanced settings are preserved and will still apply, but they are hidden in Basic mode."
    )
    expect(servicesMock.createWatchlistJob).toHaveBeenCalledWith(
      expect.objectContaining({
        output_prefs: expect.objectContaining({
          deliveries: expect.objectContaining({
            email: expect.objectContaining({
              subject: "Ops Digest"
            })
          })
        })
      })
    )

    messageInfoSpy.mockRestore()
  })

  it("restores focus to the launch control when the monitor modal closes", async () => {
    const trigger = document.createElement("button")
    trigger.type = "button"
    trigger.textContent = "Open monitor form"
    document.body.appendChild(trigger)
    trigger.focus()

    const { rerender } = render(
      <JobFormModal open onClose={vi.fn()} onSuccess={vi.fn()} />
    )

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument()
    })

    rerender(<JobFormModal open={false} onClose={vi.fn()} onSuccess={vi.fn()} />)

    await waitFor(() => {
      expect(trigger).toHaveFocus()
    })

    trigger.remove()
  })
})
