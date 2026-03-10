import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const routeRegistryPathCandidates = [
  "packages/ui/src/routes/route-registry.tsx",
  "src/routes/route-registry.tsx",
  "../packages/ui/src/routes/route-registry.tsx",
  "apps/packages/ui/src/routes/route-registry.tsx"
]

const routeRegistryPath = routeRegistryPathCandidates.find((candidate) =>
  existsSync(candidate)
)

if (!routeRegistryPath) {
  throw new Error("Unable to locate route-registry.tsx for sources route test")
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("sources route wiring", () => {
  it("mounts shared Sources routes for user and admin pages", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/sources"/)
    expect(routeRegistrySource).toMatch(/path:\s*"\/sources\/new"/)
    expect(routeRegistrySource).toMatch(/path:\s*"\/sources\/:sourceId"/)
    expect(routeRegistrySource).toMatch(/path:\s*"\/admin\/sources"/)
  })
})
