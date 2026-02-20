import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundChat diff preview guard", () => {
  it("keeps diff-highlighting and per-card cost chips in compare cards", () => {
    const sourcePath = path.resolve(__dirname, "../PlaygroundChat.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("compare-diff-toggle-")
    expect(source).toContain("compare-diff-preview-")
    expect(source).toContain("computeResponseDiffPreview")
    expect(source).toContain("playground:composer.compareDiffShow")
    expect(source).toContain("playground:composer.compareDiffVsLabel")
    expect(source).toContain("resolveMessageCostUsd")
    expect(source).toContain("playground:composer.compareCost")
  })
})
