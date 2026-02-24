import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import MlxAdminPage from "../MlxAdminPage"

const apiMock = vi.hoisted(() => ({
  getMlxStatus: vi.fn(),
  getLlmProviders: vi.fn(),
  loadMlxModel: vi.fn(),
  unloadMlxModel: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === "string") {
        return fallbackOrOptions
      }
      if (
        fallbackOrOptions &&
        typeof fallbackOrOptions === "object" &&
        typeof fallbackOrOptions.defaultValue === "string"
      ) {
        return fallbackOrOptions.defaultValue
      }
      return maybeOptions?.defaultValue || key
    }
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: apiMock
}))

vi.mock("@/components/Common/PageShell", () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

describe("MlxAdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    if (!window.matchMedia) {
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

    if (!(window as any).ResizeObserver) {
      ;(window as any).ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    }

    apiMock.getMlxStatus.mockResolvedValue({
      active: false,
      model: null,
      max_concurrent: 2
    })
    apiMock.getLlmProviders.mockResolvedValue({
      providers: []
    })
    apiMock.loadMlxModel.mockResolvedValue({})
    apiMock.unloadMlxModel.mockResolvedValue({})
  })

  it("clarifies inactive concurrency semantics", async () => {
    render(<MlxAdminPage />)

    expect(await screen.findByText(/Configured concurrency \(inactive\)/)).toBeTruthy()
    expect(
      await screen.findByText(
        "Concurrency is a configured limit and applies once a model is active."
      )
    ).toBeTruthy()
  })

  it("gates controls when admin APIs are unavailable", async () => {
    apiMock.getMlxStatus.mockRejectedValueOnce(
      new Error(
        "Request failed: 503 (GET /api/v1/admin/mlx/status) config=/Users/dev/.config/tldw/config.txt"
      )
    )

    render(<MlxAdminPage />)

    expect(await screen.findByText("Admin APIs not available")).toBeTruthy()
    expect(screen.queryByText("Load Model")).toBeNull()
  })

  it("disables model actions when MLX status is temporarily unavailable", async () => {
    apiMock.getMlxStatus.mockRejectedValueOnce(new Error("network down"))

    render(<MlxAdminPage />)

    expect(
      await screen.findByText(
        "MLX controls are temporarily unavailable until status checks succeed."
      )
    ).toBeTruthy()

    expect(screen.getByRole("button", { name: "Load Model" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Unload Model" })).toBeDisabled()
  })
})
