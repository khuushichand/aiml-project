import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing companion page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("companion Next.js page shim", () => {
  it("loads the shared companion route module with a visible loading fallback", () => {
    const source = loadSource(
      "pages/companion.tsx",
      "tldw-frontend/pages/companion.tsx",
      "apps/tldw-frontend/pages/companion.tsx"
    )
    expect(source).toContain('dynamic(() => import("@/routes/option-companion"), {')
    expect(source).toContain("loading: () => (")
    expect(source).toContain('testId="companion-route-loading"')
    expect(source).not.toContain('RouteRedirect to="/companion"')
  })
})
