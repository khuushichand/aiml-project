import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const routeCandidates = [
  "src/routes/option-scheduled-tasks.tsx",
  "../packages/ui/src/routes/option-scheduled-tasks.tsx",
  "apps/packages/ui/src/routes/option-scheduled-tasks.tsx"
]

const routePath = routeCandidates.find((candidate) => existsSync(candidate))

if (!routePath) {
  throw new Error("Unable to locate option-scheduled-tasks route for scheduled tasks route test")
}

const routeSource = readFileSync(routePath, "utf8")

describe("scheduled tasks route wiring", () => {
  it("registers the scheduled tasks route shell", () => {
    expect(routeSource).toContain("ScheduledTasksPage")
    expect(routeSource).toContain("RouteErrorBoundary")
    expect(routeSource).toContain("OptionLayout")
  })
})
