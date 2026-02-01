import { describe, it, expect, vi, afterEach, beforeEach } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import { ReferencesTab } from "../ReferencesTab"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useConnectionStore } from "@/store/connection"

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
  beforeEach(() => {
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

  it("filters by DOI and citations", () => {
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

    render(<ReferencesTab />)

    expect(screen.getByText("With DOI")).toBeInTheDocument()
    expect(screen.getByText("No DOI")).toBeInTheDocument()

    fireEvent.click(screen.getByText("Has DOI"))
    expect(screen.getByText("With DOI")).toBeInTheDocument()
    expect(screen.queryByText("No DOI")).not.toBeInTheDocument()

    fireEvent.click(screen.getByText("Has citations"))
    expect(screen.getByText("With DOI")).toBeInTheDocument()
  })
})
