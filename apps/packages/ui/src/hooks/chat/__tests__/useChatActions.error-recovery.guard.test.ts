import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("useChatActions interruption recovery guard", () => {
  it("marks interrupted assistant variants with recovery metadata", () => {
    const sourcePath = path.resolve(__dirname, "../useChatActions.ts")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("interrupted: true")
    expect(source).toContain("interruptionReason")
    expect(source).toContain("interruptedAt: Date.now()")
  })
})
