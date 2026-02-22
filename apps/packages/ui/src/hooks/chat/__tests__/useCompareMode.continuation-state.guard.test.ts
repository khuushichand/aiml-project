import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("useCompareMode continuation-state persistence guard", () => {
  it("keeps continuation-mode state in compare hydration and save payloads", () => {
    const sourcePath = path.resolve(__dirname, "../useCompareMode.ts")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("compareContinuationModeByCluster")
    expect(source).toContain("setCompareContinuationModeForCluster")
    expect(source).toContain("saved.compareContinuationModeByCluster")
  })
})
