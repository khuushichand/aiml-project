import React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { WorldBooksManager } from "../Manager"

const {
  useQueryMock,
  useMutationMock,
  useQueryClientMock,
  notificationMock,
  undoNotificationMock,
  confirmDangerMock,
  tldwClientMock,
  mockBreakpoints
} = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useMutationMock: vi.fn(),
  useQueryClientMock: vi.fn(),
  notificationMock: {
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    open: vi.fn(),
    destroy: vi.fn()
  },
  undoNotificationMock: {
    showUndoNotification: vi.fn()
  },
  confirmDangerMock: vi.fn(async () => true),
  tldwClientMock: {
    initialize: vi.fn(async () => undefined),
    createWorldBook: vi.fn(async () => ({ id: 1 })),
    updateWorldBook: vi.fn(async () => ({})),
    deleteWorldBook: vi.fn(async () => ({})),
    listCharacters: vi.fn(async () => []),
    listCharacterWorldBooks: vi.fn(async () => []),
    listWorldBookEntries: vi.fn(async () => ({ entries: [] })),
    addWorldBookEntry: vi.fn(async () => ({})),
    updateWorldBookEntry: vi.fn(async () => ({})),
    deleteWorldBookEntry: vi.fn(async () => ({})),
    bulkWorldBookEntries: vi.fn(async () => ({ success: true, affected_count: 0, failed_ids: [] })),
    exportWorldBook: vi.fn(async () => ({})),
    worldBookStatistics: vi.fn(async () => ({})),
    importWorldBook: vi.fn(async () => ({})),
    attachWorldBookToCharacter: vi.fn(async () => ({})),
    detachWorldBookFromCharacter: vi.fn(async () => ({}))
  },
  mockBreakpoints: { md: true }
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useMutation: useMutationMock,
  useQueryClient: useQueryClientMock
}))

vi.mock("antd", async (importOriginal) => {
  const actual = await importOriginal<typeof import("antd")>()
  return {
    ...actual,
    Grid: {
      ...actual.Grid,
      useBreakpoint: () => mockBreakpoints
    }
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => notificationMock
}))

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => undoNotificationMock
}))

vi.mock("@/components/Common/confirm-danger", () => ({
  useConfirmDanger: () => confirmDangerMock
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: tldwClientMock
}))

const makeUseQueryResult = (value: Record<string, any>) => ({
  data: null,
  status: "success",
  isLoading: false,
  isFetching: false,
  isPending: false,
  error: null,
  refetch: vi.fn(),
  ...value
})

const makeUseMutationResult = (opts: any) => ({
  mutate: async (variables: any) => {
    try {
      const result = await opts?.mutationFn?.(variables)
      opts?.onSuccess?.(result, variables, undefined)
      return result
    } catch (error) {
      opts?.onError?.(error, variables, undefined)
      throw error
    }
  },
  mutateAsync: async (variables: any) => {
    try {
      const result = await opts?.mutationFn?.(variables)
      opts?.onSuccess?.(result, variables, undefined)
      return result
    } catch (error) {
      opts?.onError?.(error, variables, undefined)
      throw error
    }
  },
  isPending: false
})

const worldBooks = [
  {
    id: 1,
    name: "Arcana",
    description: "Main lore",
    enabled: true,
    entry_count: 1
  },
  {
    id: 2,
    name: "Bestiary",
    description: "Creature lore",
    enabled: true,
    entry_count: 1
  }
]

const characters = [
  { id: 1, name: "Alice" },
  { id: 2, name: "Bob" }
]

const entryData = [
  {
    entry_id: 1,
    keywords: ["castle"],
    content: "Castle historical facts.",
    priority: 60,
    enabled: true,
    case_sensitive: false,
    regex_match: false,
    whole_word_match: true,
    appendable: false
  }
]

describe("WorldBooksManager accessibility stage-3 focus and matrix keyboard behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockBreakpoints.md = true

    useQueryClientMock.mockReturnValue({
      invalidateQueries: vi.fn()
    })

    useMutationMock.mockImplementation((opts: any) => makeUseMutationResult(opts))
    useQueryMock.mockImplementation((opts: any) => {
      const queryKey = Array.isArray(opts?.queryKey) ? opts.queryKey : []
      const key = queryKey[0]

      if (key === "tldw:listWorldBooks") {
        return makeUseQueryResult({ data: worldBooks, status: "success" })
      }
      if (key === "tldw:listCharactersForWB") {
        return makeUseQueryResult({ data: characters, status: "success" })
      }
      if (key === "tldw:worldBookAttachments") {
        return makeUseQueryResult({
          data: {
            1: [{ id: 1, name: "Alice" }],
            2: [{ id: 2, name: "Bob" }]
          },
          isLoading: false
        })
      }
      if (key === "tldw:listWorldBookEntries") {
        return makeUseQueryResult({ data: entryData, status: "success" })
      }
      if (key === "tldw:worldBookRuntimeConfig") {
        return makeUseQueryResult({ data: { max_recursive_depth: 10 }, status: "success" })
      }
      return makeUseQueryResult({})
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("returns focus to Manage Entries trigger after closing the drawer", async () => {
    const user = userEvent.setup()
    render(<WorldBooksManager />)

    const manageEntriesButtons = await screen.findAllByRole("button", {
      name: "Manage entries"
    })
    const manageEntriesButton = manageEntriesButtons[0]
    manageEntriesButton.focus()
    await user.click(manageEntriesButton)

    expect(await screen.findByText("World Books > Arcana > Entries")).toBeInTheDocument()

    const closeDrawerButton = document.querySelector<HTMLButtonElement>(".ant-drawer-close")
    expect(closeDrawerButton).not.toBeNull()
    await user.click(closeDrawerButton as HTMLButtonElement)

    await waitFor(() => {
      expect(screen.queryByText("World Books > Arcana > Entries")).not.toBeInTheDocument()
    })
    await waitFor(() => {
      expect(manageEntriesButton).toHaveFocus()
    })
  }, 30000)

  it("returns focus to matrix trigger after closing the matrix modal", async () => {
    render(<WorldBooksManager />)

    const matrixButton = await screen.findByRole("button", {
      name: "Open relationship matrix"
    })
    matrixButton.focus()
    fireEvent.click(matrixButton)

    expect(await screen.findByText("Matrix view active (2 characters).")).toBeInTheDocument()

    const closeMatrixButton = document.querySelector<HTMLButtonElement>(".ant-modal-close")
    expect(closeMatrixButton).not.toBeNull()
    fireEvent.click(closeMatrixButton as HTMLButtonElement)

    await waitFor(() => {
      expect(matrixButton).toHaveFocus()
    })
  }, 30000)

  it("supports arrow-key navigation across matrix attachment cells", async () => {
    const user = userEvent.setup()
    render(<WorldBooksManager />)

    await user.click(
      await screen.findByRole("button", { name: "Open relationship matrix" })
    )
    expect(await screen.findByText("Matrix view active (2 characters).")).toBeInTheDocument()

    const arcanaAlice = screen.getByLabelText("Toggle attachment Arcana / Alice")
    const arcanaBob = screen.getByLabelText("Toggle attachment Arcana / Bob")
    const bestiaryBob = screen.getByLabelText("Toggle attachment Bestiary / Bob")

    arcanaAlice.focus()
    fireEvent.keyDown(arcanaAlice, { key: "ArrowRight" })
    expect(arcanaBob).toHaveFocus()

    fireEvent.keyDown(arcanaBob, { key: "ArrowDown" })
    expect(bestiaryBob).toHaveFocus()
  }, 30000)
})
