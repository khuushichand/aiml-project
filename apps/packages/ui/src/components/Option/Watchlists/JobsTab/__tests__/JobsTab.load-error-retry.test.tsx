import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { JobsTab } from "../JobsTab"

const mocks = vi.hoisted(() => ({
  fetchWatchlistJobsMock: vi.fn(),
  fetchWatchlistSourcesMock: vi.fn(),
  fetchWatchlistGroupsMock: vi.fn(),
  createWatchlistJobMock: vi.fn(),
  updateWatchlistJobMock: vi.fn(),
  deleteWatchlistJobMock: vi.fn(),
  restoreWatchlistJobMock: vi.fn(),
  triggerWatchlistRunMock: vi.fn(),
  storeStateRef: { current: {} as Record<string, any> },
  tMock: (key: string, defaultValue?: unknown, options?: Record<string, unknown>) => {
    if (typeof defaultValue !== "string") return key
    if (!options) return defaultValue
    return defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) => String(options[token] ?? ""))
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: mocks.tMock
  })
}))

vi.mock("antd", () => {
  const Button = ({ children, onClick, loading, ...rest }: any) => (
    <button
      type="button"
      disabled={Boolean(loading)}
      onClick={() => onClick?.()}
      {...rest}
    >
      {children}
    </button>
  )

  const Table = ({ "aria-label": ariaLabel }: any) => (
    <div data-testid="jobs-table" role="table" aria-label={ariaLabel} />
  )
  const Popconfirm = ({ children }: any) => <>{children}</>
  const Space = ({ children }: any) => <>{children}</>
  const Switch = () => <button type="button">switch</button>
  const Tag = ({ children }: any) => <span>{children}</span>
  const Tooltip = ({ children }: any) => <>{children}</>
  const Alert = ({ title, description, action }: any) => (
    <div>
      <div>{title}</div>
      <div>{description}</div>
      {action}
    </div>
  )

  return {
    Button,
    Table,
    Popconfirm,
    Space,
    Switch,
    Tag,
    Tooltip,
    Alert,
    message: {
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => ({
    showUndoNotification: vi.fn()
  })
}))

vi.mock("@/utils/dateFormatters", () => ({
  formatRelativeTime: () => "just now"
}))

vi.mock("@/services/watchlists", () => ({
  createWatchlistJob: (...args: any[]) => mocks.createWatchlistJobMock(...args),
  deleteWatchlistJob: (...args: any[]) => mocks.deleteWatchlistJobMock(...args),
  fetchWatchlistGroups: (...args: any[]) => mocks.fetchWatchlistGroupsMock(...args),
  fetchWatchlistJobs: (...args: any[]) => mocks.fetchWatchlistJobsMock(...args),
  fetchWatchlistSources: (...args: any[]) => mocks.fetchWatchlistSourcesMock(...args),
  restoreWatchlistJob: (...args: any[]) => mocks.restoreWatchlistJobMock(...args),
  triggerWatchlistRun: (...args: any[]) => mocks.triggerWatchlistRunMock(...args),
  updateWatchlistJob: (...args: any[]) => mocks.updateWatchlistJobMock(...args)
}))

vi.mock("@/store/watchlists", () => ({
  useWatchlistsStore: (selector: (state: any) => unknown) =>
    selector(mocks.storeStateRef.current)
}))

vi.mock("../JobFormModal", () => ({
  JobFormModal: () => null
}))

vi.mock("../JobPreviewModal", () => ({
  JobPreviewModal: () => null
}))

const baseState = (overrides: Record<string, unknown> = {}) => ({
  jobs: [],
  jobsLoading: false,
  jobsTotal: 0,
  jobsPage: 1,
  jobsPageSize: 20,
  jobFormOpen: false,
  jobFormEditId: null,
  setJobs: vi.fn(),
  setJobsLoading: vi.fn(),
  setJobsPage: vi.fn(),
  setJobsPageSize: vi.fn(),
  openJobForm: vi.fn(),
  closeJobForm: vi.fn(),
  addJob: vi.fn(),
  updateJobInList: vi.fn(),
  removeJob: vi.fn(),
  addRun: vi.fn(),
  ...overrides
})

describe("JobsTab load-error retry", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.storeStateRef.current = baseState()
    mocks.fetchWatchlistGroupsMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.fetchWatchlistSourcesMock.mockResolvedValue({ items: [], total: 0, has_more: false })
    mocks.createWatchlistJobMock.mockResolvedValue({})
    mocks.updateWatchlistJobMock.mockResolvedValue({})
    mocks.deleteWatchlistJobMock.mockResolvedValue({})
    mocks.restoreWatchlistJobMock.mockResolvedValue({})
    mocks.triggerWatchlistRunMock.mockResolvedValue({})
  })

  it("renders contextual load error and retries monitor load", async () => {
    mocks.fetchWatchlistJobsMock
      .mockRejectedValueOnce(new Error("Failed to fetch"))
      .mockResolvedValueOnce({ items: [], total: 0, has_more: false })

    render(<JobsTab />)

    expect(screen.getByRole("table", { name: "Monitors table" })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText("Could not load Monitors.")).toBeInTheDocument()
      expect(screen.getByText("Check server connection and try again. Details: Failed to fetch")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => {
      expect(mocks.fetchWatchlistJobsMock).toHaveBeenCalledTimes(2)
    })
  })
})
