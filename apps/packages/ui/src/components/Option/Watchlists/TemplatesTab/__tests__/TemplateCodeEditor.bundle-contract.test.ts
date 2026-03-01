import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("TemplateCodeEditor bundle contract", () => {
  it("does not depend on next/dynamic so extension bundles can resolve imports", () => {
    const sourcePath = path.resolve(
      __dirname,
      "..",
      "TemplateCodeEditor.tsx"
    )
    const source = fs.readFileSync(sourcePath, "utf8")

    expect(source).not.toContain('from "next/dynamic"')
  })
})
