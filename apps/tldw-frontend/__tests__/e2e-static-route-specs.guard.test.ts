import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const STATIC_ROUTE_SPECS = [
  "e2e/workflows/hosted-placeholder-routes.spec.ts",
  "e2e/workflows/route-placeholder-settings.spec.ts",
  "e2e/workflows/tier-2-features/documentation.spec.ts",
  "e2e/workflows/tier-4-admin/privileges.spec.ts",
]

describe("static route specs", () => {
  it("avoid brittle networkidle waits", () => {
    for (const relativePath of STATIC_ROUTE_SPECS) {
      const source = readFileSync(path.join(process.cwd(), relativePath), "utf8")
      expect(source).not.toContain('waitForLoadState("networkidle")')
    }
  })
})
