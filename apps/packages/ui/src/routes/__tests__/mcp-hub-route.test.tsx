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
  throw new Error("Unable to locate route-registry.tsx for MCP Hub route test")
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("mcp hub route wiring", () => {
  it("registers mcp hub in route registry for both workspace and settings entry", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/mcp-hub"/)
    expect(routeRegistrySource).toMatch(/path:\s*"\/settings\/mcp-hub"/)
  })
})
