import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"
import { describe, expect, it } from "vitest"

const testDir = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(testDir, "../TtsInspectorPanel.tsx")

describe("TtsInspectorPanel drawer prop guard", () => {
  it("uses Drawer size instead of the deprecated width prop", () => {
    const source = readFileSync(sourcePath, "utf8")

    expect(source).toContain("size={360}")
    expect(source).not.toContain("width={360}")
  })
})
