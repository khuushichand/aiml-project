import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { KnowledgePanel } from "../KnowledgePanel"

const mockUseKnowledgeSettings = vi.fn()
const mockUseKnowledgeSearch = vi.fn()
const mockUseFileSearch = vi.fn()
const mockUseQASearch = vi.fn()

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: { language: "en" }
  })
}))

vi.mock("../hooks", () => ({
  useKnowledgeSettings: (...args: unknown[]) =>
    mockUseKnowledgeSettings(...args),
  useKnowledgeSearch: (...args: unknown[]) => mockUseKnowledgeSearch(...args),
  toPinnedResult: (item: any) => ({
    id: `pin-${item?.metadata?.id ?? "1"}`,
    title:
      typeof item?.metadata?.title === "string" ? item.metadata.title : "",
    source:
      typeof item?.metadata?.source === "string"
        ? item.metadata.source
        : undefined,
    url:
      typeof item?.metadata?.url === "string" ? item.metadata.url : undefined,
    snippet: String(item?.content || item?.text || item?.chunk || "")
  }),
  withFullMediaTextIfAvailable: async (pinned: unknown) => pinned,
  qaDocumentToRagResult: (doc: any) => ({
    content: doc.content || doc.text || doc.chunk || "",
    metadata: doc.metadata || {},
    score: doc.score,
    relevance: doc.relevance
  })
}))

vi.mock("../hooks/useFileSearch", async () => {
  const actual = await vi.importActual<typeof import("../hooks/useFileSearch")>(
    "../hooks/useFileSearch"
  )
  return {
    ...actual,
    useFileSearch: (...args: unknown[]) => mockUseFileSearch(...args)
  }
})

vi.mock("../hooks/useQASearch", () => ({
  useQASearch: (...args: unknown[]) => mockUseQASearch(...args)
}))

const setup = (isDirty: boolean) => {
  const applySettings = vi.fn()
  const runSearch = vi.fn().mockResolvedValue(undefined)
  const runQASearch = vi.fn().mockResolvedValue(undefined)

  mockUseKnowledgeSettings.mockReturnValue({
    preset: "balanced",
    draftSettings: {
      query: "knowledge query",
      sources: ["media_db"],
      strategy: "standard"
    },
    storedSettings: {},
    useCurrentMessage: false,
    advancedOpen: false,
    advancedSearch: "",
    resolvedQuery: "knowledge query",
    isDirty,
    updateSetting: vi.fn(),
    applyPreset: vi.fn(),
    applySettings,
    resetToBalanced: vi.fn(),
    setUseCurrentMessage: vi.fn(),
    setAdvancedOpen: vi.fn(),
    setAdvancedSearch: vi.fn(),
    discardChanges: vi.fn()
  })

  mockUseKnowledgeSearch.mockReturnValue({
    pinnedResults: [],
    handlePin: vi.fn(),
    handleUnpin: vi.fn(),
    handleClearPins: vi.fn()
  })

  mockUseFileSearch.mockReturnValue({
    loading: false,
    results: [],
    sortMode: "relevance",
    timedOut: false,
    hasAttemptedSearch: false,
    queryError: null,
    mediaTypes: [],
    setMediaTypes: vi.fn(),
    attachedMediaIds: new Set<number>(),
    runSearch,
    setSortMode: vi.fn(),
    sortResults: (items: unknown[]) => items,
    handleAttach: vi.fn(),
    handlePreview: vi.fn(),
    handleOpen: vi.fn(),
    handlePin: vi.fn(),
    copyResult: vi.fn()
  })

  mockUseQASearch.mockReturnValue({
    loading: false,
    response: null,
    timedOut: false,
    hasAttemptedSearch: false,
    queryError: null,
    runQASearch,
    copyAnswer: vi.fn(),
    insertAnswer: vi.fn(),
    insertChunk: vi.fn(),
    copyChunk: vi.fn(),
    pinChunk: vi.fn()
  })

  render(
    <KnowledgePanel
      open
      showToggle={false}
      onInsert={vi.fn()}
      onAsk={vi.fn()}
    />
  )

  return { applySettings, runSearch, runQASearch }
}

describe("KnowledgePanel footer behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("hides footer action buttons when settings are not dirty", () => {
    setup(false)

    expect(
      screen.queryByRole("button", { name: "Apply" })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Apply & Search" })
    ).not.toBeInTheDocument()
  })

  it("shows footer on QA tab when dirty and runs QA apply-and-search", async () => {
    const { applySettings, runSearch, runQASearch } = setup(true)

    const applyButton = screen.getByRole("button", { name: "Apply" })
    const applyAndSearchButton = screen.getByRole("button", {
      name: "Apply & Search"
    })

    expect(applyButton).toBeEnabled()
    fireEvent.click(applyButton)
    expect(applySettings).toHaveBeenCalledTimes(1)

    fireEvent.click(applyAndSearchButton)
    await waitFor(() => {
      expect(runQASearch).toHaveBeenCalledWith({ applyFirst: true })
    })
    expect(runSearch).not.toHaveBeenCalled()
  })

  it("disables Apply on file-search tab and routes apply-and-search to file search", async () => {
    const { applySettings, runSearch, runQASearch } = setup(true)

    fireEvent.click(screen.getByRole("tab", { name: "File Search" }))

    const applyButton = screen.getByRole("button", { name: "Apply" })
    expect(applyButton).toBeDisabled()
    fireEvent.click(applyButton)
    expect(applySettings).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Apply & Search" }))
    await waitFor(() => {
      expect(runSearch).toHaveBeenCalledWith({ applyFirst: true })
    })
    expect(runQASearch).not.toHaveBeenCalled()
  })

  it("routes apply-and-search from settings tab back to QA search", async () => {
    const { runSearch, runQASearch } = setup(true)

    fireEvent.click(screen.getByRole("tab", { name: "Settings" }))
    fireEvent.click(screen.getByRole("button", { name: "Apply & Search" }))

    await waitFor(() => {
      expect(runQASearch).toHaveBeenCalledWith({ applyFirst: true })
    })
    expect(runSearch).not.toHaveBeenCalled()
    expect(screen.getByRole("tab", { name: "QA Search" })).toHaveAttribute(
      "aria-selected",
      "true"
    )
  })
})
