import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"
import { describe, expect, it } from "vitest"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(
  testDir,
  "../index.tsx"
)

describe("WritingPlayground list guard", () => {
  it("does not rely on the deprecated Ant Design List component", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).not.toContain("\n  List,\n")
    expect(source).not.toContain("<List")
    expect(source).not.toContain("List.Item")
  })
})
