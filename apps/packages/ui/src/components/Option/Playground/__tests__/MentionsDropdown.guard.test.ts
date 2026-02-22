import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("MentionsDropdown guard", () => {
  it("keeps zero-result keyboard guardrails and helper copy", () => {
    const sourcePath = path.resolve(__dirname, "../MentionsDropdown.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("if (tabs.length === 0) return")
    expect(source).toContain("playground:mentions.noTabsHint")
    expect(source).toContain('role="listbox"')
  })
})
