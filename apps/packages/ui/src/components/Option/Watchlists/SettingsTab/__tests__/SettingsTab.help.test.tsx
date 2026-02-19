import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SettingsTab } from "../SettingsTab"
import { WATCHLISTS_HELP_DOCS } from "../../shared/help-docs"

const mocks = vi.hoisted(() => ({
  getWatchlistSettingsMock: vi.fn(),
  fetchWatchlistJobsMock: vi.fn(),
  fetchClaimClustersMock: vi.fn(),
  fetchJobClaimClustersMock: vi.fn(),
  subscribeJobToClusterMock: vi.fn(),
  unsubscribeJobFromClusterMock: vi.fn(),
  messageErrorMock: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown) =>
      typeof defaultValue === "string" ? defaultValue : _key
  })
}))

vi.mock("antd", () => {
  const Button = ({ children, onClick, loading: _loading, ...rest }: any) => (
    <button type="button" {...rest} onClick={() => onClick?.()}>
      {children}
    </button>
  )
  const Card = ({ title, children }: any) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  )
  const DescriptionsComponent = ({ children }: any) => <div>{children}</div>
  ;(DescriptionsComponent as any).Item = ({ label, children }: any) => (
    <div>
      <strong>{label}</strong>
      <span>{children}</span>
    </div>
  )
  const Input = {
    Search: ({ value, onChange, onSearch }: any) => (
      <input
        value={value || ""}
        onChange={(event) => onChange?.(event)}
        onKeyDown={(event) => {
          if (event.key === "Enter") onSearch?.(value)
        }}
      />
    )
  }
  const Select = ({ options = [], value, onChange }: any) => (
    <select
      value={value ?? ""}
      onChange={(event) => onChange?.(event.currentTarget.value || null)}
    >
      <option value="" />
      {options.map((option: any) => (
        <option key={String(option.value)} value={String(option.value)}>
          {String(option.label)}
        </option>
      ))}
    </select>
  )
  const Skeleton = () => <div>Loading...</div>
  const Switch = () => null
  const Table = ({ dataSource = [] }: any) => <div>{dataSource.length}</div>
  const Tooltip = ({ title, children }: any) => (
    <div>
      {children}
      {title}
    </div>
  )

  return {
    Alert: ({ title, description }: any) => (
      <div>
        <div>{title}</div>
        <div>{description}</div>
      </div>
    ),
    Button,
    Card,
    Descriptions: DescriptionsComponent,
    Empty: ({ description }: any) => <div>{description}</div>,
    Input,
    Select,
    Skeleton,
    Switch,
    Table,
    Tooltip,
    message: {
      error: mocks.messageErrorMock,
      success: vi.fn(),
      warning: vi.fn()
    }
  }
})

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: Record<string, any>) => unknown) =>
    selector({
      settings: {
        default_output_ttl_seconds: 86400,
        temporary_output_ttl_seconds: 3600
      },
      settingsLoading: false,
      setSettings: vi.fn(),
      setSettingsLoading: vi.fn()
    })
}))

vi.mock("@/services/watchlists", () => ({
  fetchClaimClusters: (...args: any[]) => mocks.fetchClaimClustersMock(...args),
  fetchJobClaimClusters: (...args: any[]) => mocks.fetchJobClaimClustersMock(...args),
  fetchWatchlistJobs: (...args: any[]) => mocks.fetchWatchlistJobsMock(...args),
  getWatchlistSettings: (...args: any[]) => mocks.getWatchlistSettingsMock(...args),
  subscribeJobToCluster: (...args: any[]) => mocks.subscribeJobToClusterMock(...args),
  unsubscribeJobFromCluster: (...args: any[]) => mocks.unsubscribeJobFromClusterMock(...args)
}))

vi.mock("@/utils/humanize-milliseconds", () => ({
  humanizeMilliseconds: (value: number) => `${value} ms`
}))

vi.mock("@/utils/dateFormatters", () => ({
  formatRelativeTime: () => "just now"
}))

describe("SettingsTab contextual help", () => {
  const originalDiagnosticsFlag = process.env.NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS

  beforeEach(() => {
    vi.clearAllMocks()
    delete process.env.NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS
    mocks.getWatchlistSettingsMock.mockResolvedValue({
      default_output_ttl_seconds: 86400,
      temporary_output_ttl_seconds: 3600
    })
    mocks.fetchWatchlistJobsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.fetchClaimClustersMock.mockResolvedValue([])
    mocks.fetchJobClaimClustersMock.mockResolvedValue([])
    mocks.subscribeJobToClusterMock.mockResolvedValue(undefined)
    mocks.unsubscribeJobFromClusterMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    if (originalDiagnosticsFlag == null) {
      delete process.env.NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS
      return
    }
    process.env.NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS = originalDiagnosticsFlag
  })

  it("shows claim cluster explanation with docs link and help trigger", async () => {
    render(<SettingsTab />)

    await waitFor(() => {
      expect(
        screen.getByText("Related Topics (Claim Clusters)")
      ).toBeInTheDocument()
    })

    expect(screen.getByTestId("watchlists-help-claimClusters")).toBeInTheDocument()
    const links = screen.getAllByRole("link", { name: "Learn more" })
    expect(
      links.some((link) => link.getAttribute("href") === WATCHLISTS_HELP_DOCS.claimClusters)
    ).toBe(true)
  })

  it("hides internal diagnostics by default", async () => {
    render(<SettingsTab />)

    await waitFor(() => {
      expect(
        screen.getByText("Related Topics (Claim Clusters)")
      ).toBeInTheDocument()
    })

    expect(screen.queryByText("Internal diagnostics")).not.toBeInTheDocument()
    expect(screen.queryByText("Phase 3 Readiness")).not.toBeInTheDocument()
  })

  it("shows internal diagnostics when explicitly enabled", async () => {
    process.env.NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS = "true"
    render(<SettingsTab />)

    await waitFor(() => {
      expect(screen.getByText("Internal diagnostics")).toBeInTheDocument()
    })
  })
})
