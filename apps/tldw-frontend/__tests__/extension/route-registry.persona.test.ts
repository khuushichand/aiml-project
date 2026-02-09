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
  throw new Error("Unable to locate extension route-registry.tsx for parity test")
}

const extensionRouteRegistrySource = readFileSync(
  extensionRouteRegistryPath,
  "utf8"
)

describe("extension sidepanel route registry persona parity", () => {
  it("registers persona sidepanel path", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/persona"/)
  })

  it("retains existing agent route alongside persona route", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/agent"/)
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/persona"/)
  })
})
