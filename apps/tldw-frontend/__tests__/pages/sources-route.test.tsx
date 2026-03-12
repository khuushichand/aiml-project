import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("sources Next.js page shims", () => {
  it("loads the shared route modules for user and admin sources pages", () => {
    expect(loadSource("tldw-frontend/pages/sources.tsx", "apps/tldw-frontend/pages/sources.tsx")).toContain(
      'dynamic(() => import("@/routes/option-sources"), { ssr: false })'
    )
    expect(
      loadSource("tldw-frontend/pages/sources/new.tsx", "apps/tldw-frontend/pages/sources/new.tsx")
    ).toContain(
      'dynamic(() => import("@/routes/option-sources-new"), { ssr: false })'
    )
    expect(
      loadSource(
        "tldw-frontend/pages/sources/[sourceId].tsx",
        "apps/tldw-frontend/pages/sources/[sourceId].tsx"
      )
    ).toContain(
      'dynamic(() => import("@/routes/option-sources-detail"), { ssr: false })'
    )
    expect(
      loadSource("tldw-frontend/pages/admin/sources.tsx", "apps/tldw-frontend/pages/admin/sources.tsx")
    ).toContain(
      'dynamic(() => import("@/routes/option-admin-sources"), { ssr: false })'
    )
  })
})
