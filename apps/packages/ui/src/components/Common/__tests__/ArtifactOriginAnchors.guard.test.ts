import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("Artifact origin anchor guard", () => {
  it("keeps code/table artifact origin anchors for jump-back workflows", () => {
    const codeBlockPath = path.resolve(__dirname, "../CodeBlock.tsx")
    const tableBlockPath = path.resolve(__dirname, "../TableBlock.tsx")
    const codeBlockSource = fs.readFileSync(codeBlockPath, "utf8")
    const tableBlockSource = fs.readFileSync(tableBlockPath, "utf8")

    expect(codeBlockSource).toContain("artifact-origin-")
    expect(codeBlockSource).toContain("data-artifact-origin")
    expect(tableBlockSource).toContain("artifact-origin-")
    expect(tableBlockSource).toContain("data-artifact-origin")
  })
})
