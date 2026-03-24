import path from "node:path"

import { describe, expect, it } from "vitest"

import { prioritizeExtensionBuildCandidates } from "./extension-paths"

describe("prioritizeExtensionBuildCandidates", () => {
  it("prefers .output/chrome-mv3 over build/chrome-mv3", () => {
    const repoRoot = path.resolve("/tmp/tldw-extension")
    const buildPath = path.join(repoRoot, "build", "chrome-mv3")
    const outputPath = path.join(repoRoot, ".output", "chrome-mv3")

    expect(
      prioritizeExtensionBuildCandidates([buildPath, outputPath])
    ).toEqual([outputPath, buildPath])
  })

  it("keeps custom extension directories ahead of standard build outputs", () => {
    const repoRoot = path.resolve("/tmp/tldw-extension")
    const customPath = path.join(repoRoot, "fixtures", "packed-extension")
    const buildPath = path.join(repoRoot, "build", "chrome-mv3")
    const outputPath = path.join(repoRoot, ".output", "chrome-mv3")

    expect(
      prioritizeExtensionBuildCandidates([customPath, buildPath, outputPath])
    ).toEqual([customPath, outputPath, buildPath])
  })
})
