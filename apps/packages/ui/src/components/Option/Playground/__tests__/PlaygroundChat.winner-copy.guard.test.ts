import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundChat winner copy guard", () => {
  it("keeps winner-selection copy in plain language", () => {
    const sourcePath = path.resolve(__dirname, "../PlaygroundChat.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("playground:composer.comparePrimaryOff")
    expect(source).toContain("Use as main response")
    expect(source).toContain("playground:composer.compareContinueWinner")
    expect(source).toContain("Continue with winner")
    expect(source).toContain("playground:composer.compareKeepComparing")
    expect(source).toContain("Keep comparing")
  })
})
