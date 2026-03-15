import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing workspace mode guard", () => {
  it("no longer includes draft/manage mode switch (removed in IA restructure)", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).not.toContain("writing-workspace-mode-switch")
    expect(source).not.toContain("writing-mode-draft")
    expect(source).not.toContain("writing-mode-manage")
    expect(source).toContain("writing-section-prompt-chunks")
  })
})
