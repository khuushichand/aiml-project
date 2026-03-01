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

    const generationTab = screen.getByRole("tab", { name: "Generation" })
    const planningTab = screen.getByRole("tab", { name: "Planning" })

    expect(generationTab).toHaveAttribute("aria-selected", "true")
    expect(planningTab).toHaveAttribute("aria-selected", "false")

    fireEvent.click(planningTab)

    expect(planningTab).toHaveAttribute("aria-selected", "true")
    expect(generationTab).toHaveAttribute("aria-selected", "false")
  })

  it("supports keyboard arrow navigation between tabs", () => {
    render(<WritingPlayground />)

    const generationTab = screen.getByRole("tab", { name: "Generation" })
    const planningTab = screen.getByRole("tab", { name: "Planning" })

    generationTab.focus()
    fireEvent.keyDown(generationTab, { key: "ArrowRight" })

    expect(planningTab).toHaveAttribute("aria-selected", "true")
    expect(generationTab).toHaveAttribute("aria-selected", "false")
    expect(planningTab).toHaveFocus()
  })

  it("supports Home/End and wraparound focus traversal", () => {
    render(<WritingPlayground />)

    const generationTab = screen.getByRole("tab", { name: "Generation" })
    const diagnosticsTab = screen.getByRole("tab", { name: "Diagnostics" })

    generationTab.focus()
    fireEvent.keyDown(generationTab, { key: "ArrowLeft" })
    expect(diagnosticsTab).toHaveAttribute("aria-selected", "true")
    expect(diagnosticsTab).toHaveFocus()

    fireEvent.keyDown(diagnosticsTab, { key: "Home" })
    expect(generationTab).toHaveAttribute("aria-selected", "true")
    expect(generationTab).toHaveFocus()

    fireEvent.keyDown(generationTab, { key: "End" })
    expect(diagnosticsTab).toHaveAttribute("aria-selected", "true")
    expect(diagnosticsTab).toHaveFocus()
  })

  it("shows template/theme management actions in Planning, not Generation", () => {
    render(<WritingPlayground />)

    expect(
      screen.queryByRole("button", { name: "Manage templates" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Manage themes" })
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Planning" }))

    expect(
      screen.getByRole("button", { name: "Manage templates" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Manage themes" })
    ).toBeInTheDocument()
  })

  it("renders non-placeholder diagnostics content", () => {
    render(<WritingPlayground />)

    fireEvent.click(screen.getByRole("tab", { name: "Diagnostics" }))

    expect(
      screen.queryByText("Diagnostics tools will be moved here.")
    ).not.toBeInTheDocument()
  })
})
