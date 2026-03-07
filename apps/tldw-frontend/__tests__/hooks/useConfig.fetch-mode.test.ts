import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

describe("useConfig docs bootstrap fetch mode", () => {
  it("uses non-credentialed fetch for docs-info bootstrap", () => {
    const sourcePath = join(
      process.cwd(),
      "apps",
      "tldw-frontend",
      "hooks",
      "useConfig.tsx"
    )
    const source = readFileSync(sourcePath, "utf-8")

    expect(source).toContain(
      "fetch(`${base}/api/v1/config/docs-info`, { credentials: 'omit' })"
    )
  })
})

