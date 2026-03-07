import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("@tanstack/react-query", () => {
  const writingCaps = {
    server: {
      sessions: true,
      templates: true,
      themes: true,
      defaults_catalog: false,
      snapshots: false
    },
    requested: {
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

  const resolveQueryData = (queryKey: unknown): unknown => {
    const key = Array.isArray(queryKey) ? queryKey[0] : queryKey
    switch (key) {
      case "writing-capabilities":
        return writingCaps
      case "writing-defaults":
        return { templates: [], themes: [] }
      case "writing-sessions":
        return { sessions: [], total: 0, limit: 200, offset: 0 }
      case "writing-templates":
        return { templates: [], total: 0, limit: 200, offset: 0 }
      case "writing-themes":
        return { themes: [], total: 0, limit: 200, offset: 0 }
      case "writing-session":
        return null
      default:
        return undefined
    }
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
    useStorage: <T,>(_key: string, initial?: T) =>
      React.useState<T | undefined>(initial)
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
  resolveApiProviderForModel: async () => null
}))

vi.mock("@/components/Common/MarkdownPreview", () => ({
  MarkdownPreview: ({ content }: { content: string }) => <div>{content}</div>
}))

vi.mock("@/services/tldw/TldwChat", () => ({
  TldwChatService: class TldwChatServiceMock {
    cancelStream() {}
    async *streamMessage() {
      yield ""
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

describe("WritingPlayground inspector tabs", () => {
  it("switches inspector tabs with semantic tab roles", () => {
    render(<WritingPlayground />)

    const tablist = screen.getByRole("tablist", {
      name: "Writing inspector tabs"
    })
    expect(tablist).toBeInTheDocument()

    const samplingTab = screen.getByRole("tab", { name: "Sampling" })
    const contextTab = screen.getByRole("tab", { name: "Context" })

    expect(samplingTab).toHaveAttribute("aria-selected", "true")
    expect(contextTab).toHaveAttribute("aria-selected", "false")

    fireEvent.click(contextTab)

    expect(contextTab).toHaveAttribute("aria-selected", "true")
    expect(samplingTab).toHaveAttribute("aria-selected", "false")
  })

  it("supports keyboard arrow navigation between tabs", () => {
    render(<WritingPlayground />)

    const samplingTab = screen.getByRole("tab", { name: "Sampling" })
    const contextTab = screen.getByRole("tab", { name: "Context" })

    samplingTab.focus()
    fireEvent.keyDown(samplingTab, { key: "ArrowRight" })

    expect(contextTab).toHaveAttribute("aria-selected", "true")
    expect(samplingTab).toHaveAttribute("aria-selected", "false")
    expect(contextTab).toHaveFocus()
  })

  it("supports Home/End and wraparound focus traversal", () => {
    render(<WritingPlayground />)

    const samplingTab = screen.getByRole("tab", { name: "Sampling" })
    const inspectTab = screen.getByRole("tab", { name: "Inspect" })

    samplingTab.focus()
    fireEvent.keyDown(samplingTab, { key: "ArrowLeft" })
    expect(inspectTab).toHaveAttribute("aria-selected", "true")
    expect(inspectTab).toHaveFocus()

    fireEvent.keyDown(inspectTab, { key: "Home" })
    expect(samplingTab).toHaveAttribute("aria-selected", "true")
    expect(samplingTab).toHaveFocus()

    fireEvent.keyDown(samplingTab, { key: "End" })
    expect(inspectTab).toHaveAttribute("aria-selected", "true")
    expect(inspectTab).toHaveFocus()
  })

  it("shows template/theme management actions in Setup tab", () => {
    render(<WritingPlayground />)

    expect(
      screen.queryByRole("button", { name: "Manage templates" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Manage themes" })
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Setup" }))

    expect(
      screen.getByRole("button", { name: "Manage templates" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Manage themes" })
    ).toBeInTheDocument()
  })

  it("renders essentials strip with model input and generate button", () => {
    render(<WritingPlayground />)

    expect(
      screen.getByTestId("writing-essentials-strip")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-essentials-model")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-essentials-generate")
    ).toBeInTheDocument()
  })

  it("has four tabs: Sampling, Context, Setup, Inspect", () => {
    render(<WritingPlayground />)

    expect(screen.getByRole("tab", { name: "Sampling" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Context" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Setup" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Inspect" })).toBeInTheDocument()
  })
})
