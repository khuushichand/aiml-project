import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing draft mode guard", () => {
  it("keeps editor + quick controls in draft mode", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain('workspaceMode === "draft"')
    expect(source).toContain("writing-section-draft-editor")
    expect(source).toContain("writing-section-draft-inspector")
    expect(source).toContain("temperature")
    expect(source).toContain("max_tokens")
    expect(source).toContain("token_streaming")
  })
})
