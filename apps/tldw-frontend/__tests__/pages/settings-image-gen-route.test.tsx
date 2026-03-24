import { existsSync, readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing settings image-gen page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("settings image-gen Next.js page shim", () => {
  it("redirects the legacy alias to the canonical image-generation settings route", () => {
    const source = loadSource(
      "pages/settings/image-gen.tsx",
      "tldw-frontend/pages/settings/image-gen.tsx",
      "apps/tldw-frontend/pages/settings/image-gen.tsx"
    )

    expect(source).toContain("RouteRedirect")
    expect(source).toContain('to="/settings/image-generation"')
    expect(source).not.toContain("ImageGenerationSettings")
  })
})
