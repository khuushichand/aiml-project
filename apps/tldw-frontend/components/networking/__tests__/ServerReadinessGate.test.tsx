import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

describe("ServerReadinessGate", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
  })

  it("accepts the backend healthy status envelope", async () => {
    vi.stubEnv("NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE", "advanced")
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000")
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ status: "healthy" })
    } as Response)
    const { ServerReadinessGate } = await import("../ServerReadinessGate")

    render(
      <ServerReadinessGate>
        <div>App ready</div>
      </ServerReadinessGate>
    )

    await waitFor(() => {
      expect(screen.getByText("App ready")).toBeInTheDocument()
    })
  })
})
