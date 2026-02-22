import { render, screen } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { DataTablesList } from "../DataTablesList"

const {
  useQueryMock,
  useQueryClientMock,
  invalidateQueriesMock,
  listState
} = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useQueryClientMock: vi.fn(),
  invalidateQueriesMock: vi.fn(),
  listState: {
    tablesPage: 1,
    tablesPageSize: 20,
    tablesSearch: "",
    selectedTableId: null,
    tableDetailOpen: false,
    deleteConfirmOpen: false,
    deleteTargetId: null,
    setTablesPage: vi.fn(),
    setTablesSearch: vi.fn(),
    openTableDetail: vi.fn(),
    closeTableDetail: vi.fn(),
    openDeleteConfirm: vi.fn(),
    closeDeleteConfirm: vi.fn()
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@tanstack/react-query", () => ({
  keepPreviousData: Symbol("keepPreviousData"),
  useQuery: useQueryMock,
  useQueryClient: useQueryClientMock
}))

vi.mock("@/store/data-tables", () => ({
  useDataTablesStore: (selector: (state: typeof listState) => unknown) =>
    selector(listState)
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    deleteDataTable: vi.fn(),
    exportDataTable: vi.fn(),
    listDataTables: vi.fn()
  }
}))

vi.mock("@/utils/download-blob", () => ({
  downloadBlob: vi.fn()
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("DataTablesList action control accessibility", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    if (typeof window.matchMedia !== "function") {
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
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(useQueryClient).mockReturnValue({
      invalidateQueries: invalidateQueriesMock
    } as any)

    vi.mocked(useQuery).mockReturnValue({
      data: {
        tables: [
          {
            id: "table-1",
            name: "Monthly KPIs",
            row_count: 25,
            column_count: 4,
            source_count: 2,
            created_at: "2026-02-17T12:00:00.000Z",
            updated_at: "2026-02-17T12:00:00.000Z"
          }
        ],
        total: 1,
        page: 1,
        page_size: 20,
        pages: 1
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn()
    } as any)
  })

  it("renders icon-only row actions with labels and 44x44 touch targets", () => {
    render(<DataTablesList />)

    const viewButton = screen.getByRole("button", { name: "View" })
    const exportButton = screen.getByRole("button", { name: "Export" })
    const deleteButton = screen.getByRole("button", { name: "Delete" })

    expect(viewButton).toHaveClass("min-h-[44px]")
    expect(viewButton).toHaveClass("min-w-[44px]")
    expect(viewButton).toHaveClass("md:min-h-[32px]")
    expect(viewButton).toHaveClass("md:min-w-[32px]")

    expect(exportButton).toHaveClass("min-h-[44px]")
    expect(exportButton).toHaveClass("min-w-[44px]")
    expect(exportButton).toHaveClass("md:min-h-[32px]")
    expect(exportButton).toHaveClass("md:min-w-[32px]")

    expect(deleteButton).toHaveClass("min-h-[44px]")
    expect(deleteButton).toHaveClass("min-w-[44px]")
    expect(deleteButton).toHaveClass("md:min-h-[32px]")
    expect(deleteButton).toHaveClass("md:min-w-[32px]")
  })
})
