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
  throw new Error("Unable to locate route-registry.tsx for chat workflows route test")
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

describe("chat workflows route wiring", () => {
  it("registers the chat workflows route in the shared route registry", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/chat-workflows"/)
    expect(routeRegistrySource).toMatch(
      /const OptionChatWorkflows = lazy\(\(\) => import\("\.\/option-chat-workflows"\)\)/
    )
  })
})
