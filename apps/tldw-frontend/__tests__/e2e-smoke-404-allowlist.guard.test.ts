import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const sourcePath = path.resolve(process.cwd(), "e2e/smoke/smoke.setup.ts")

describe("smoke 404 allowlist guard", () => {
  it("treats the intentional /404 route response as allowlisted noise", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).toContain('"/404"')
  })
})
