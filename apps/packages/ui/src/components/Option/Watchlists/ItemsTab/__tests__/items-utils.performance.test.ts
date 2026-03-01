import { describe, expect, it } from "vitest"
import type { ScrapedItem } from "@/types/watchlists"
import { resolveSelectedItemId, sortItemsForReader } from "../items-utils"

const buildItems = (count: number): ScrapedItem[] =>
  Array.from({ length: count }, (_unused, index) => {
    const id = index + 1
    return {
      id,
      run_id: Math.floor(index / 10) + 1,
      job_id: (index % 25) + 1,
      source_id: (index % 200) + 1,
      media_id: null,
      media_uuid: null,
      url: `https://example.com/article-${id}`,
      title: `Article ${id}`,
      summary: `Summary ${id}`,
      content: `Content ${id}`,
      published_at: new Date(2026, 1, 24, 10, index % 60, index % 60).toISOString(),
      tags: index % 2 === 0 ? ["ai"] : ["news"],
      status: "ingested",
      reviewed: index % 4 === 0,
      created_at: "2026-02-24T10:00:00Z"
    }
  })

describe("items-utils high-volume performance guards", () => {
  it("keeps unread-first sorting and selected-item resolution bounded", () => {
    const items = buildItems(8000)

    const startedAt = performance.now()
    const sorted = sortItemsForReader(items, "unreadFirst")
    const selected = resolveSelectedItemId(null, sorted)
    const elapsed = performance.now() - startedAt

    expect(sorted).toHaveLength(8000)
    expect(selected).toBe(sorted[0].id)
    expect(elapsed).toBeLessThan(250)
  })

  it("keeps bulk reviewed-state mapping bounded for large selections", () => {
    const items = buildItems(8000)
    const selectedIds = new Set(items.slice(0, 1200).map((item) => item.id))

    const startedAt = performance.now()
    const updated = items.map((item) =>
      selectedIds.has(item.id) ? { ...item, reviewed: true } : item
    )
    const elapsed = performance.now() - startedAt

    expect(updated).toHaveLength(8000)
    expect(updated.filter((item) => item.reviewed).length).toBeGreaterThan(1200)
    expect(elapsed).toBeLessThan(200)
  })
})
