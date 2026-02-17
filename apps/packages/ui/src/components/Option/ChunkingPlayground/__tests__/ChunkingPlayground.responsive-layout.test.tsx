import { render, screen } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery } from "@tanstack/react-query"
import { ChunkingPlayground } from "../index"

const { useQueryMock, mediaQueryState } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  mediaQueryState: {
    isDesktop: false
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

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ChunkingPlayground responsive single-mode layout", () => {
  const originalMatchMedia = window.matchMedia
  const isBefore = (a: HTMLElement, b: HTMLElement) =>
    Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

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
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn()
    } as any)
  })

  it("renders settings before result output on non-desktop viewports", () => {
    mediaQueryState.isDesktop = false
    render(<ChunkingPlayground />)

    const settingsLabel = screen.getAllByText("Settings")[0]
    const emptyResultState = screen.getByText(
      "Enter text and click 'Chunk Text' to see results"
    )

    expect(isBefore(settingsLabel, emptyResultState)).toBe(true)
  })

  it("keeps desktop ordering with results before side settings panel", () => {
    mediaQueryState.isDesktop = true
    render(<ChunkingPlayground />)

    const settingsLabel = screen.getAllByText("Settings")[0]
    const emptyResultState = screen.getByText(
      "Enter text and click 'Chunk Text' to see results"
    )

    expect(isBefore(settingsLabel, emptyResultState)).toBe(false)
  })
})
