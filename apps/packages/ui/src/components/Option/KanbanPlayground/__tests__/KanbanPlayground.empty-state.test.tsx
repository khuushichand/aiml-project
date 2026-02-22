import { render, screen } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { KanbanPlayground } from "../index"

const { useQueryMock, useMutationMock, useQueryClientMock } = vi.hoisted(
  () => ({
    useQueryMock: vi.fn(),
    useMutationMock: vi.fn(),
    useQueryClientMock: vi.fn()
  })
)

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useMutation: useMutationMock,
  useQueryClient: useQueryClientMock
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue ?? _key
  })
}))

vi.mock("@/services/kanban", () => ({
  listBoards: vi.fn(),
  getBoard: vi.fn(),
  createBoard: vi.fn(),
  deleteBoard: vi.fn(),
  generateClientId: vi.fn(() => "test-client-id")
}))

vi.mock("../BoardView", () => ({
  BoardView: () => <div>Board View</div>
}))

vi.mock("../ImportPanel", () => ({
  ImportPanel: () => <div>Import Panel</div>
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("KanbanPlayground empty-state copy", () => {
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
      invalidateQueries: vi.fn()
    } as any)
    vi.mocked(useMutation).mockReturnValue({
      mutate: vi.fn(),
      isPending: false
    } as any)
  })

  const mockQueryResponses = (boardsCount: number) => {
    const boards = Array.from({ length: boardsCount }, (_, index) => ({
      id: index + 1,
      name: `Board ${index + 1}`
    }))

    vi.mocked(useQuery).mockImplementation((options: any) => {
      const queryKey = Array.isArray(options?.queryKey) ? options.queryKey : []
      if (queryKey[0] === "kanban-boards") {
        return {
          data: { boards },
          isLoading: false,
          refetch: vi.fn()
        } as any
      }
      if (queryKey[0] === "kanban-board") {
        return {
          data: null,
          isLoading: false,
          refetch: vi.fn()
        } as any
      }
      return {
        data: null,
        isLoading: false,
        refetch: vi.fn()
      } as any
    })
  }

  it("shows first-time guidance when there are no boards", () => {
    mockQueryResponses(0)
    render(<KanbanPlayground />)

    expect(
      screen.getByText("No boards yet. Create your first board")
    ).toBeInTheDocument()
  })

  it("shows selection guidance when boards already exist", () => {
    mockQueryResponses(1)
    render(<KanbanPlayground />)

    expect(
      screen.getByText("Select an existing board to get started")
    ).toBeInTheDocument()
  })
})
