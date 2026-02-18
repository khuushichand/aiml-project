import { describe, expect, it } from "vitest"
import {
  buildWikilinkIndex,
  getActiveWikilinkQuery,
  insertWikilinkAtCursor,
  renderContentWithResolvedWikilinks,
  resolveWikilinkTitle,
  tokenizeWikilinks
} from "../wikilinks"

describe("notes wikilink utilities", () => {
  it("tokenizes wikilinks with positions", () => {
    const content = "See [[Alpha Note]] and [[Beta Note]]."
    const tokens = tokenizeWikilinks(content)
    expect(tokens).toEqual([
      { raw: "[[Alpha Note]]", title: "Alpha Note", start: 4, end: 18 },
      { raw: "[[Beta Note]]", title: "Beta Note", start: 23, end: 36 }
    ])
  })

  it("resolves ambiguous titles with deterministic id fallback", () => {
    const index = buildWikilinkIndex([
      { id: "note-3", title: "Shared" },
      { id: "note-1", title: "Shared" },
      { id: "note-2", title: "Shared" }
    ])
    expect(resolveWikilinkTitle("Shared", index)).toBe("note-1")
  })

  it("renders resolved wikilinks as note:// anchors", () => {
    const index = buildWikilinkIndex([
      { id: "note-a", title: "Alpha Note" },
      { id: "note-b", title: "Beta Note" }
    ])
    const content = "Link [[Alpha Note]] and keep [[Missing Note]] plain."
    const rendered = renderContentWithResolvedWikilinks(content, index)
    expect(rendered).toContain("[[[Alpha Note]]](note://note-a)")
    expect(rendered).toContain("[[Missing Note]]")
  })

  it("detects active wikilink query and inserts selected title", () => {
    const content = "Research [[Al"
    const query = getActiveWikilinkQuery(content, content.length)
    expect(query).toEqual({
      start: 9,
      end: 13,
      query: "Al"
    })
    const inserted = insertWikilinkAtCursor(content, query!, "Alpha Note")
    expect(inserted.content).toBe("Research [[Alpha Note]]")
    expect(inserted.cursor).toBe(23)
  })
})
