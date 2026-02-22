import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("MessageSource transparency guard", () => {
  it("keeps why-this-source diagnostics and knowledge-panel jump action", () => {
    const sourcePath = path.resolve(__dirname, "../MessageSource.tsx")
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).toContain("sourceWhyTitle")
    expect(source).toContain("sourceWhyChunk")
    expect(source).toContain("sourceWhyStrategy")
    expect(source).toContain("sourceOpenKnowledgePanel")
  })
})
