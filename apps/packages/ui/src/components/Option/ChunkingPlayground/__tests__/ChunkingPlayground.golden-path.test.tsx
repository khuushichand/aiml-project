import { fireEvent, render, screen } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery } from "@tanstack/react-query"
import { ChunkingPlayground } from "../index"

const { useQueryMock, mediaQueryState } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  mediaQueryState: {
    isDesktop: true
  }
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useQueryClient: vi.fn(() => ({
    invalidateQueries: vi.fn()
  })),
  useMutation: vi.fn(() => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false
  }))
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useDesktop: () => mediaQueryState.isDesktop
}))

vi.mock("../SaveAsTemplateModal", () => ({
  SaveAsTemplateModal: () => null
}))

vi.mock("../SampleTexts", () => ({
  SampleTexts: () => <div data-testid="chunking-sample-texts">Sample Text Presets</div>
}))

vi.mock("../MediaSelector", () => ({
  MediaSelector: () => <div data-testid="chunking-media-selector">Media Selector</div>
}))

vi.mock("../CompareView", () => ({
  CompareView: () => <div data-testid="chunking-compare-view">Compare Mode</div>
}))

vi.mock("../ChunkingTemplatesPanel", () => ({
  ChunkingTemplatesPanel: () => (
    <div data-testid="chunking-templates-panel">Templates Mode</div>
  )
}))

vi.mock("../ChunkingCapabilitiesPanel", () => ({
  ChunkingCapabilitiesPanel: () => (
    <div data-testid="chunking-capabilities-panel">Capabilities Mode</div>
  )
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ChunkingPlayground golden path guardrails", () => {
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
    mediaQueryState.isDesktop = true
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn()
    } as any)
  })

  it("preserves multi-input source affordances for chunking workflows", () => {
    render(<ChunkingPlayground />)

    expect(screen.getByRole("radio", { name: "Paste Text" })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Upload File" })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Upload PDF" })).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Sample Text" })).toBeInTheDocument()
    expect(
      screen.getByRole("radio", { name: "From Media Library" })
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "Upload File" }))
    expect(screen.getByText("Click or drag file to upload")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "Upload PDF" }))
    expect(screen.getByText("Click or drag PDF to upload")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "Sample Text" }))
    expect(screen.getByTestId("chunking-sample-texts")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "From Media Library" }))
    expect(screen.getByTestId("chunking-media-selector")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("radio", { name: "Paste Text" }))
    expect(screen.getByPlaceholderText("Paste text here...")).toBeInTheDocument()
  })

  it("keeps core mode navigation for single, compare, templates, and capabilities", () => {
    render(<ChunkingPlayground />)

    expect(screen.getByRole("tab", { name: "Single" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Compare" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Templates" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Capabilities" })).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Compare" }))
    expect(screen.getByTestId("chunking-compare-view")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Templates" }))
    expect(screen.getByTestId("chunking-templates-panel")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Capabilities" }))
    expect(screen.getByTestId("chunking-capabilities-panel")).toBeInTheDocument()
  })
})
