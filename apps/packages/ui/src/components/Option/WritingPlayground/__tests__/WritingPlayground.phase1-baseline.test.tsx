import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockState = vi.hoisted(() => ({
  storageValues: new Map<string, unknown>(),
  queryData: new Map<string, unknown>(),
  resolveApiProviderForModel: vi.fn(async () => null as string | null),
  streamCalls: [] as Array<{ messages: unknown[]; options: Record<string, unknown> }>,
  sendCalls: [] as Array<{ messages: unknown[]; options: Record<string, unknown> }>
}))

vi.mock("@tanstack/react-query", () => {
  const resolveQueryData = (queryKey: unknown): unknown => {
    const key = Array.isArray(queryKey) ? queryKey[0] : queryKey
    if (key === "writing-session" && Array.isArray(queryKey)) {
      return mockState.queryData.get(
        `writing-session:${String(queryKey[1] || "")}`
      )
    }
    return mockState.queryData.get(String(key))
  }

  return {
    useQuery: ({ queryKey }: { queryKey: unknown }) => ({
      data: resolveQueryData(queryKey),
      isLoading: false,
      isFetching: false,
      error: null
    }),
    useMutation: () => ({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false
    }),
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
      setQueryData: vi.fn()
    })
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) return fallbackOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@plasmohq/storage/hook", () => {
  return {
    useStorage: <T,>(key: string, initial?: T) =>
      React.useState<T | undefined>(() =>
        mockState.storageValues.has(key)
          ? (mockState.storageValues.get(key) as T)
          : initial
      )
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasChat: true },
    loading: false,
    refresh: async () => {}
  })
}))

vi.mock("@/utils/resolve-api-provider", () => ({
  AUTO_MODEL_ID: "auto",
  resolveApiProviderForModel: mockState.resolveApiProviderForModel
}))

vi.mock("@/components/Common/MarkdownPreview", () => ({
  MarkdownPreview: ({ content }: { content: string }) => <div>{content}</div>
}))

vi.mock("@/services/tldw/TldwChat", () => ({
  TldwChatService: class TldwChatServiceMock {
    cancelStream() {}
    async *streamMessage(
      messages: unknown[],
      options: Record<string, unknown>
    ) {
      mockState.streamCalls.push({ messages, options })
      yield "mocked stream token"
    }
    async sendMessage(messages: unknown[], options: Record<string, unknown>) {
      mockState.sendCalls.push({ messages, options })
      return "mocked completion"
    }
  }
}))

vi.mock("@/services/writing-playground", () => ({
  cloneWritingSession: vi.fn(),
  createWritingSession: vi.fn(),
  createWritingTemplate: vi.fn(),
  createWritingTheme: vi.fn(),
  createWritingWordcloud: vi.fn(),
  countWritingTokens: vi.fn(),
  deleteWritingSession: vi.fn(),
  deleteWritingTemplate: vi.fn(),
  deleteWritingTheme: vi.fn(),
  exportWritingSnapshot: vi.fn(),
  getWritingCapabilities: vi.fn(),
  getWritingDefaults: vi.fn(),
  getWritingWordcloud: vi.fn(),
  getWritingSession: vi.fn(),
  importWritingSnapshot: vi.fn(),
  listWritingSessions: vi.fn(),
  listWritingTemplates: vi.fn(),
  listWritingThemes: vi.fn(),
  tokenizeWritingText: vi.fn(),
  updateWritingSession: vi.fn(),
  updateWritingTemplate: vi.fn(),
  updateWritingTheme: vi.fn()
}))

import { WritingPlayground } from "../index"
import { useWritingPlaygroundStore } from "@/store/writing-playground"

const DEFAULT_WRITING_CAPABILITIES = {
  server: {
    sessions: true,
    templates: true,
    themes: true,
    defaults_catalog: false,
    snapshots: false,
    tokenize: true,
    token_count: true
  },
  requested: {
    provider: "openai",
    tokenizer_available: true,
    tokenizer: "mock-tokenizer",
    tokenizer_kind: "mock",
    tokenizer_source: "mock",
    detokenize_available: true,
    features: {
      logprobs: true
    },
    supported_fields: ["top_logprobs"],
    extra_body_compat: {
      effective: true,
      source: "mock",
      notes: "mock"
    }
  }
}

