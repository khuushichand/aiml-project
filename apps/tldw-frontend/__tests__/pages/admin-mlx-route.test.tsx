import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing admin mlx page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("admin mlx Next.js page shim", () => {
  it("loads the admin mlx route module with a visible loading fallback", () => {
    const source = loadSource(
      "pages/admin/mlx.tsx",
      "tldw-frontend/pages/admin/mlx.tsx",
      "apps/tldw-frontend/pages/admin/mlx.tsx"
    )

    expect(source).toContain('dynamic(() => import("@/routes/option-admin-mlx"), {')
    expect(source).toContain("loading: () => (")
    expect(source).toContain('testId="admin-mlx-route-loading"')
  })
})
