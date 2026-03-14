import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequestClient: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequestClient: (...args: unknown[]) => mocks.bgRequestClient(...args)
}))

import {
  dryRunGovernancePack,
  listGovernancePacks,
  setExternalServerSecret
} from "../mcp-hub"

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

  it("requests governance pack dry-run reports through the MCP Hub preview endpoint", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce({
      report: {
        manifest: {
          pack_id: "researcher-pack",
          pack_version: "1.0.0",
          title: "Researcher Pack"
        },
        digest: "a".repeat(64),
        resolved_capabilities: ["tool.invoke.research"],
        unresolved_capabilities: [],
        warnings: [],
        blocked_objects: [],
        verdict: "importable"
      }
    })

    const payload = {
      owner_scope_type: "user" as const,
      pack: {
        manifest: { pack_id: "researcher-pack" },
        profiles: [],
        approvals: [],
        personas: [],
        assignments: []
      }
    }
    const out = await dryRunGovernancePack(payload)

    expect(out.report.verdict).toBe("importable")
    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/mcp/hub/governance-packs/dry-run",
        method: "POST",
        body: payload
      })
    )
  })

  it("lists governance packs with scope filters", async () => {
    mocks.bgRequestClient.mockResolvedValueOnce([
      {
        id: 81,
        pack_id: "researcher-pack",
        pack_version: "1.0.0",
        title: "Researcher Pack",
        owner_scope_type: "user",
        owner_scope_id: 7,
        bundle_digest: "a".repeat(64),
        manifest: {}
      }
    ])

    const out = await listGovernancePacks({ owner_scope_type: "user", owner_scope_id: 7 })

    expect(out).toHaveLength(1)
    expect(mocks.bgRequestClient).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/mcp/hub/governance-packs?owner_scope_type=user&owner_scope_id=7",
        method: "GET"
      })
    )
  })
})
