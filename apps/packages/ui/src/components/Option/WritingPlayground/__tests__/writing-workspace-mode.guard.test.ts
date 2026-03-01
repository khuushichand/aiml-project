import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing workspace mode guard", () => {
  it("includes draft/manage mode switch and test ids", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain("writing-workspace-mode-switch")
    expect(source).toContain("writing-mode-draft")
    expect(source).toContain("writing-mode-manage")
    expect(source).toContain("writing-section-sessions")
  })
})
