import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"
import { describe, expect, it } from "vitest"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(testDir, "../CodeBlock.tsx")

describe("CodeBlock prism keys", () => {
  it("passes Prism keys directly instead of spreading them through JSX props", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).toContain("key={i}")
    expect(source).toContain("key={key}")
    expect(source).not.toContain("getLineProps({ line, key: i })")
    expect(source).not.toContain("getTokenProps({ token, key })")
  })
})
