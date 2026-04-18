import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const readWritingSource = (relativePath: string) =>
  fs.readFileSync(path.resolve(__dirname, "..", relativePath), "utf8")

describe("writing review comment guards", () => {
  it("removes `as any` casts from the new manuscript UI surfaces", () => {
    const files = [
      "AIAgentTab.tsx",
      "CharacterWorldTab.tsx",
      "ResearchTab.tsx",
      path.join("modals", "ConnectionWebModal.tsx"),
    ]

    for (const file of files) {
      expect(readWritingSource(file)).not.toContain("as any")
    }
  })

  it("moves citation mark styling out of the TipTap extension", () => {
    const extensionSource = readWritingSource(path.join("extensions", "CitationExtension.ts"))
    const cssSource = fs.readFileSync(
      path.resolve(__dirname, "../../../../assets/tailwind-shared.css"),
      "utf8",
    )

    expect(extensionSource).toContain('class: "citation-mark"')
    expect(extensionSource).not.toContain("style:")
    expect(cssSource).toContain(".citation-mark")
  })
})
