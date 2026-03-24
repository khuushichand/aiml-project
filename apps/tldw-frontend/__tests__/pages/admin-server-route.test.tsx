import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const loadSource = (...candidates: string[]) => {
  const sourcePath = candidates.find((candidate) => existsSync(candidate))
  if (!sourcePath) {
    throw new Error(`Missing page shim: ${candidates.join(" | ")}`)
  }
  return readFileSync(sourcePath, "utf8")
}

describe("admin server Next.js page shim", () => {
  it("loads the shared admin server route module", () => {
    expect(
      loadSource(
        path.resolve(__dirname, "..", "..", "pages", "admin", "server.tsx"),
        path.resolve(process.cwd(), "pages", "admin", "server.tsx")
      )
    ).toMatch(
      /dynamic\(\(\) => import\("@\/routes\/option-admin-server"\),\s*\{\s*ssr:\s*false\s*\}\)/
    )
  })
})
