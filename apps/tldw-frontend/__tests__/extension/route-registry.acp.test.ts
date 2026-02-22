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
  throw new Error("Unable to locate extension route-registry.tsx for ACP parity test")
}

const extensionRouteRegistrySource = readFileSync(
  extensionRouteRegistryPath,
  "utf8"
)

describe("extension route registry ACP parity", () => {
  it("registers ACP playground route", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/acp-playground"/)
  })

  it("exposes ACP playground in workspace navigation", () => {
    expect(extensionRouteRegistrySource).toMatch(/labelToken:\s*"settings:acpPlaygroundNav"/)
  })
})
