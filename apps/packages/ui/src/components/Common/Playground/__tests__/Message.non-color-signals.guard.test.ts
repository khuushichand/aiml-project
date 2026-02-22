import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundMessage non-color signal guard", () => {
  it("keeps icon+text redundancy for mood and compare states", () => {
    const sourcePath = path.resolve(__dirname, "../Message.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("message-mood-indicator")
    expect(source).toContain("Mood:")
    expect(source).toContain("playground:composer.compareSelectedTag")
    expect(source).toContain("aria-pressed={props.compareSelected}")
    expect(source).toContain("AlertTriangle")
    expect(source).toContain("CheckCircle2")
    expect(source).toContain("error.label")
    expect(source).toContain("playground:composer.compareChosenLabel")
  })
})
