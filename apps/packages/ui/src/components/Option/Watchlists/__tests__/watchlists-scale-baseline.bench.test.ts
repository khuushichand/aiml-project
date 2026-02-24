// @vitest-environment jsdom

import { describe, expect, it } from "vitest"
import {
  filterSourcesForReader,
  orderSourcesForReader,
  resolveSelectedItemId,
  sortItemsForReader
} from "../ItemsTab/items-utils"
import {
  dedupeRunNotificationEvents,
  groupRunNotificationEvents,
  type RunNotificationEvent
} from "../RunsTab/run-notifications"

const measure = <T>(fn: () => T): { value: T; durationMs: number } => {
  const startedAt = performance.now()
  const value = fn()
  const durationMs = performance.now() - startedAt
  return { value, durationMs }
}

const buildSources = (count: number) =>
  Array.from({ length: count }, (_value, index) => {
    const id = index + 1
    return {
      id,
      name: `Source ${id}`,
      url: `https://example.com/source-${id}.xml`,
      source_type: index % 3 === 0 ? "site" : "rss",
      active: true,
      tags: index % 2 === 0 ? ["research"] : ["news"],
      created_at: "2026-02-20T00:00:00Z",
      updated_at: "2026-02-20T00:00:00Z",
      status: "healthy"
    }
  })

const buildItems = (count: number) =>
  Array.from({ length: count }, (_value, index) => {
    const id = index + 1
    const minute = String(index % 60).padStart(2, "0")
    return {
      id,
      run_id: 1,
      job_id: 1,
      source_id: (index % 200) + 1,
      url: `https://example.com/article-${id}`,
      title: `Article ${id}`,
      summary: `Summary ${id}`,
      tags: ["watchlists"],
      status: index % 4 === 0 ? "filtered" : "ingested",
      reviewed: index % 3 === 0,
      created_at: `2026-02-23T08:${minute}:00Z`,
      published_at: `2026-02-23T08:${minute}:00Z`
    }
  })

const buildEvents = (count: number): RunNotificationEvent[] =>
  Array.from({ length: count }, (_value, index) => {
    const runId = index + 1
    const kind = index % 7 === 0 ? "failed" : index % 5 === 0 ? "stalled" : "completed"
    return {
      eventKey: `${runId}:${kind}`,
      kind,
      runId,
      hint: kind === "failed" ? "retry source" : null
    }
  })

describe("Watchlists scale baseline budgets", () => {
  it("keeps source filter+ordering pipeline within budget for 5/50/200 feed profiles", () => {
    const profiles = [5, 50, 200]
    const timings = profiles.map((size) => {
      const sources = buildSources(size)
      const selectedId = Math.max(1, Math.floor(size / 2))
      const measured = measure(() => {
        const filtered = filterSourcesForReader(sources as any, "source")
        return orderSourcesForReader(filtered as any, selectedId)
      })
      return { size, durationMs: measured.durationMs, resultCount: measured.value.length }
    })

    console.info("[watchlists-scale] source_pipeline_ms", timings)
    const maxDuration = Math.max(...timings.map((entry) => entry.durationMs))
    expect(maxDuration).toBeLessThan(60)
  })

  it("keeps item sort pipeline within budget for high-volume reader payloads", () => {
    const profiles = [100, 1000, 5000]
    const timings = profiles.map((size) => {
      const items = buildItems(size)
      const measured = measure(() =>
        sortItemsForReader(items as any, "unreadFirst")
      )
      return { size, durationMs: measured.durationMs, resultCount: measured.value.length }
    })

    console.info("[watchlists-scale] items_sort_ms", timings)
    const maxDuration = Math.max(...timings.map((entry) => entry.durationMs))
    expect(maxDuration).toBeLessThan(300)
  })

  it("keeps selection and query-change pipelines within budget", () => {
    const items = buildItems(5000)
    const sources = buildSources(1000)
    const queries = ["s", "so", "sou", "source", "source 2", "research", "news"]

    const measured = measure(() => {
      let selectedId: number | null = null
      for (let index = 0; index < 250; index += 1) {
        selectedId = resolveSelectedItemId((index % items.length) + 1, items as any)
      }
      queries.forEach((query) => {
        filterSourcesForReader(sources as any, query)
      })
      return selectedId
    })

    console.info("[watchlists-scale] selection_filter_ms", measured.durationMs)
    expect(typeof measured.value).toBe("number")
    expect(measured.durationMs).toBeLessThan(180)
  })

  it("keeps run notification dedupe/group pipeline within budget under burst load", () => {
    const events = buildEvents(1000)
    const seenKeys = new Set<string>()

    const measured = measure(() => {
      const deduped = dedupeRunNotificationEvents(events, seenKeys)
      const grouped = groupRunNotificationEvents(deduped)
      return { dedupedCount: deduped.length, groupedCount: grouped.length }
    })

    console.info("[watchlists-scale] run_notifications_ms", measured.durationMs)
    expect(measured.value.dedupedCount).toBe(1000)
    expect(measured.value.groupedCount).toBeGreaterThan(0)
    expect(measured.durationMs).toBeLessThan(80)
  })
})
