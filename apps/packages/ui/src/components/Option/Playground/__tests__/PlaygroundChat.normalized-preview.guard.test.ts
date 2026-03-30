import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundChat normalized preview guard", () => {
  it("keeps normalized preview controls and budgeted snippets in compare cards", () => {
    const sourcePath = path.resolve(__dirname, "../PlaygroundCompareCluster.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("normalizedPreviewEnabled")
    expect(source).toContain("playground:composer.comparePreviewNormalized")
    expect(source).toContain("computeNormalizedPreviewBudget")
    expect(source).toContain("playground:composer.comparePreviewLabel")
    expect(source).toContain("playground:composer.comparePreviewBudget")
    expect(source).toContain("compare-normalized-preview-")
  })
})
