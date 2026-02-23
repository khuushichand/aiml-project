// @vitest-environment jsdom

import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { OverviewTab } from "../OverviewTab"

const mockState = vi.hoisted(() => ({
  fetchOverviewMock: vi.fn(),
  createWatchlistSourceMock: vi.fn(),
  createWatchlistJobMock: vi.fn(),
  triggerWatchlistRunMock: vi.fn(),
  trackWatchlistsOnboardingTelemetryMock: vi.fn(),
  setActiveTabMock: vi.fn(),
  openSourceFormMock: vi.fn(),
  openJobFormMock: vi.fn(),
  openRunDetailMock: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
          const value = maybeOptions?.[token]
          return value == null ? "" : String(value)
        })
      }
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        const fallback = fallbackOrOptions.defaultValue
        if (typeof fallback === "string") {
          return fallback
        }
      }
      return key
    }
  })
}))

vi.mock("@/services/watchlists-overview", () => ({
  fetchWatchlistsOverviewData: (...args: unknown[]) =>
    mockState.fetchOverviewMock(...args),
  getOverviewTabBadges: (model?: { tabBadges?: { sources?: number; runs?: number; outputs?: number } } | null) => ({
    sources: Number(model?.tabBadges?.sources || 0),
    runs: Number(model?.tabBadges?.runs || 0),
    outputs: Number(model?.tabBadges?.outputs || 0)
  })
}))

vi.mock("@/services/watchlists", () => ({
  createWatchlistSource: (...args: unknown[]) => mockState.createWatchlistSourceMock(...args),
  createWatchlistJob: (...args: unknown[]) => mockState.createWatchlistJobMock(...args),
  triggerWatchlistRun: (...args: unknown[]) => mockState.triggerWatchlistRunMock(...args)
}))

vi.mock("@/utils/watchlists-onboarding-telemetry", () => ({
  trackWatchlistsOnboardingTelemetry: (...args: unknown[]) =>
    mockState.trackWatchlistsOnboardingTelemetryMock(...args)
}))

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      setActiveTab: mockState.setActiveTabMock,
      openSourceForm: mockState.openSourceFormMock,
      openJobForm: mockState.openJobFormMock,
      openRunDetail: mockState.openRunDetailMock
    })
}))

vi.mock("@/utils/dateFormatters", () => ({
  formatRelativeTime: () => "just now"
}))

const createOverviewPayload = (overrides?: Partial<Record<string, unknown>>) => ({
  fetchedAt: "2026-02-18T12:00:00Z",
  sources: {
    total: 0,
    healthy: 0,
    degraded: 0,
    inactive: 0,
    unknown: 0,
    ...(overrides?.sources as Record<string, unknown> | undefined)
  },
  jobs: {
    total: 0,
    active: 0,
    nextRunAt: null,
    attention: 0,
    ...(overrides?.jobs as Record<string, unknown> | undefined)
  },
  items: {
    unread: 0,
    ...(overrides?.items as Record<string, unknown> | undefined)
  },
  runs: {
    running: 0,
    pending: 0,
    failed: 0,
    recentFailed: [],
    ...(overrides?.runs as Record<string, unknown> | undefined)
  },
  outputs: {
    total: 0,
    expired: 0,
    deliveryIssues: 0,
    attention: 0,
    ...(overrides?.outputs as Record<string, unknown> | undefined)
  },
  health: {
    statuses: {
      sources: "unknown",
      jobs: "unknown",
      runs: "unknown",
      outputs: "unknown"
    },
    attention: {
      total: 0,
      sources: 0,
      jobs: 0,
      runs: 0,
      outputs: 0
    },
    tabBadges: {
      sources: 0,
      runs: 0,
      outputs: 0
    },
    ...(overrides?.health as Record<string, unknown> | undefined)
  },
  systemHealth: "healthy" as const,
  ...overrides
})

describe("OverviewTab quick setup flow", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.trackWatchlistsOnboardingTelemetryMock.mockResolvedValue(undefined)
  })

  it("opens Feed creation directly from quick setup", async () => {
    mockState.fetchOverviewMock.mockResolvedValue(createOverviewPayload())

    render(<OverviewTab />)

    await waitFor(() => {
      expect(screen.getByText("Quick setup")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-overview-cta-add-feed"))

    expect(mockState.setActiveTabMock).toHaveBeenCalledWith("sources")
    expect(mockState.openSourceFormMock).toHaveBeenCalledTimes(1)
  })

  it("opens Monitor creation directly when feeds already exist", async () => {
    mockState.fetchOverviewMock.mockResolvedValue(
      createOverviewPayload({
        sources: { total: 2, healthy: 2 },
        jobs: { total: 0, active: 0 }
      })
    )

    render(<OverviewTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-overview-cta-create-monitor")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-overview-cta-create-monitor"))

    expect(mockState.setActiveTabMock).toHaveBeenCalledWith("jobs")
    expect(mockState.openJobFormMock).toHaveBeenCalledTimes(1)
  })

  it("opens guided setup modal and advances to monitor configuration", async () => {
    mockState.fetchOverviewMock.mockResolvedValue(createOverviewPayload())

    render(<OverviewTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-overview-cta-guided-setup")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-overview-cta-guided-setup"))
    expect(mockState.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "quick_setup_opened"
    })
    expect(
      screen.getByText("Tip: paste a feed URL now. You can adjust feed settings later.")
    ).toBeInTheDocument()

    fireEvent.change(
      screen.getByPlaceholderText("e.g., Daily Tech Feed"),
      { target: { value: "AI Feed" } }
    )
    fireEvent.change(
      screen.getByPlaceholderText("https://example.com/feed.xml"),
      { target: { value: "https://example.com/rss.xml" } }
    )
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText("e.g., Morning Brief")).toBeInTheDocument()
    })
    expect(
      screen.getByText("No cron needed: choose a preset schedule for now.")
    ).toBeInTheDocument()
  }, 20_000)

  it("routes to Reports after setup when briefing goal is selected and run-now is disabled", async () => {
    mockState.fetchOverviewMock.mockResolvedValue(createOverviewPayload())
    mockState.createWatchlistSourceMock.mockResolvedValue({ id: 101 })
    mockState.createWatchlistJobMock.mockResolvedValue({ id: 202 })

    render(<OverviewTab />)

    await waitFor(() => {
      expect(screen.getByTestId("watchlists-overview-cta-guided-setup")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("watchlists-overview-cta-guided-setup"))
    fireEvent.change(screen.getByPlaceholderText("e.g., Daily Tech Feed"), {
      target: { value: "AI Feed" }
    })
    fireEvent.change(screen.getByPlaceholderText("https://example.com/feed.xml"), {
      target: { value: "https://example.com/rss.xml" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText("e.g., Morning Brief")).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText("e.g., Morning Brief"), {
      target: { value: "AM Brief" }
    })
    fireEvent.click(screen.getByRole("switch"))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create setup" })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole("button", { name: "Create setup" }))

    await waitFor(() => {
      expect(mockState.setActiveTabMock).toHaveBeenLastCalledWith("outputs")
    })
    expect(mockState.triggerWatchlistRunMock).not.toHaveBeenCalled()
    expect(mockState.createWatchlistJobMock).toHaveBeenCalledWith(
      expect.objectContaining({
        output_prefs: {
          template_name: "briefing_md"
        }
      })
    )
    expect(mockState.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "quick_setup_completed",
      goal: "briefing",
      runNow: false,
      destination: "outputs"
    })
  }, 20_000)
})
