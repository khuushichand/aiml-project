import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing prompt chunks guard", () => {
  it("includes prompt chunks display behind showPromptChunks toggle", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain("showPromptChunks")
    expect(source).toContain("writing-section-prompt-chunks")
    expect(source).toContain("promptChunkData")
  })
})
