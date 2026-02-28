// @vitest-environment jsdom

import React from "react"
import axe from "axe-core"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WatchlistsPlaygroundPage } from "../WatchlistsPlaygroundPage"
import {
  WATCHLISTS_ISSUE_REPORT_URL,
  WATCHLISTS_MAIN_DOCS_URL,
  WATCHLISTS_TAB_HELP_DOCS
} from "../shared/help-docs"

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

const runA11yBaselineRules = async (context: Element) =>
  axe.run(context, {
    runOnly: {
      type: "rule",
      values: [
        "button-name",
        "link-name",
        "label",
        "aria-valid-attr",
        "aria-valid-attr-value",
        "aria-required-attr"
      ]
    },
    resultTypes: ["violations"]
  })

const expectNoInvalidAriaViolations = (
  violations: Array<{
    id: string
  }>
) => {
  const disallowedIds = new Set([
    "aria-valid-attr",
    "aria-valid-attr-value",
    "aria-required-attr"
  ])

  const disallowedViolations = violations.filter((violation) =>
    disallowedIds.has(violation.id)
  )

  expect(disallowedViolations).toEqual([])
}

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
  const Alert = ({
    title,
    description,
    action,
    closable,
    onClose,
    className,
    type: _type,
    showIcon: _showIcon,
    ...rest
  }: any) => (
    <div className={className} data-testid={rest["data-testid"]}>
      <div>{title}</div>
      <div>{description}</div>
      <div>{action}</div>
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
        <button
          key={item.key}
          type="button"
          data-testid={`watchlists-tab-${item.key}`}
        >
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
    <button
      type="button"
      onClick={() => onClick?.()}
      disabled={Boolean(disabled)}
      {...rest}
    >
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

describe("WatchlistsPlaygroundPage help surfaces", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.state.activeTab = "sources"
    mocks.state.overviewHealth = {
      tabBadges: {
        sources: 0,
        runs: 0,
        outputs: 0
      }
    }
    mocks.fetchWatchlistRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.recordWatchlistsIaExperimentTelemetryMock.mockResolvedValue({ accepted: true })
    mocks.trackWatchlistsOnboardingTelemetryMock.mockResolvedValue(undefined)
    ;(window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__ = false
    localStorage.removeItem("beta-dismissed:watchlists")
    localStorage.removeItem("watchlists:guided-tour:v1")
    localStorage.removeItem("watchlists:teach-points:v1")
    localStorage.removeItem("watchlists:ia-experiment:v1")
  })

  afterEach(() => {
    cleanup()
    delete (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown }).__TLDW_WATCHLISTS_IA_EXPERIMENT__
    localStorage.removeItem("beta-dismissed:watchlists")
    localStorage.removeItem("watchlists:guided-tour:v1")
    localStorage.removeItem("watchlists:teach-points:v1")
    localStorage.removeItem("watchlists:ia-experiment:v1")
  })

  it("shows persistent docs links and tab-context help link", () => {
    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-main-docs-link")).toHaveAttribute("href", WATCHLISTS_MAIN_DOCS_URL)
    expect(screen.getByTestId("watchlists-context-docs-link")).toHaveAttribute(
      "href",
      WATCHLISTS_TAB_HELP_DOCS.sources
    )
    expect(screen.getByTestId("watchlists-beta-docs-link")).toHaveAttribute("href", WATCHLISTS_MAIN_DOCS_URL)
    expect(screen.getByTestId("watchlists-beta-report-link")).toHaveAttribute("href", WATCHLISTS_ISSUE_REPORT_URL)
  })

  it("keeps context docs routing aligned with each canonical tab help label", () => {
    const expectations: Array<{
      tab: typeof mocks.state.activeTab
      href: string
      label: string
    }> = [
      { tab: "overview", href: WATCHLISTS_TAB_HELP_DOCS.overview, label: "Overview guidance" },
      { tab: "sources", href: WATCHLISTS_TAB_HELP_DOCS.sources, label: "Feeds setup" },
      { tab: "jobs", href: WATCHLISTS_TAB_HELP_DOCS.jobs, label: "Monitor scheduling" },
      { tab: "runs", href: WATCHLISTS_TAB_HELP_DOCS.runs, label: "Activity guidance" },
      { tab: "items", href: WATCHLISTS_TAB_HELP_DOCS.items, label: "Article review" },
      { tab: "outputs", href: WATCHLISTS_TAB_HELP_DOCS.outputs, label: "Reports guidance" },
      { tab: "templates", href: WATCHLISTS_TAB_HELP_DOCS.templates, label: "Template authoring" },
      { tab: "settings", href: WATCHLISTS_TAB_HELP_DOCS.settings, label: "Workspace settings" }
    ]

    const { rerender } = render(<WatchlistsPlaygroundPage />)
    const link = () => screen.getByTestId("watchlists-context-docs-link")

    for (const expectation of expectations) {
      mocks.state.activeTab = expectation.tab
      rerender(<WatchlistsPlaygroundPage />)
      expect(link()).toHaveAttribute("href", expectation.href)
      expect(link()).toHaveTextContent(`Learn more: ${expectation.label}`)
    }
  })

  it("renders canonical tab and quick-action labels for the primary workflow", () => {
    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-tab-sources")).toHaveTextContent("Feeds")
    expect(screen.getByTestId("watchlists-tab-jobs")).toHaveTextContent("Monitors")
    expect(screen.getByTestId("watchlists-tab-runs")).toHaveTextContent("Activity")
    expect(screen.getByTestId("watchlists-tab-items")).toHaveTextContent("Articles")
    expect(screen.getByTestId("watchlists-tab-outputs")).toHaveTextContent("Reports")

    expect(screen.getByTestId("watchlists-task-open-sources")).toHaveTextContent("Set up feeds")
    expect(screen.getByTestId("watchlists-task-open-jobs")).toHaveTextContent("Configure monitors")
    expect(screen.getByTestId("watchlists-task-open-runs")).toHaveTextContent("Check activity")
    expect(screen.getByTestId("watchlists-task-open-items")).toHaveTextContent("Review articles")
    expect(screen.getByTestId("watchlists-task-open-outputs")).toHaveTextContent("View reports")
  })

  it("keeps beta banner dismissible and persisted by storage key", () => {
    const { rerender } = render(<WatchlistsPlaygroundPage />)

    expect(screen.getByText("Beta Feature")).toBeInTheDocument()
    const betaAlert = screen.getByText("Beta Feature").parentElement
    expect(betaAlert).not.toBeNull()
    fireEvent.click(within(betaAlert as HTMLElement).getByRole("button", { name: "Dismiss" }))

    expect(screen.queryByText("Beta Feature")).not.toBeInTheDocument()
    expect(localStorage.getItem("beta-dismissed:watchlists")).toBe("1")

    rerender(<WatchlistsPlaygroundPage />)
    expect(screen.queryByText("Beta Feature")).not.toBeInTheDocument()
  })

  it("supports guided-tour start and resume with persisted progress", () => {
    const { unmount } = render(<WatchlistsPlaygroundPage />)

    fireEvent.click(screen.getByTestId("watchlists-start-guide"))
    expect(screen.getByText("Watchlists guided tour")).toBeInTheDocument()
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument()
    expect(
      screen.getByText("Feeds are inputs for monitors. Add RSS/site feeds before scheduling Activity checks.")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument()
    expect(
      screen.getByText("Monitors define schedule, filters, and template-driven reports, including optional audio.")
    ).toBeInTheDocument()

    const persisted = JSON.parse(localStorage.getItem("watchlists:guided-tour:v1") || "{}")
    expect(persisted.status).toBe("in_progress")
    expect(persisted.step).toBe(1)
    expect(mocks.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "guided_tour_started"
    })
    expect(mocks.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "guided_tour_step_viewed",
      step: 1
    })

    unmount()
    render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-resume-guide")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("watchlists-resume-guide"))
    expect(screen.getByText("Watchlists guided tour")).toBeInTheDocument()
    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument()
    expect(mocks.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "guided_tour_resumed",
      step: 2
    })
  })

  it("shows first-time teach points for jobs/templates and persists dismissal", () => {
    mocks.state.activeTab = "jobs"
    const { rerender } = render(<WatchlistsPlaygroundPage />)

    expect(screen.getByTestId("watchlists-teach-point-title")).toHaveTextContent("Monitor setup tip")
    expect(screen.getByTestId("watchlists-teach-point-description")).toHaveTextContent(
      "Start with schedule presets first. Use cron and advanced filters only after your first successful Activity check."
    )
    fireEvent.click(
      within(screen.getByTestId("watchlists-teach-point-alert")).getByRole("button", { name: "Dismiss" })
    )

    const persisted = JSON.parse(localStorage.getItem("watchlists:teach-points:v1") || "{}")
    expect(persisted.jobsCronFilters).toBe(true)

    rerender(<WatchlistsPlaygroundPage />)
    expect(screen.queryByTestId("watchlists-teach-point-title")).not.toBeInTheDocument()

    mocks.state.activeTab = "templates"
    rerender(<WatchlistsPlaygroundPage />)
    expect(screen.getByTestId("watchlists-teach-point-title")).toHaveTextContent("Template setup tip")
    fireEvent.click(
      within(screen.getByTestId("watchlists-teach-point-alert")).getByRole("button", { name: "Dismiss" })
    )
    const nextPersisted = JSON.parse(localStorage.getItem("watchlists:teach-points:v1") || "{}")
    expect(nextPersisted.templatesAuthoring).toBe(true)
  })

  it("marks guided tour complete and shows completion notice", () => {
    render(<WatchlistsPlaygroundPage />)

    fireEvent.click(screen.getByTestId("watchlists-start-guide"))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Finish" }))

    expect(screen.getByText("Guided tour complete")).toBeInTheDocument()
    const persisted = JSON.parse(localStorage.getItem("watchlists:guided-tour:v1") || "{}")
    expect(persisted.status).toBe("completed")
    expect(mocks.trackWatchlistsOnboardingTelemetryMock).toHaveBeenCalledWith({
      type: "guided_tour_completed"
    })
  })

  it("exposes attention badge labels and passes aria-name baseline checks", async () => {
    mocks.state.overviewHealth = {
      tabBadges: {
        sources: 3,
        runs: 2,
        outputs: 1
      }
    }

    const { container } = render(<WatchlistsPlaygroundPage />)

    expect(screen.getByLabelText("3 attention items")).toBeInTheDocument()
    expect(screen.getByLabelText("2 attention items")).toBeInTheDocument()
    expect(screen.getByLabelText("1 attention items")).toBeInTheDocument()

    const results = await runA11yBaselineRules(container)
    expectNoInvalidAriaViolations(results.violations)
    expect(results.violations.map((violation) => violation.id)).not.toContain("button-name")
    expect(results.violations.map((violation) => violation.id)).not.toContain("link-name")
  }, 15000)
})
