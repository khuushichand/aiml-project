import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const sourcePath = path.resolve(
  process.cwd(),
  "src/components/Option/WorkspacePlayground/ShareDialog.tsx"
)

describe("ShareDialog modal prop guard", () => {
  it("uses destroyOnHidden instead of the deprecated destroyOnClose prop", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).toContain("destroyOnHidden")
    expect(source).not.toContain("destroyOnClose")
  })
})
