import { describe, expect, it } from "vitest"

import type { MediaNavigationNode } from "@/hooks/useMediaNavigation"
import {
  type MediaNavigationResumeEntry,
  resolveMediaNavigationResumeSelection,
  upsertMediaNavigationResumeEntries
} from "@/utils/media-navigation-resume"

const makeNode = (overrides: Partial<MediaNavigationNode>): MediaNavigationNode => ({
  id: overrides.id || "node",
  parent_id: overrides.parent_id ?? null,
  level: overrides.level ?? 0,
  title: overrides.title || "Untitled",
  order: overrides.order ?? 0,
  path_label: overrides.path_label ?? null,
  target_type: overrides.target_type || "char_range",
  target_start: overrides.target_start ?? 0,
  target_end: overrides.target_end ?? 10,
  target_href: overrides.target_href ?? null,
  source: overrides.source || "test",
  confidence: overrides.confidence ?? null
})

const makeEntry = (
  overrides: Partial<MediaNavigationResumeEntry>
): MediaNavigationResumeEntry => ({
  media_id: overrides.media_id || "media-1",
  node_id: overrides.node_id ?? "node-1",
  navigation_version: overrides.navigation_version ?? "v1",
  path_label: overrides.path_label ?? "1",
  title: overrides.title ?? "Chapter 1",
  level: overrides.level ?? 0,
  last_accessed_at: overrides.last_accessed_at ?? 1_000,
  updated_at: overrides.updated_at ?? 1_000
})

describe("media-navigation-resume", () => {
  it("enforces bounded LRU entries and reports eviction counts", () => {
    const entries: MediaNavigationResumeEntry[] = []
    for (let i = 0; i < 1002; i += 1) {
      entries.push(
        makeEntry({
          media_id: `media-${i}`,
          node_id: `node-${i}`,
          path_label: `${i}`,
          title: `Chapter ${i}`,
          last_accessed_at: 10_000 - i,
          updated_at: 10_000 - i
        })
      )
    }

    const result = upsertMediaNavigationResumeEntries({
      entries,
      nextEntry: {
        media_id: "media-new",
        node_id: "node-new",
        navigation_version: "v9",
        path_label: "99.1",
        title: "Section 99.1",
        level: 2
      },
      now: 20_000
    })

    expect(result.entries.length).toBe(1000)
    expect(result.evicted_lru_count).toBe(3)
    expect(result.evicted_stale_count).toBe(0)
    expect(result.entries[0].media_id).toBe("media-new")
  })

  it("prunes stale entries older than retention window", () => {
    const now = 1_000_000
    const result = upsertMediaNavigationResumeEntries({
      entries: [
        makeEntry({
          media_id: "fresh",
          last_accessed_at: now - 10,
          updated_at: now - 10
        }),
        makeEntry({
          media_id: "stale",
          last_accessed_at: now - 100_000,
          updated_at: now - 100_000
        })
      ],
      nextEntry: {
        media_id: "next",
        node_id: "next-node",
        navigation_version: "v1",
        path_label: "1",
        title: "Next",
        level: 0
      },
      now,
      maxEntries: 1000,
      maxAgeMs: 60_000
    })

    expect(result.evicted_stale_count).toBe(1)
    expect(result.entries.some((entry) => entry.media_id === "stale")).toBe(false)
    expect(result.entries.some((entry) => entry.media_id === "next")).toBe(true)
  })

  it("restores exact node only when navigation version still matches", () => {
    const nodes = [
      makeNode({ id: "chapter-1", title: "Chapter 1", path_label: "1", order: 1 })
    ]

    const exact = resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v5",
      resumeEntry: makeEntry({
        node_id: "chapter-1",
        navigation_version: "v5",
        path_label: "1",
        title: "Chapter 1"
      })
    })
    expect(exact).toEqual({
      nodeId: "chapter-1",
      outcome: "exact"
    })

    const staleVersion = resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v6",
      resumeEntry: makeEntry({
        node_id: "chapter-1",
        navigation_version: "v5",
        path_label: "1",
        title: "Chapter 1"
      })
    })
    expect(staleVersion?.outcome).toBe("path_label")
  })

  it("falls back in order: path label then title/depth then root", () => {
    const nodes = [
      makeNode({ id: "root-b", title: "Part B", order: 2 }),
      makeNode({ id: "root-a", title: "Part A", order: 1 }),
      makeNode({
        id: "sec-12-5",
        parent_id: "root-a",
        level: 1,
        title: "Overview",
        path_label: "12.5",
        order: 1
      }),
      makeNode({
        id: "overview-deep",
        parent_id: "root-b",
        level: 3,
        title: "Overview",
        path_label: null,
        order: 1
      })
    ]

    const pathLabel = resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v2",
      resumeEntry: makeEntry({
        node_id: "missing",
        navigation_version: "v1",
        path_label: "12.5",
        title: "No Match",
        level: 2
      })
    })
    expect(pathLabel).toEqual({
      nodeId: "sec-12-5",
      outcome: "path_label"
    })

    const titleDepth = resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v2",
      resumeEntry: makeEntry({
        node_id: "missing",
        navigation_version: "v1",
        path_label: "99.9",
        title: "overview",
        level: 3
      })
    })
    expect(titleDepth).toEqual({
      nodeId: "overview-deep",
      outcome: "title_depth"
    })

    const rootFallback = resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v2",
      resumeEntry: makeEntry({
        node_id: "missing",
        navigation_version: "v1",
        path_label: "99.9",
        title: "Unknown title",
        level: 5
      })
    })
    expect(rootFallback).toEqual({
      nodeId: "root-a",
      outcome: "root_fallback"
    })
  })
})
