import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("writing essentials strip guard", () => {
  it("includes top-bar controls and settings in index", () => {
    const source = fs.readFileSync(path.resolve(__dirname, "../index.tsx"), "utf8")
    expect(source).toContain("writing-topbar-model")
    expect(source).toContain("writing-topbar-generate")
    expect(source).toContain("temperature")
    expect(source).toContain("max_tokens")
    expect(source).toContain("token_streaming")
  })
})
