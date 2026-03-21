import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing admin watchlists runs page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("admin watchlists runs Next.js page shim", () => {
  it("renders a watchlists-specific placeholder instead of redirecting to server admin", () => {
    const source = loadSource(
      "pages/admin/watchlists-runs.tsx",
      "tldw-frontend/pages/admin/watchlists-runs.tsx",
      "apps/tldw-frontend/pages/admin/watchlists-runs.tsx"
    )

    expect(source).toContain("RoutePlaceholder")
    expect(source).toContain("Watchlist Runs Admin Is Coming Soon")
    expect(source).not.toContain('RouteRedirect to="/admin/server"')
  })
})
