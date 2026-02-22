import { describe, expect, it, vi } from "vitest"
import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"
import {
  buildDefaultItemsViewPresets,
  extractImageUrl,
  filterSourcesForReader,
  isSystemItemsViewPresetId,
  ITEM_PAGE_SIZE,
  ITEMS_PAGE_SIZE_STORAGE_KEY,
  ITEMS_VIEW_PRESETS_STORAGE_KEY,
  loadPersistedItemsViewPresets,
  loadPersistedItemPageSize,
  normalizeItemPageSize,
  orderSourcesForReader,
  persistItemsViewPresets,
  persistItemPageSize,
  provisionItemsViewPresets,
  resolveSelectedItemId,
  shouldReloadItemsAfterReviewMutation,
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

describe("item page-size persistence helpers", () => {
  it("normalizes supported and unsupported page-size values", () => {
    expect(normalizeItemPageSize(50)).toBe(50)
    expect(normalizeItemPageSize("100")).toBe(100)
    expect(normalizeItemPageSize("12")).toBe(ITEM_PAGE_SIZE)
    expect(normalizeItemPageSize(null)).toBe(ITEM_PAGE_SIZE)
  })

  it("loads persisted page-size from storage when valid", () => {
    const storage = {
      getItem: (key: string) => (key === ITEMS_PAGE_SIZE_STORAGE_KEY ? "50" : null)
    }
    expect(loadPersistedItemPageSize(storage)).toBe(50)
  })

  it("falls back to default when persisted value is invalid or storage throws", () => {
    const invalidStorage = {
      getItem: () => "17"
    }
    const throwingStorage = {
      getItem: () => {
        throw new Error("unavailable")
      }
    }
    expect(loadPersistedItemPageSize(invalidStorage)).toBe(ITEM_PAGE_SIZE)
    expect(loadPersistedItemPageSize(throwingStorage)).toBe(ITEM_PAGE_SIZE)
  })

  it("persists normalized page-size safely", () => {
    const setItem = vi.fn()
    persistItemPageSize({ setItem }, 50)
    expect(setItem).toHaveBeenCalledWith(ITEMS_PAGE_SIZE_STORAGE_KEY, "50")

    persistItemPageSize({ setItem }, 19)
    expect(setItem).toHaveBeenLastCalledWith(
      ITEMS_PAGE_SIZE_STORAGE_KEY,
      String(ITEM_PAGE_SIZE)
    )
  })
})

describe("items view preset persistence helpers", () => {
  it("loads valid saved presets from storage", () => {
    const storage = {
      getItem: (key: string) =>
        key === ITEMS_VIEW_PRESETS_STORAGE_KEY
          ? JSON.stringify([
              {
                id: "preset-1",
                name: "Unread tech",
                sourceId: 4,
                smartFilter: "unread",
                statusFilter: "ingested",
                searchQuery: "ai"
              }
            ])
          : null
    }
    expect(loadPersistedItemsViewPresets(storage)).toEqual([
      {
        id: "preset-1",
        name: "Unread tech",
        sourceId: 4,
        smartFilter: "unread",
        statusFilter: "ingested",
        searchQuery: "ai"
      }
    ])
  })

  it("drops invalid entries and handles parse/storage errors", () => {
    const mixedStorage = {
      getItem: () =>
        JSON.stringify([
          {
            id: "good-1",
            name: "Good",
            sourceId: null,
            smartFilter: "all",
            statusFilter: "all",
            searchQuery: ""
          },
          {
            id: "",
            name: "Bad",
            sourceId: 1,
            smartFilter: "all",
            statusFilter: "all",
            searchQuery: ""
          }
        ])
    }
    const throwingStorage = {
      getItem: () => {
        throw new Error("blocked")
      }
    }

    expect(loadPersistedItemsViewPresets(mixedStorage)).toHaveLength(1)
    expect(loadPersistedItemsViewPresets(throwingStorage)).toEqual([])
  })

  it("persists only valid presets", () => {
    const setItem = vi.fn()
    persistItemsViewPresets(
      { setItem },
      [
        {
          id: "preset-1",
          name: "Unread",
          sourceId: 1,
          smartFilter: "unread",
          statusFilter: "ingested",
          searchQuery: "alpha"
        },
        {
          id: "",
          name: "Invalid",
          sourceId: 2,
          smartFilter: "all",
          statusFilter: "all",
          searchQuery: ""
        }
      ] as any
    )

    expect(setItem).toHaveBeenCalledTimes(1)
    const payload = setItem.mock.calls[0]?.[1]
    expect(typeof payload).toBe("string")
    const parsed = JSON.parse(String(payload))
    expect(parsed).toEqual([
      {
        id: "preset-1",
        name: "Unread",
        sourceId: 1,
        smartFilter: "unread",
        statusFilter: "ingested",
        searchQuery: "alpha"
      }
    ])
  })

  it("provisions default triage views and keeps deterministic ordering", () => {
    const defaults = buildDefaultItemsViewPresets()
    const provisioned = provisionItemsViewPresets([], defaults)

    expect(provisioned.map((preset) => preset.id)).toEqual([
      "system-unread-today",
      "system-high-priority",
      "system-needs-review"
    ])
  })

  it("keeps custom presets sorted after system defaults", () => {
    const defaults = buildDefaultItemsViewPresets()
    const provisioned = provisionItemsViewPresets(
      [
        {
          id: "custom-z",
          name: "Zulu",
          sourceId: null,
          smartFilter: "all",
          statusFilter: "all",
          searchQuery: ""
        },
        {
          id: "custom-a",
          name: "Alpha",
          sourceId: null,
          smartFilter: "all",
          statusFilter: "all",
          searchQuery: ""
        }
      ],
      defaults
    )

    expect(provisioned.map((preset) => preset.id)).toEqual([
      "system-unread-today",
      "system-high-priority",
      "system-needs-review",
      "custom-a",
      "custom-z"
    ])
  })

  it("detects system preset ids", () => {
    expect(isSystemItemsViewPresetId("system-unread-today")).toBe(true)
    expect(isSystemItemsViewPresetId("custom-view")).toBe(false)
    expect(isSystemItemsViewPresetId(null)).toBe(false)
  })
})

describe("orderSourcesForReader", () => {
  it("prioritizes selected and active sources before inactive sources", () => {
    const sources = [
      makeSource({
        id: 2,
        name: "Inactive Source",
        active: false,
        last_scraped_at: "2026-02-20T00:00:00Z"
      }),
      makeSource({
        id: 3,
        name: "Active Healthy",
        active: true,
        status: "healthy",
        last_scraped_at: "2026-02-21T00:00:00Z"
      }),
      makeSource({
        id: 1,
        name: "Selected Source",
        active: true,
        status: "error",
        last_scraped_at: "2026-02-22T00:00:00Z"
      })
    ]

    const ordered = orderSourcesForReader(sources, 1)
    expect(ordered.map((source) => source.id)).toEqual([1, 3, 2])
  })
})

describe("shouldReloadItemsAfterReviewMutation", () => {
  it("reloads when reviewed state can change result membership", () => {
    expect(shouldReloadItemsAfterReviewMutation("unread")).toBe(true)
    expect(shouldReloadItemsAfterReviewMutation("reviewed")).toBe(true)
    expect(shouldReloadItemsAfterReviewMutation("todayUnread")).toBe(true)
  })

  it("skips reload when reviewed state does not affect current membership", () => {
    expect(shouldReloadItemsAfterReviewMutation("all")).toBe(false)
    expect(shouldReloadItemsAfterReviewMutation("today")).toBe(false)
  })
})
