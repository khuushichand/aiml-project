import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import MlxAdminPage from "../MlxAdminPage"

const apiMock = vi.hoisted(() => ({
  getMlxStatus: vi.fn(),
  getMlxModels: vi.fn(),
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
    apiMock.getMlxModels.mockResolvedValue({
      backend: "mlx",
      model_dir: "/tmp/mlx-models",
      model_dir_configured: true,
      warnings: [],
      available_models: []
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

  it("loads discovered model using model_id", async () => {
    apiMock.getMlxModels.mockResolvedValueOnce({
      backend: "mlx",
      model_dir: "/tmp/mlx-models",
      model_dir_configured: true,
      warnings: [],
      available_models: [
        {
          id: "family/model-a",
          name: "model-a",
          selectable: true,
          reasons: []
        }
      ]
    })

    render(<MlxAdminPage />)

    await screen.findByText("model-a (family/model-a)")
    fireEvent.click(screen.getByRole("button", { name: "Load Model" }))

    await waitFor(() => {
      expect(apiMock.loadMlxModel).toHaveBeenCalledWith(
        expect.objectContaining({ model_id: "family/model-a" })
      )
    })
  })

  it("shows non-selectable discovered model reasons", async () => {
    apiMock.getMlxModels.mockResolvedValueOnce({
      backend: "mlx",
      model_dir: "/tmp/mlx-models",
      model_dir_configured: true,
      warnings: [],
      available_models: [
        {
          id: "family/model-b",
          name: "model-b",
          selectable: false,
          reasons: ["Missing tokenizer.json or tokenizer.model"]
        }
      ]
    })

    render(<MlxAdminPage />)

    expect(await screen.findByText("Missing tokenizer.json or tokenizer.model")).toBeTruthy()
  })

  it("uses manual model_path fallback when no discovered model is selected", async () => {
    render(<MlxAdminPage />)

    const manualPathWrapper = await screen.findByTestId("mlx-manual-model-path")
    const manualPathInput = manualPathWrapper.querySelector("input")
    expect(manualPathInput).toBeTruthy()

    fireEvent.change(manualPathInput as HTMLInputElement, {
      target: { value: "/tmp/manual-model" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Load Model" }))

    await waitFor(() => {
      expect(apiMock.loadMlxModel).toHaveBeenCalledWith(
        expect.objectContaining({ model_path: "/tmp/manual-model" })
      )
    })
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
