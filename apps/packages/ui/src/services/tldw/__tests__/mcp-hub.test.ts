import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequestClient: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequestClient: (...args: unknown[]) => mocks.bgRequestClient(...args)
}))

import { setExternalServerSecret } from "../mcp-hub"

describe("mcp hub service client", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("maps external secret set response without exposing plaintext", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce({
      server_id: "docs",
      secret_configured: true,
      key_hint: "cdef"
    })

    const out = await setExternalServerSecret("docs", "my-secret")

    expect(out.secret_configured).toBe(true)
    expect(JSON.stringify(out)).not.toContain("my-secret")
    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/mcp/hub/external-servers/docs/secret",
        method: "POST",
        body: { secret: "my-secret" }
      })
    )
  })
})
