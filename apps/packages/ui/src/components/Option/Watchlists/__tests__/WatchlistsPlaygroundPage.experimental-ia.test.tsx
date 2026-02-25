// @vitest-environment jsdom

import React from "react"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WatchlistsPlaygroundPage } from "../WatchlistsPlaygroundPage"

const IA_STORAGE_KEY = "watchlists:ia-experiment:v1"
const IA_ROLLOUT_STORAGE_KEY = "watchlists:ia-rollout:v1"

const mocks = vi.hoisted(() => {
  const state = {
    activeTab: "sources" as
      | "overview"
      | "sources"
      | "jobs"
      | "runs"
      | "items"
      | "outputs"
      | "templates"
      | "settings",
    setActiveTab: vi.fn((next: string) => {
      state.activeTab = next as typeof state.activeTab
    })
  }
  return {
    fetchWatchlistRunsMock: vi.fn(),
    recordWatchlistsIaExperimentTelemetryMock: vi.fn(),
    trackWatchlistsOnboardingTelemetryMock: vi.fn(),
    notificationDestroyMock: vi.fn(),
    state
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown, options?: Record<string, unknown>) => {
      if (typeof defaultValue !== "string") return _key
      if (!options) return defaultValue
      return defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options[token] ?? ""))
    }
  })
}))

vi.mock("antd", () => {
  const Alert = ({ title, description, closable, onClose }: any) => (
    <div>
      <div>{title}</div>
      <div>{description}</div>
      {closable ? (
        <button type="button" onClick={() => onClose?.()}>
          Dismiss
        </button>
      ) : null}
    </div>
  )

  const Tabs = ({ items = [] }: any) => (
    <div>
      {items.map((item: any) => (
        <button key={item.key} type="button" data-testid={`watchlists-tab-${item.key}`}>
          {item.label}
        </button>
      ))}
      <div>{items[0]?.children}</div>
    </div>
  )

  const Modal = ({ open, title, children, footer }: any) =>
    open ? (
      <div>
        <h3>{title}</h3>
        {children}
        <div>{footer}</div>
      </div>
    ) : null

  const Empty = ({ description }: any) => <div>{description}</div>
  const Button = ({ children, onClick, disabled, ...rest }: any) => (
    <button type="button" onClick={() => onClick?.()} disabled={Boolean(disabled)} {...rest}>
      {children}
    </button>
  )
  return { Alert, Tabs, Empty, Button, Modal }
})

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    destroy: mocks.notificationDestroyMock,
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/services/watchlists", () => ({
  fetchWatchlistRuns: (...args: any[]) => mocks.fetchWatchlistRunsMock(...args),
  recordWatchlistsIaExperimentTelemetry: (...args: any[]) =>
    mocks.recordWatchlistsIaExperimentTelemetryMock(...args)
}))

vi.mock("@/utils/watchlists-onboarding-telemetry", () => ({
  trackWatchlistsOnboardingTelemetry: (...args: any[]) =>
    mocks.trackWatchlistsOnboardingTelemetryMock(...args)
}))

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      activeTab: mocks.state.activeTab,
      setActiveTab: mocks.state.setActiveTab,
      openRunDetail: vi.fn(),
      resetStore: vi.fn()
    })
}))

vi.mock("../OverviewTab/OverviewTab", () => ({
  OverviewTab: () => <div>Overview tab</div>
}))
vi.mock("../SourcesTab/SourcesTab", () => ({
  SourcesTab: () => <div>Sources tab</div>
}))
vi.mock("../JobsTab/JobsTab", () => ({
  JobsTab: () => <div>Jobs tab</div>
}))
vi.mock("../RunsTab/RunsTab", () => ({
  RunsTab: () => <div>Runs tab</div>
}))
vi.mock("../OutputsTab/OutputsTab", () => ({
  OutputsTab: () => <div>Outputs tab</div>
}))
vi.mock("../TemplatesTab/TemplatesTab", () => ({
  TemplatesTab: () => <div>Templates tab</div>
}))
vi.mock("../SettingsTab/SettingsTab", () => ({
  SettingsTab: () => <div>Settings tab</div>
}))
vi.mock("../ItemsTab/ItemsTab", () => ({
  ItemsTab: () => <div>Items tab</div>
}))

