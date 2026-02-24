import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { RunsTab } from "../RunsTab"

const STORAGE_KEY = "watchlists:runs:advanced-filters:v1"

const mocks = vi.hoisted(() => ({
  fetchJobRunsMock: vi.fn(),
  exportRunsCsvMock: vi.fn(),
  fetchWatchlistJobsMock: vi.fn(),
  fetchWatchlistRunsMock: vi.fn(),
  storeStateRef: { current: {} as Record<string, any> }
}))

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
  const Select = ({ value, onChange, options = [], allowClear, ...rest }: any) => (
    <select
      data-testid={rest["data-testid"] || "antd-select"}
      value={value == null ? "" : String(value)}
      onChange={(event) => {
        const next = event.currentTarget.value
        onChange?.(next === "" ? null : next)
      }}
    >
      {allowClear ? <option value="" /> : null}
      {options.map((option: any) => (
        <option key={String(option.value)} value={String(option.value)} disabled={Boolean(option.disabled)}>
          {String(option.label)}
        </option>
      ))}
    </select>
  )

  const Button = ({ children, onClick, loading, ...rest }: any) => (
    <button type="button" disabled={Boolean(loading)} onClick={() => onClick?.()} {...rest}>
      {children}
    </button>
  )

  const Dropdown = ({ children }: any) => <>{children}</>
  const Table = ({ dataSource = [] }: any) => (
    <table data-testid="runs-table">
      <tbody>
        {dataSource.map((record: any) => (
          <tr key={String(record.id)}>
            <td>{String(record.id)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
  const Progress = () => <div />
  const Tooltip = ({ children }: any) => <>{children}</>
  const Space = ({ children }: any) => <>{children}</>
  const Alert = ({ title, description, action }: any) => (
    <div>
      <div>{title}</div>
      <div>{description}</div>
      {action}
    </div>
  )

  return {
    Select,
    Button,
    Dropdown,
    Table,
    Progress,
    Tooltip,
    Space,
    Alert,
    message: {
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

vi.mock("@/utils/dateFormatters", () => ({
  formatRelativeTime: () => "just now"
}))

vi.mock("@/services/watchlists", () => ({
  fetchJobRuns: (...args: any[]) => mocks.fetchJobRunsMock(...args),
  exportRunsCsv: (...args: any[]) => mocks.exportRunsCsvMock(...args),
  fetchWatchlistJobs: (...args: any[]) => mocks.fetchWatchlistJobsMock(...args),
  fetchWatchlistRuns: (...args: any[]) => mocks.fetchWatchlistRunsMock(...args)
}))

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: any) => unknown) => selector(mocks.storeStateRef.current)
}))

vi.mock("../RunDetailDrawer", () => ({
  RunDetailDrawer: () => null
}))

const baseState = (overrides: Record<string, unknown> = {}) => ({
  runs: [],
  runsLoading: false,
  runsTotal: 0,
  runsPage: 1,
  runsPageSize: 20,
  runsJobFilter: null,
  runsStatusFilter: null,
  pollingActive: false,
  runDetailOpen: false,
  selectedRunId: null,
  setRuns: vi.fn(),
  setRunsLoading: vi.fn(),
  setRunsPage: vi.fn(),
  setRunsPageSize: vi.fn(),
  setRunsJobFilter: vi.fn(),
  setRunsStatusFilter: vi.fn(),
  setPollingActive: vi.fn(),
  openRunDetail: vi.fn(),
  closeRunDetail: vi.fn(),
  updateRunInList: vi.fn(),
  ...overrides
})

const buildRun = (id: number) => ({
  id,
  job_id: id % 5 ? 1 : 2,
  status: id % 4 === 0 ? "completed" : "running",
  started_at: "2026-02-18T00:00:00Z",
  finished_at: null,
  stats: {
    items_found: 12,
    items_ingested: 8,
    items_filtered: 3,
    items_errored: 1
  }
})

describe("RunsTab advanced filters disclosure", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem(STORAGE_KEY)
    mocks.storeStateRef.current = baseState()
    mocks.fetchWatchlistRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.fetchJobRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.fetchWatchlistJobsMock.mockResolvedValue({ items: [{ id: 1, name: "Daily Monitor" }], total: 1, has_more: false })
    mocks.exportRunsCsvMock.mockResolvedValue("")
  })

  it("starts collapsed, toggles open, and persists disclosure state", async () => {
    render(<RunsTab />)

    expect(screen.queryByTestId("watchlists-runs-job-filter")).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId("watchlists-runs-advanced-toggle"))
    expect(screen.getByTestId("watchlists-runs-job-filter")).toBeInTheDocument()

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBe("1")
    })
  })

  it("auto-opens when active filters exist", () => {
    mocks.storeStateRef.current = baseState({ runsJobFilter: 1 })

    render(<RunsTab />)

    expect(screen.getByTestId("watchlists-runs-job-filter")).toBeInTheDocument()
  })

  it("renders high-density activity tables while keeping filters responsive", () => {
    const runs = Array.from({ length: 500 }, (_value, index) => buildRun(index + 1))
    mocks.storeStateRef.current = baseState({
      runs,
      runsTotal: runs.length
    })

    const { container } = render(<RunsTab />)

    expect(screen.getByTestId("watchlists-runs-advanced-toggle")).toBeInTheDocument()
    expect(container.querySelectorAll("tr").length).toBe(500)
  })
})
