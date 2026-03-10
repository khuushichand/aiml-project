import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const routeRegistryPathCandidates = [
  "src/routes/route-registry.tsx",
  "../packages/ui/src/routes/route-registry.tsx",
  "apps/packages/ui/src/routes/route-registry.tsx"
]

const routeRegistryPath = routeRegistryPathCandidates.find((candidate) =>
  existsSync(candidate)
)

if (!routeRegistryPath) {
  throw new Error("Unable to locate route-registry.tsx for companion parity test")
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("sidepanel route registry companion parity", () => {
  it("registers a dedicated companion sidepanel route", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/companion"/)
  })

  it("registers the companion conversation route in both option and sidepanel shells", () => {
    const matches = routeRegistrySource.match(/path:\s*"\/companion\/conversation"/g) ?? []
    expect(matches).toHaveLength(2)
  })
})