describe("WatchlistsPlaygroundPage experimental IA", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchWatchlistRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.recordWatchlistsIaExperimentTelemetryMock.mockResolvedValue({ accepted: true })
    mocks.trackWatchlistsOnboardingTelemetryMock.mockResolvedValue(undefined)
    mocks.state.activeTab = "sources"
    localStorage.removeItem(IA_STORAGE_KEY)
    localStorage.removeItem(IA_ROLLOUT_STORAGE_KEY)
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = true
  })

  afterEach(() => {
    cleanup()
    localStorage.removeItem(IA_STORAGE_KEY)
    localStorage.removeItem(IA_ROLLOUT_STORAGE_KEY)
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
  })

  it("shows task-centered primary tabs and exposes implementation tabs via More views", () => {
    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-tab-overview")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-sources")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-items")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-outputs")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-settings")).toBeInTheDocument()

    expect(screen.queryByTestId("watchlists-tab-jobs")).not.toBeInTheDocument()
    expect(screen.queryByTestId("watchlists-tab-runs")).not.toBeInTheDocument()
    expect(screen.queryByTestId("watchlists-tab-templates")).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId("watchlists-experimental-tab-jobs"))
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("jobs")
    fireEvent.click(screen.getByTestId("watchlists-experimental-tab-runs"))
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("runs")
  })

  it("keeps hidden tabs reachable when currently selected", () => {
    mocks.state.activeTab = "templates"

    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-tab-templates")).toBeInTheDocument()
  })

  it("routes task views to user outcomes and keeps legacy tabs mapped to the active task", () => {
    render(<WatchlistsPlaygroundPage />)

    fireEvent.click(screen.getByTestId("watchlists-task-view-collect"))
    fireEvent.click(screen.getByTestId("watchlists-task-view-review"))
    fireEvent.click(screen.getByTestId("watchlists-task-view-briefings"))

    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("sources")
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("items")
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("outputs")

    cleanup()
    mocks.state.activeTab = "runs"
    render(<WatchlistsPlaygroundPage />)
    expect(screen.getByTestId("watchlists-task-view-review")).toHaveAttribute("aria-pressed", "true")

    cleanup()
    mocks.state.activeTab = "templates"
    render(<WatchlistsPlaygroundPage />)
    expect(screen.getByTestId("watchlists-task-view-briefings")).toHaveAttribute("aria-pressed", "true")
  })

  it("records tab transition telemetry when experiment mode is active", () => {
    const { rerender } = render(<WatchlistsPlaygroundPage />)

    let payload = JSON.parse(localStorage.getItem(IA_STORAGE_KEY) || "{}")
    expect(payload.transitions).toBe(0)
    expect(payload.variant).toBe("experimental")
    expect(payload.visited_tabs).toContain("sources")

    mocks.state.activeTab = "runs"
    rerender(<WatchlistsPlaygroundPage />)
    payload = JSON.parse(localStorage.getItem(IA_STORAGE_KEY) || "{}")
    expect(payload.transitions).toBe(1)
    expect(payload.visited_tabs).toContain("sources")
    expect(payload.visited_tabs).toContain("runs")
    expect(mocks.recordWatchlistsIaExperimentTelemetryMock).toHaveBeenCalled()
  })

  it("uses the legacy tab map and records baseline telemetry when experiment is disabled", () => {
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = false

    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-tab-jobs")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-items")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-tab-templates")).toBeInTheDocument()
    expect(screen.queryByTestId("watchlists-experimental-tab-jobs")).not.toBeInTheDocument()
    const payload = JSON.parse(localStorage.getItem(IA_STORAGE_KEY) || "{}")
    expect(payload.variant).toBe("baseline")
    expect(payload.visited_tabs).toContain("sources")
    expect(mocks.recordWatchlistsIaExperimentTelemetryMock).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "baseline" })
    )
  })

  it("honors persisted rollout assignment when runtime override is absent", () => {
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
    localStorage.setItem(
      IA_ROLLOUT_STORAGE_KEY,
      JSON.stringify({ version: 1, variant: "experimental" })
    )

    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-experimental-tab-jobs")).toBeInTheDocument()
    expect(screen.queryByTestId("watchlists-tab-jobs")).not.toBeInTheDocument()

    const payload = JSON.parse(localStorage.getItem(IA_STORAGE_KEY) || "{}")
    expect(payload.variant).toBe("experimental")
  })
})
