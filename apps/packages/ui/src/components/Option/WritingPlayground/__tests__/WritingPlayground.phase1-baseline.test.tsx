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

describe("WritingPlayground phase1 baseline", () => {
  it("renders key empty-state landmarks without crashing", () => {
    render(<WritingPlayground />)

    expect(
      screen.getByTestId("writing-playground-shell")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-library-panel")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-editor-panel")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-settings-card")
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: "Writing Playground" })
    ).toBeInTheDocument()
    expect(
      screen.getByText("Create your first session to start writing.")
    ).toBeInTheDocument()
    expect(screen.getByText("Select a session to begin.")).toBeInTheDocument()
    expect(
      screen.getByText("Select a session to edit settings.")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-main-grid")
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("writing-playground-content-grid")
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
})
