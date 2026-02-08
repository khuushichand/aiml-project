import { describe, it, expect, vi, afterEach, beforeEach } from "vitest"
import { render, screen, fireEvent, cleanup, waitFor, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReferencesTab } from "../ReferencesTab"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useConnectionStore } from "@/store/connection"
import { tldwClient } from "@/services/tldw"

let mockReferencesResponse: any = null

vi.mock("@/hooks/document-workspace", async () => {
  const actual = await vi.importActual<any>("@/hooks/document-workspace")
  return {
    ...actual,
    useDocumentReferences: () => ({
      data: mockReferencesResponse,
      isLoading: false,
      error: null,
    }),
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key,
  }),
}))

describe("ReferencesTab", () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient()
    useDocumentWorkspaceStore.setState({ activeDocumentId: 1 })
    const prev = useConnectionStore.getState().state
    useConnectionStore.setState({
      state: { ...prev, isConnected: true, mode: "normal" },
    })
    if (typeof globalThis.ResizeObserver === "undefined") {
      globalThis.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    }
  })

  afterEach(() => {
    cleanup()
    useDocumentWorkspaceStore.setState({ activeDocumentId: null })
    const prev = useConnectionStore.getState().state
    useConnectionStore.setState({
      state: { ...prev, isConnected: false, mode: "normal" },
    })
    vi.clearAllMocks()
  })

  it("filters references by search query", () => {
    mockReferencesResponse = {
      media_id: 1,
      has_references: true,
      references: [
        {
          raw_text: "Ref with DOI",
          title: "With DOI",
          doi: "10.1234/abcd",
          citation_count: 12,
        },
        {
          raw_text: "Ref without DOI",
          title: "No DOI",
          citation_count: 0,
        },
      ],
      enrichment_source: "semantic_scholar",
    }

    render(
      <QueryClientProvider client={queryClient}>
        <ReferencesTab />
      </QueryClientProvider>
    )

    expect(screen.getByText("With DOI")).toBeInTheDocument()
    expect(screen.getByText("No DOI")).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText("Search references...")
    fireEvent.change(searchInput, { target: { value: "With DOI" } })
    expect(screen.getByText("With DOI")).toBeInTheDocument()
    expect(screen.queryByText("No DOI")).not.toBeInTheDocument()
  })

  it("enriches a single reference using reference_index", async () => {
    mockReferencesResponse = {
      media_id: 1,
      has_references: true,
      references: [
        {
          raw_text: "First reference raw",
          title: "First reference",
          doi: "10.1234/first",
        },
        {
          raw_text: "Second reference raw",
          title: "Second reference",
          citation_count: 3,
        },
      ],
      enrichment_source: null,
    }

    const getDocumentReferencesSpy = vi
      .spyOn(tldwClient, "getDocumentReferences")
      .mockResolvedValue({
        media_id: 1,
        has_references: true,
        references: [
          {
            raw_text: "First reference raw",
            title: "First reference",
            doi: "10.1234/first",
            citation_count: 22,
          },
          {
            raw_text: "Second reference raw",
            title: "Second reference",
            citation_count: 3,
          },
        ],
        enrichment_source: "semantic_scholar",
      })

    render(
      <QueryClientProvider client={queryClient}>
        <ReferencesTab />
      </QueryClientProvider>
    )

    const firstTitle = screen.getByText("First reference")
    const card = firstTitle.closest(".rounded-lg")
    expect(card).not.toBeNull()
    const enrichButton = within(card as HTMLElement).getByRole("button", {
      name: "Enrich",
    })
    fireEvent.click(enrichButton)

    await waitFor(() => {
      expect(getDocumentReferencesSpy).toHaveBeenCalledWith(1, {
        enrich: true,
        referenceIndex: 0,
        offset: 0,
        limit: 50,
        parseCap: undefined,
      })
    })
  })
})
