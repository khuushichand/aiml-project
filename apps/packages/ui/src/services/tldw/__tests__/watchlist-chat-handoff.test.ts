import { describe, expect, it } from "vitest"
import {
  buildWatchlistChatHint,
  normalizeWatchlistChatHandoffPayload,
  type WatchlistChatArticle,
  type WatchlistChatHandoffPayload
} from "../watchlist-chat-handoff"

describe("normalizeWatchlistChatHandoffPayload", () => {
  it("returns undefined for null", () => {
    expect(normalizeWatchlistChatHandoffPayload(null)).toBeUndefined()
  })

  it("returns undefined for non-object", () => {
    expect(normalizeWatchlistChatHandoffPayload("string")).toBeUndefined()
  })

  it("returns undefined for empty articles array", () => {
    expect(normalizeWatchlistChatHandoffPayload({ articles: [] })).toBeUndefined()
  })

  it("normalizes a single-article payload", () => {
    const input = {
      articles: [{ title: " My Title ", content: "Body text" }]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result).toEqual({
      articles: [{ title: "My Title", content: "Body text" }]
    })
  })

  it("filters out articles with no content and no title", () => {
    const input = {
      articles: [
        { title: "Good", content: "Has content" },
        { content: "  " } // empty after trim
      ]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result!.articles).toHaveLength(1)
    expect(result!.articles[0].title).toBe("Good")
  })

  it("keeps articles that have title but no content", () => {
    const input = {
      articles: [{ title: "Title Only", url: "https://example.com" }]
    }
    const result = normalizeWatchlistChatHandoffPayload(input)
    expect(result!.articles).toHaveLength(1)
  })
})

describe("buildWatchlistChatHint", () => {
  it("builds hint for single article with content", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "My Article", content: "Article body here", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("I'd like to discuss this article:")
    expect(hint).toContain('--- "My Article" ---')
    expect(hint).toContain("Article body here")
  })

  it("builds hint for multiple articles", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "First", content: "Body 1", sourceType: "item" },
        { title: "Second", content: "Body 2", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("I'd like to discuss these articles:")
    expect(hint).toContain('--- Article 1: "First" ---')
    expect(hint).toContain('--- Article 2: "Second" ---')
  })

  it("includes URL when available", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "With URL", url: "https://example.com", content: "Body", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("URL: https://example.com")
  })

  it("handles article with no content — uses title and url fallback", () => {
    const payload: WatchlistChatHandoffPayload = {
      articles: [
        { title: "No Content", url: "https://example.com", sourceType: "item" }
      ]
    }
    const hint = buildWatchlistChatHint(payload)
    expect(hint).toContain("No Content")
    expect(hint).toContain("https://example.com")
    expect(hint).toContain("Full content not available")
  })

  it("returns empty string for empty articles", () => {
    expect(buildWatchlistChatHint({ articles: [] })).toBe("")
  })
})
