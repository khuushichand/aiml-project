import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing manage mode guard", () => {
  it("keeps all advanced sections behind manage mode", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain('workspaceMode === "manage"')
    expect(source).toContain("writing-section-manage-styling")
    expect(source).toContain("writing-section-manage-generation")
    expect(source).toContain("writing-section-manage-context")
    expect(source).toContain("writing-section-manage-analysis")
  })
})
