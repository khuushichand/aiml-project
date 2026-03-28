import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const extensionRouteRegistryPathCandidates = [
  "extension/routes/route-registry.tsx",
  "apps/tldw-frontend/extension/routes/route-registry.tsx"
]

const extensionRouteRegistryPath = extensionRouteRegistryPathCandidates.find(
  (candidate) => existsSync(candidate)
)

if (!extensionRouteRegistryPath) {
  throw new Error("Unable to locate extension route-registry.tsx for MCP Hub parity test")
}

const extensionRouteRegistrySource = readFileSync(
  extensionRouteRegistryPath,
  "utf8"
)

describe("extension route registry MCP Hub parity", () => {
  it("registers the settings MCP Hub route", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/settings\/mcp-hub"/)
    expect(extensionRouteRegistrySource).toMatch(
      /labelToken:\s*"settings:mcpHubNav"/
    )
  })

  it("registers the standalone MCP Hub route", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/mcp-hub"/)
  })
})
