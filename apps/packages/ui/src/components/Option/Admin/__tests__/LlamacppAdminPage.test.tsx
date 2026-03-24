import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import LlamacppAdminPage from "../LlamacppAdminPage"

const apiMock = vi.hoisted(() => ({
  getLlamacppStatus: vi.fn(),
  listLlamacppModels: vi.fn(),
  startLlamacppServer: vi.fn(),
  stopLlamacppServer: vi.fn()
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

describe("LlamacppAdminPage", () => {
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

    apiMock.getLlamacppStatus.mockResolvedValue({
      state: "stopped",
      model: null,
      port: 8080
    })
    apiMock.listLlamacppModels.mockResolvedValue({
      available_models: ["toy.gguf"]
    })
    apiMock.startLlamacppServer.mockResolvedValue({
      status: "started"
    })
    apiMock.stopLlamacppServer.mockResolvedValue({
      status: "stopped"
    })
  })

  it("renders structured sections and preset controls", async () => {
    render(<LlamacppAdminPage />)

    expect(await screen.findByText("Main Options")).toBeTruthy()
    expect(await screen.findByText("Other Options")).toBeTruthy()
    expect(await screen.findByText("Multimodal (vision)")).toBeTruthy()
    expect(await screen.findByText("Speculative decoding")).toBeTruthy()
    expect(await screen.findByText("Raw argument overrides")).toBeTruthy()

    expect(await screen.findByRole("button", { name: "Export preset" })).toBeTruthy()
    expect(await screen.findByRole("button", { name: "Import preset" })).toBeTruthy()
  })

  it("emits structured llama server args when starting", async () => {
    render(<LlamacppAdminPage />)

    const startButton = await screen.findByRole("button", { name: "Start Server" })
    fireEvent.click(startButton)

    await waitFor(() => {
      expect(apiMock.startLlamacppServer).toHaveBeenCalled()
    })

    expect(apiMock.startLlamacppServer).toHaveBeenCalledWith(
      "toy.gguf",
      expect.objectContaining({
        ctx_size: 4096,
        n_gpu_layers: 0,
        cache_type_k: "f16",
        cache_type_v: "f16"
      })
    )
  })

  it("disables start actions when model prerequisites fail to load", async () => {
    apiMock.listLlamacppModels.mockRejectedValueOnce(
      new Error(
        "Request failed: 500 (GET /api/v1/llamacpp/models) model_dir=/Users/dev/models"
      )
    )

    render(<LlamacppAdminPage />)

    const startButton = await screen.findByRole("button", { name: "Start Server" })
    expect(startButton).toBeDisabled()

    const fullText = document.body.textContent || ""
    expect(fullText).toContain("[admin-endpoint]")
    expect(fullText).toContain("[redacted-path]")
  })

  it("gates controls when admin APIs are unavailable", async () => {
    apiMock.getLlamacppStatus.mockRejectedValueOnce(
      new Error(
        "Request failed: 503 (GET /api/v1/admin/llamacpp/status) config=/Users/dev/.config/tldw/config.txt"
      )
    )

    render(<LlamacppAdminPage />)

    expect(await screen.findByText("Admin APIs not available")).toBeTruthy()
    expect(screen.queryByText("Load Model")).toBeNull()
  })

  it("loads status and models only once during strict-mode mount", async () => {
    render(
      <React.StrictMode>
        <LlamacppAdminPage />
      </React.StrictMode>
    )

    await waitFor(() => {
      expect(apiMock.getLlamacppStatus).toHaveBeenCalledTimes(1)
      expect(apiMock.listLlamacppModels).toHaveBeenCalledTimes(1)
    })
  })
})