const seedWritingSession = () => {
  useWritingPlaygroundStore.setState({
    activeSessionId: "session-auto",
    activeSessionName: "Auto Session"
  })
  mockState.queryData.set("writing-sessions", {
    sessions: [
      {
        id: "session-auto",
        name: "Auto Session",
        last_modified: "2026-03-16T12:00:00Z",
        version: 1
      }
    ],
    total: 1,
    limit: 200,
    offset: 0
  })
  mockState.queryData.set("writing-session:session-auto", {
    id: "session-auto",
    name: "Auto Session",
    payload: {
      prompt: "Seed prompt",
      settings: {},
      template_name: null,
      theme_name: null,
      chat_mode: false
    },
    schema_version: 1,
    version_parent_id: null,
    created_at: "2026-03-16T12:00:00Z",
    last_modified: "2026-03-16T12:00:00Z",
    deleted: false,
    client_id: "test-client",
    version: 1
  })
}

beforeEach(() => {
  mockState.storageValues.clear()
  mockState.queryData.clear()
  mockState.resolveApiProviderForModel.mockReset()
  mockState.resolveApiProviderForModel.mockResolvedValue(null)
  mockState.streamCalls.length = 0
  mockState.sendCalls.length = 0

  mockState.queryData.set("writing-capabilities", DEFAULT_WRITING_CAPABILITIES)
  mockState.queryData.set("writing-defaults", { templates: [], themes: [] })
  mockState.queryData.set("writing-sessions", {
    sessions: [],
    total: 0,
    limit: 200,
    offset: 0
  })
  mockState.queryData.set("writing-templates", {
    templates: [],
    total: 0,
    limit: 200,
    offset: 0
  })
  mockState.queryData.set("writing-themes", {
    themes: [],
    total: 0,
    limit: 200,
    offset: 0
  })
  mockState.queryData.set("writing-session:", null)

  useWritingPlaygroundStore.setState({
    activeSessionId: null,
    activeSessionName: null
  })
})

describe("WritingPlayground phase1 baseline", () => {
  it("renders key empty-state landmarks without crashing", () => {
    render(<WritingPlayground />)

    expect(
      screen.getByTestId("writing-playground-shell")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-editor-panel")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-topbar")
    ).toBeInTheDocument()
    expect(screen.getByText("Select a session to begin.")).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-main-grid")
    ).toBeInTheDocument()
  })

  it("updates shell layout mode on resize for compact behavior", () => {
    const originalWidth = window.innerWidth
    try {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        writable: true,
        value: 1280
      })

      render(<WritingPlayground />)

      const shell = screen.getByTestId("writing-playground-shell")
      expect(shell).toHaveAttribute("data-layout-mode", "expanded")

      window.innerWidth = 960
      fireEvent(window, new Event("resize"))
      expect(shell).toHaveAttribute("data-layout-mode", "compact")
    } finally {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        writable: true,
        value: originalWidth
      })
    }
  })

  it("surfaces auto-routing limits for token inspection", () => {
    mockState.storageValues.set("selectedModel", "auto")
    seedWritingSession()

    render(<WritingPlayground />)
    fireEvent.click(screen.getByRole("button", { name: "Toggle settings" }))
    fireEvent.click(screen.getByTestId("writing-inspector-tab-inspect"))

    expect(
      screen.getByRole("button", { name: "Count tokens" })
    ).toBeDisabled()
  })

  it("passes auto model selections through generation requests", async () => {
    mockState.storageValues.set("selectedModel", "auto")
    seedWritingSession()

    render(<WritingPlayground />)

    fireEvent.change(
      screen.getByPlaceholderText("Start writing your prompt..."),
      {
        target: { value: "Route this prompt on the server." }
      }
    )
    fireEvent.click(screen.getByTestId("writing-topbar-generate"))

    await waitFor(() => {
      expect(mockState.streamCalls).toHaveLength(1)
    })
    expect(mockState.streamCalls[0]?.options.model).toBe("auto")
    expect(mockState.streamCalls[0]?.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          content: "Route this prompt on the server."
        })
      ])
    )
  })
})
