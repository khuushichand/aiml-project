import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"
import {
  FLASHCARDS_HELP_DOC_BASE_URL,
  FLASHCARDS_HELP_LINKS
} from "../help-links"

const DOC_PATH = path.resolve(
  process.cwd(),
  "../../../Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md"
)

const toAnchorSlug = (heading: string): string =>
  heading
    .trim()
    .toLowerCase()
    .replace(/`/g, "")
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")

const extractHeadingAnchors = (markdown: string): Set<string> => {
  const anchors = new Set<string>()
  for (const line of markdown.split(/\r?\n/)) {
    const match = line.match(/^#{1,6}\s+(.+?)\s*$/)
    if (!match) continue
    anchors.add(toAnchorSlug(match[1]))
  }
  return anchors
}

describe("flashcards help links", () => {
  it("uses versioned guide URLs", () => {
    expect(FLASHCARDS_HELP_DOC_BASE_URL).toContain("/blob/HEAD/")
    expect(FLASHCARDS_HELP_DOC_BASE_URL).toContain(
      "Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md"
    )
  })

  it("includes a structured import guide anchor", () => {
    expect(FLASHCARDS_HELP_LINKS.structuredImport).toContain(
      "#structured-q-and-a-preview"
    )
  })

  it("matches anchors present in the flashcards study guide", () => {
    const markdown = fs.readFileSync(DOC_PATH, "utf8")
    const anchors = extractHeadingAnchors(markdown)
    for (const href of Object.values(FLASHCARDS_HELP_LINKS)) {
      const [base, hash] = href.split("#")
      expect(base).toBe(FLASHCARDS_HELP_DOC_BASE_URL)
      expect(hash).toBeTruthy()
      expect(anchors.has(hash)).toBe(true)
    }
  })

  it("documents current import payload fields used by transfer help", () => {
    const markdown = fs.readFileSync(DOC_PATH, "utf8")
    expect(markdown).toContain("Deck")
    expect(markdown).toContain("Front")
    expect(markdown).toContain("Back")
    expect(markdown).toContain("Tags")
    expect(markdown).toContain("Model_Type")
    expect(markdown).toContain("is_cloze")
  })
})
