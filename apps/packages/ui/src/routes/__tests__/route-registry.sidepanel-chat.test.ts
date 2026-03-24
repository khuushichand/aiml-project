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
  throw new Error(
    "Unable to locate route-registry.tsx for sidepanel chat route test"
  )
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("sidepanel route registry chat parity", () => {
  it("registers a dedicated sidepanel chat route", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/chat"/)
    expect(routeRegistrySource).toContain("SidepanelChat")
  })

  it("keeps the sidepanel home resolver on the root route", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/"/)
    expect(routeRegistrySource).toContain("SidepanelHomeResolver")
  })
})
