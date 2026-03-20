import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const path = candidates.find((candidate) => existsSync(candidate))
  if (!path) {
    throw new Error(`Missing page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(path, "utf8")
}

describe("admin server Next.js page shim", () => {
  it("loads the shared admin server route module", () => {
    expect(
      loadSource(
        path.resolve(__dirname, "..", "..", "pages", "admin", "server.tsx"),
        path.resolve(process.cwd(), "pages", "admin", "server.tsx")
      )
    ).toContain('dynamic(() => import("@/routes/option-admin-server"), { ssr: false })')
  })
})
