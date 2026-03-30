import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const routeRegistryPathCandidates = [
  "src/routes/sidepanel-route-registry.tsx",
  "../packages/ui/src/routes/sidepanel-route-registry.tsx",
  "apps/packages/ui/src/routes/sidepanel-route-registry.tsx"
]

const routeRegistryPath = routeRegistryPathCandidates.find((candidate) =>
  existsSync(candidate)
)

if (!routeRegistryPath) {
  throw new Error(
    "Unable to locate sidepanel-route-registry.tsx for persona parity test"
  )
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("sidepanel route registry persona parity", () => {
  it("registers a dedicated persona sidepanel route", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/persona"/)
  })

  it("keeps persona and coding-agent routes separate", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/agent"/)
    expect(routeRegistrySource).toMatch(/path:\s*"\/persona"/)
  })
})
