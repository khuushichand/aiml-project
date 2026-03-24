import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing admin watchlists items page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("admin watchlists items Next.js page shim", () => {
  it("renders the dedicated watchlists items route instead of the generic watchlists admin page", () => {
    const source = loadSource(
      "pages/admin/watchlists-items.tsx",
      "tldw-frontend/pages/admin/watchlists-items.tsx",
      "apps/tldw-frontend/pages/admin/watchlists-items.tsx"
    )

    expect(source).toContain('option-admin-watchlists-items')
    expect(source).not.toContain('import("@/routes/option-admin-watchlists"),')
  })
})
