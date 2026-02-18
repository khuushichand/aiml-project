import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { DictionariesManager } from "../Manager"

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches:
      /min-width:\s*576px/.test(query) ||
      /min-width:\s*768px/.test(query) ||
      /min-width:\s*992px/.test(query),
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false
  })
})

if (typeof window.ResizeObserver === "undefined") {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(window as any).ResizeObserver = ResizeObserverMock
  ;(globalThis as any).ResizeObserver = ResizeObserverMock
}

const {
  useQueryMock,
  useMutationMock,
  useQueryClientMock,
  confirmDangerMock,
  notificationMock,
  tldwClientMock,
  storeActions
} = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useMutationMock: vi.fn(),
  useQueryClientMock: vi.fn(),
  confirmDangerMock: vi.fn(async () => true),
  notificationMock: {
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    open: vi.fn(),
    destroy: vi.fn()
  },
  tldwClientMock: {
    initialize: vi.fn(async () => undefined),
    createDictionary: vi.fn(async () => ({ id: 99 })),
    updateDictionary: vi.fn(async () => ({})),
    deleteDictionary: vi.fn(async () => ({})),
    dictionaryStatistics: vi.fn(async () => ({
      dictionary_id: 7,
      name: "Activity Dictionary",
      total_entries: 2,
      regex_entries: 0,
      literal_entries: 2,
      enabled_entries: 2,
      disabled_entries: 0,
      probabilistic_entries: 0,
      timed_effect_entries: 0,
      zero_usage_entries: 0,
      pattern_conflict_count: 0,
      groups: [],
      average_probability: 1,
      created_at: "2026-02-18T10:00:00Z",
      updated_at: "2026-02-18T10:30:00Z",
      last_used: "2026-02-18T11:00:00Z",
      total_usage_count: 2,
      entry_usage: []
    })),
    dictionaryActivity: vi.fn(async () => ({
      dictionary_id: 7,
      total: 1,
      limit: 10,
      offset: 0,
      events: [
        {
          id: 1,
          dictionary_id: 7,
          chat_id: "chat-123",
          entries_used: [11, 12],
          replacements: 2,
          iterations: 1,
          token_budget_used: 320,
          original_text_preview: "foo bar",
          processed_text_preview: "FOO BAR",
          created_at: "2026-02-18T11:00:00Z"
        }
      ]
    }))
  },
  storeActions: {
    setHistoryId: vi.fn(),
    setServerChatId: vi.fn(),
    setServerChatState: vi.fn(),
    setServerChatTitle: vi.fn()
  }
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useMutation: useMutationMock,
  useQueryClient: useQueryClientMock
}))

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

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: false,
    capabilities: {
      hasChatDictionaries: true
    }
  })
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => notificationMock
}))

vi.mock("@/hooks/useUndoNotification", () => ({
  useUndoNotification: () => ({
    showUndoNotification: vi.fn()
  })
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  default: ({ title }: { title: string }) => <div>{title}</div>
}))

vi.mock("@/components/Common/LabelWithHelp", () => ({
  LabelWithHelp: ({ label }: { label: React.ReactNode }) => <span>{label}</span>
}))

vi.mock("@/components/Common/confirm-danger", () => ({
  useConfirmDanger: () => confirmDangerMock
}))

vi.mock("@/store/option", () => ({
  useStoreMessageOption: (selector: any) => {
    const state = {
      setHistoryId: storeActions.setHistoryId,
      setServerChatId: storeActions.setServerChatId,
      setServerChatState: storeActions.setServerChatState,
      setServerChatTitle: storeActions.setServerChatTitle
    }
    return selector ? selector(state) : state
  }
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: tldwClientMock
}))

const makeUseQueryResult = (value: Record<string, any>) => ({
  data: undefined,
  status: "success",
  error: null,
  isPending: false,
  isFetching: false,
  isLoading: false,
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
    } finally {
      opts?.onSettled?.(undefined, undefined, variables, undefined)
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
    } finally {
      opts?.onSettled?.(undefined, undefined, variables, undefined)
    }
  },
  isPending: false
})

describe("DictionariesManager chat integration stage-3", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    useQueryClientMock.mockReturnValue({
      invalidateQueries: vi.fn(),
      setQueryData: vi.fn(),
      getQueryData: vi.fn()
    })
    useMutationMock.mockImplementation((opts: any) => makeUseMutationResult(opts))

    useQueryMock.mockImplementation((opts: any) => {
      const key = Array.isArray(opts?.queryKey) ? opts.queryKey[0] : undefined
      if (key === "tldw:listDictionaries") {
        return makeUseQueryResult({
          status: "success",
          data: [
            {
              id: 7,
              name: "Activity Dictionary",
              description: "Tracks replacements",
              is_active: true,
              default_token_budget: 320,
              entry_count: 2
            }
          ]
        })
      }
      return makeUseQueryResult({})
    })
  })

  it("submits default token budget when creating dictionaries", async () => {
    const user = userEvent.setup()
    render(<DictionariesManager />)

    await user.click(screen.getByRole("button", { name: "New Dictionary" }))
    await user.type(screen.getByRole("textbox", { name: "Name" }), "Clinical Terms")
    await user.type(
      screen.getByRole("spinbutton", { name: "Default Token Budget" }),
      "450"
    )
    await user.click(screen.getByRole("button", { name: "Create" }))

    await waitFor(() => {
      expect(tldwClientMock.createDictionary).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Clinical Terms",
          default_token_budget: 450
        })
      )
    })
  }, 15000)

  it("renders recent activity and default token budget in the statistics modal", async () => {
    const user = userEvent.setup()
    render(<DictionariesManager />)

    await user.click(
      screen.getByRole("button", {
        name: "View statistics for Activity Dictionary"
      })
    )

    await waitFor(() => {
      expect(tldwClientMock.dictionaryStatistics).toHaveBeenCalledWith(7)
    })
    await waitFor(() => {
      expect(tldwClientMock.dictionaryActivity).toHaveBeenCalledWith(7, {
        limit: 10,
        offset: 0
      })
    })

    expect(screen.getByText("Recent activity")).toBeInTheDocument()
    expect(screen.getByText("Chat: chat-123")).toBeInTheDocument()
    expect(screen.getByText("Entries: 11, 12")).toBeInTheDocument()
    expect(screen.getByText("320 tokens")).toBeInTheDocument()
  }, 15000)
})
