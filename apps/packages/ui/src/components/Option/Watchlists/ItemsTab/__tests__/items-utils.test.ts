import { describe, expect, it } from "vitest"
import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"
import {
  extractImageUrl,
  filterSourcesForReader,
  resolveSelectedItemId,
  stripHtmlToText
} from "../items-utils"

const makeSource = (overrides: Partial<WatchlistSource> = {}): WatchlistSource => ({
  id: overrides.id ?? 1,
  name: overrides.name ?? "Example Feed",
  url: overrides.url ?? "https://example.com/rss.xml",
  source_type: overrides.source_type ?? "rss",
  active: overrides.active ?? true,
  tags: overrides.tags ?? [],
  created_at: overrides.created_at ?? "2026-01-01T00:00:00Z",
  updated_at: overrides.updated_at ?? "2026-01-01T00:00:00Z",
  ...overrides
})

const makeItem = (overrides: Partial<ScrapedItem> = {}): ScrapedItem => ({
  id: overrides.id ?? 1,
  run_id: overrides.run_id ?? 10,
  job_id: overrides.job_id ?? 20,
  source_id: overrides.source_id ?? 1,
  media_id: overrides.media_id ?? null,
  media_uuid: overrides.media_uuid ?? null,
  url: overrides.url ?? "https://example.com/post",
  title: overrides.title ?? "Sample item",
  summary: overrides.summary ?? "Summary",
  published_at: overrides.published_at ?? "2026-01-01T00:00:00Z",
  tags: overrides.tags ?? [],
  status: overrides.status ?? "ingested",
  reviewed: overrides.reviewed ?? false,
  created_at: overrides.created_at ?? "2026-01-01T00:00:00Z",
  ...overrides
})

describe("filterSourcesForReader", () => {
  it("returns all sources for empty query", () => {
    const sources = [
      makeSource({ id: 1, name: "Alpha" }),
      makeSource({ id: 2, name: "Beta" })
    ]
    expect(filterSourcesForReader(sources, "")).toEqual(sources)
  })

  it("matches by name, url, and tags", () => {
    const sources = [
      makeSource({ id: 1, name: "Tech Daily", tags: ["tech"] }),
      makeSource({ id: 2, name: "World News", url: "https://news.example.com" }),
      makeSource({ id: 3, name: "Cooking", tags: ["food"] })
    ]

    expect(filterSourcesForReader(sources, "tech").map((s) => s.id)).toEqual([1])
    expect(filterSourcesForReader(sources, "news.example.com").map((s) => s.id)).toEqual([2])
    expect(filterSourcesForReader(sources, "food").map((s) => s.id)).toEqual([3])
  })
})

describe("resolveSelectedItemId", () => {
  it("returns null when no items exist", () => {
    expect(resolveSelectedItemId(3, [])).toBeNull()
  })

  it("keeps current id when still present", () => {
    const items = [makeItem({ id: 5 }), makeItem({ id: 6 })]
    expect(resolveSelectedItemId(6, items)).toBe(6)
  })

  it("falls back to first item when current id is missing", () => {
    const items = [makeItem({ id: 5 }), makeItem({ id: 6 })]
    expect(resolveSelectedItemId(99, items)).toBe(5)
  })
})

describe("stripHtmlToText", () => {
  it("strips html and collapses whitespace", () => {
    const html = "<p>Hello <strong>world</strong></p><p>  Next&nbsp;line </p>"
    expect(stripHtmlToText(html)).toBe("Hello world Next line")
  })
})

describe("extractImageUrl", () => {
  it("extracts first image URL from html", () => {
    const html = '<p>One</p><img src="https://example.com/image.jpg" alt="img" />'
    expect(extractImageUrl(html)).toBe("https://example.com/image.jpg")
  })

  it("extracts first image URL from markdown", () => {
    const markdown = "Text ![hero](https://example.com/hero.png) after"
    expect(extractImageUrl(markdown)).toBe("https://example.com/hero.png")
  })

  it("returns null when no image exists", () => {
    expect(extractImageUrl("no image here")).toBeNull()
  })
})
