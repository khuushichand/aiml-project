import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const extensionRouteRegistryPathCandidates = [
  "tldw-frontend/extension/routes/route-registry.tsx",
  "extension/routes/route-registry.tsx",
  "apps/tldw-frontend/extension/routes/route-registry.tsx"
]

const extensionRouteRegistryPath = extensionRouteRegistryPathCandidates.find(
  (candidate) => existsSync(candidate)
)

if (!extensionRouteRegistryPath) {
  throw new Error("Unable to locate extension route-registry.tsx for sources parity test")
}

const extensionRouteRegistrySource = readFileSync(extensionRouteRegistryPath, "utf8")

describe("extension route registry sources parity", () => {
  it("registers the sources options routes and admin mirror", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/sources"/)
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/sources\/new"/)
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/sources\/:sourceId"/)
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/admin\/sources"/)
  })
})
