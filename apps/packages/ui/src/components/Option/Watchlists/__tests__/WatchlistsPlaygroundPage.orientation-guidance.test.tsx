// @vitest-environment jsdom

import React from "react"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WatchlistsPlaygroundPage } from "../WatchlistsPlaygroundPage"

const mocks = vi.hoisted(() => {
  const state = {
    activeTab: "overview" as
      | "overview"
      | "sources"
      | "jobs"
      | "runs"
      | "items"
      | "outputs"
      | "templates"
      | "settings",
    overviewHealth: {
      tabBadges: {
        sources: 0,
        runs: 0,
        outputs: 0
      }
    },
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
      overviewHealth: mocks.state.overviewHealth,
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

describe("WatchlistsPlaygroundPage orientation guidance", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.state.activeTab = "overview"
    mocks.fetchWatchlistRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.recordWatchlistsIaExperimentTelemetryMock.mockResolvedValue({ accepted: true })
    mocks.trackWatchlistsOnboardingTelemetryMock.mockResolvedValue(undefined)
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = false
    localStorage.removeItem("beta-dismissed:watchlists")
    localStorage.removeItem("watchlists:guided-tour:v1")
    localStorage.removeItem("watchlists:ia-experiment:v1")
  })

  afterEach(() => {
    cleanup()
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
    localStorage.removeItem("beta-dismissed:watchlists")
    localStorage.removeItem("watchlists:guided-tour:v1")
    localStorage.removeItem("watchlists:ia-experiment:v1")
  })

  it("renders contextual guidance and key cross-surface actions for Activity and Articles", () => {
    mocks.state.activeTab = "runs"
    const { unmount } = render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-orientation-banner")).toBeInTheDocument()
    expect(screen.getByTestId("watchlists-orientation-what")).toHaveTextContent(
      "Activity shows monitor run status, logs, and failures."
    )
    expect(screen.getByTestId("watchlists-orientation-next")).toHaveTextContent(
      "Next: open Reports to verify generated briefing outputs."
    )
    fireEvent.click(screen.getByTestId("watchlists-orientation-action-outputs"))
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("outputs")

    unmount()
    mocks.state.activeTab = "items"
    render(<WatchlistsPlaygroundPage />)
    fireEvent.click(screen.getByTestId("watchlists-orientation-action-jobs"))
    expect(mocks.state.setActiveTab).toHaveBeenCalledWith("jobs")
  })

  it("supports Overview -> Feeds -> Monitors -> Activity -> Reports next-step journey", () => {
    mocks.state.activeTab = "overview"
    const { rerender } = render(<WatchlistsPlaygroundPage />)

    const expectedPath: Array<
      "sources" | "jobs" | "runs" | "outputs"
    > = ["sources", "jobs", "runs", "outputs"]

    for (const nextTab of expectedPath) {
      fireEvent.click(screen.getByTestId(`watchlists-orientation-action-${nextTab}`))
      expect(mocks.state.setActiveTab).toHaveBeenLastCalledWith(nextTab)
      rerender(<WatchlistsPlaygroundPage />)
    }
  })
})
