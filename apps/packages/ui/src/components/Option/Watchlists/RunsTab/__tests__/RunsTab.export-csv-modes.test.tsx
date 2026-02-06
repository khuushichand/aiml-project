import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { RunsTab } from "../RunsTab"

const fetchJobRunsMock = vi.fn()
const exportRunsCsvMock = vi.fn()
const fetchWatchlistJobsMock = vi.fn()
const fetchWatchlistRunsMock = vi.fn()
const messageSuccessMock = vi.fn()
const messageWarningMock = vi.fn()
const messageErrorMock = vi.fn()

let storeState: Record<string, any> = {}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown) => {
      if (typeof defaultValue === "string") return defaultValue
      if (
        defaultValue &&
        typeof defaultValue === "object" &&
        "defaultValue" in (defaultValue as Record<string, unknown>)
      ) {
        const text = (defaultValue as Record<string, unknown>).defaultValue
        if (typeof text === "string") return text
      }
      return _key
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
        <option
          key={String(option.value)}
          value={String(option.value)}
          disabled={Boolean(option.disabled)}
        >
          {String(option.label)}
        </option>
      ))}
    </select>
  )

  const Button = ({ children, onClick, loading }: any) => (
    <button type="button" disabled={Boolean(loading)} onClick={() => onClick?.()}>
      {children}
    </button>
  )

  const Table = () => <div data-testid="runs-table" />
  const Progress = () => <div />
  const Tooltip = ({ children }: any) => <>{children}</>
  const Space = ({ children }: any) => <>{children}</>
  const Tag = ({ children }: any) => <span>{children}</span>

  return {
    Select,
    Button,
    Table,
    Progress,
    Tooltip,
    Space,
    Tag,
    message: {
      success: messageSuccessMock,
      warning: messageWarningMock,
      error: messageErrorMock,
    },
  }
})

vi.mock("@/utils/dateFormatters", () => ({
  formatRelativeTime: () => "just now"
}))

vi.mock("@/services/watchlists", () => ({
  fetchJobRuns: (...args: any[]) => fetchJobRunsMock(...args),
  exportRunsCsv: (...args: any[]) => exportRunsCsvMock(...args),
  fetchWatchlistJobs: (...args: any[]) => fetchWatchlistJobsMock(...args),
  fetchWatchlistRuns: (...args: any[]) => fetchWatchlistRunsMock(...args)
}))

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: any) => unknown) => selector(storeState)
}))

vi.mock("@/components/Option/Watchlists/RunsTab/RunDetailDrawer", () => ({
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
  ...overrides,
})

describe("RunsTab CSV export modes", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storeState = baseState()
    fetchWatchlistRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    fetchJobRunsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    fetchWatchlistJobsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    exportRunsCsvMock.mockResolvedValue("filter_key,count\nkw:alpha,2\n")

    if (typeof URL.createObjectURL !== "function") {
      Object.defineProperty(URL, "createObjectURL", {
        configurable: true,
        value: vi.fn(() => "blob:mock"),
      })
    } else {
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock")
    }
    if (typeof URL.revokeObjectURL !== "function") {
      Object.defineProperty(URL, "revokeObjectURL", {
        configurable: true,
        value: vi.fn(),
      })
    } else {
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {})
    }
  })

  it("requests global aggregate tallies CSV when aggregate mode is selected", async () => {
    render(<RunsTab />)

    fireEvent.change(screen.getByTestId("runs-csv-tallies-mode"), {
      target: { value: "aggregate" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }))

    await waitFor(() => {
      expect(exportRunsCsvMock).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "global",
          include_tallies: true,
          tallies_mode: "aggregate"
        })
      )
    })
  })

  it("requests per-run tallies CSV for job scope when per-run mode is selected", async () => {
    storeState = baseState({ runsJobFilter: 42 })
    exportRunsCsvMock.mockResolvedValue(
      "id,job_id,status,started_at,finished_at,items_found,items_ingested,filters_include,filters_exclude,filters_flag,filter_tallies_json\n"
    )

    render(<RunsTab />)

    fireEvent.change(screen.getByTestId("runs-csv-tallies-mode"), {
      target: { value: "per_run" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }))

    await waitFor(() => {
      expect(exportRunsCsvMock).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: "job",
          job_id: 42,
          include_tallies: true,
          tallies_mode: "per_run"
        })
      )
    })
  })
})

