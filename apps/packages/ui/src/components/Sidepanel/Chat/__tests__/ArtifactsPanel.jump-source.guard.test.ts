import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("ArtifactsPanel jump-to-source guard", () => {
  it("keeps jump-to-source action and fallback scroll event", () => {
    const sourcePath = path.resolve(__dirname, "../ArtifactsPanel.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("artifacts-jump-source")
    expect(source).toContain("artifactsJumpToSource")
    expect(source).toContain("artifact-origin-${active.id}")
    expect(source).toContain("tldw:scroll-to-latest")
    expect(source).toContain("tldw:focus-artifacts-trigger")
  })
})
