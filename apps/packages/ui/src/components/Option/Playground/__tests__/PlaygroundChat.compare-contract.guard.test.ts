import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundChat compare continuation contract guard", () => {
  it("keeps explicit continuation and resume notices for compare flow", () => {
    const sourcePath = path.resolve(__dirname, "../PlaygroundChat.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("playground:composer.compareContinueContract")
    expect(source).toContain("playground:composer.compareResumeContract")
    expect(source).toContain("setCompareMode(false)")
    expect(source).toContain("setCompareContinuationModeForCluster")
    expect(source).toContain("playground:composer.compareContinuationLabel")
  })
})
