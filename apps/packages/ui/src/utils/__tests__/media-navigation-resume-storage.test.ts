import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { MediaNavigationNode } from "@/hooks/useMediaNavigation"

const makeNode = (overrides: Partial<MediaNavigationNode>): MediaNavigationNode => ({
  id: overrides.id || "node",
  parent_id: overrides.parent_id ?? null,
  level: overrides.level ?? 0,
  title: overrides.title || "Untitled",
  order: overrides.order ?? 0,
  path_label: overrides.path_label ?? null,
  target_type: overrides.target_type || "char_range",
  target_start: overrides.target_start ?? 0,
  target_end: overrides.target_end ?? 1,
  target_href: overrides.target_href ?? null,
  source: overrides.source || "test",
  confidence: overrides.confidence ?? null
})

describe("media-navigation-resume storage integration", () => {
  let storageMap: Map<string, unknown>

  beforeEach(() => {
    storageMap = new Map<string, unknown>()
    vi.resetModules()
    vi.doMock("@/utils/safe-storage", () => ({
      createSafeStorage: () => ({
        get: async (key: string) => storageMap.get(key),
        set: async (key: string, value: unknown) => {
          storageMap.set(key, value)
        },
        remove: async (key: string) => {
          storageMap.delete(key)
        }
      })
    }))
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  it("keeps resume selection isolated per scope key", async () => {
    const resume = await import("@/utils/media-navigation-resume")

    await resume.saveMediaNavigationResumeSelection({
      scopeKey: "scope-a",
      mediaId: "42",
      node: {
        id: "scope-a-node",
        path_label: "12.5",
        title: "Section A",
        level: 2
      },
      navigationVersion: "v1"
    })

    await resume.saveMediaNavigationResumeSelection({
      scopeKey: "scope-b",
      mediaId: "42",
      node: {
        id: "scope-b-node",
        path_label: "7.1",
        title: "Section B",
        level: 1
      },
      navigationVersion: "v1"
    })

    const scopeAEntry = await resume.getMediaNavigationResumeEntry({
      scopeKey: "scope-a",
      mediaId: "42"
    })
    const scopeBEntry = await resume.getMediaNavigationResumeEntry({
      scopeKey: "scope-b",
      mediaId: "42"
    })

    expect(scopeAEntry?.node_id).toBe("scope-a-node")
    expect(scopeBEntry?.node_id).toBe("scope-b-node")
  })

  it("restores by path label when node id is stale across navigation versions", async () => {
    const resume = await import("@/utils/media-navigation-resume")

    await resume.saveMediaNavigationResumeSelection({
      scopeKey: "scope-resume",
      mediaId: 11,
      node: {
        id: "old-node-id",
        path_label: "12.5",
        title: "Error analysis",
        level: 2
      },
      navigationVersion: "v1"
    })

    const storedEntry = await resume.getMediaNavigationResumeEntry({
      scopeKey: "scope-resume",
      mediaId: 11
    })

    const nodes = [
      makeNode({ id: "root", title: "Chapter 12", path_label: "12", order: 1 }),
      makeNode({
        id: "new-node-id",
        parent_id: "root",
        level: 2,
        title: "Error analysis",
        path_label: "12.5",
        order: 2
      })
    ]

    const restored = resume.resolveMediaNavigationResumeSelection({
      nodes,
      navigationVersion: "v2",
      resumeEntry: storedEntry
    })

    expect(restored).toEqual({
      nodeId: "new-node-id",
      outcome: "path_label"
    })
  })

  it("applies bounded LRU eviction in persisted scope store", async () => {
    const resume = await import("@/utils/media-navigation-resume")
    const scopeKey = "scope-lru"
    let sawEviction = false

    for (let i = 0; i < 1002; i += 1) {
      const eviction = await resume.saveMediaNavigationResumeSelection({
        scopeKey,
        mediaId: `media-${i}`,
        node: {
          id: `node-${i}`,
          path_label: `${i}`,
          title: `Section ${i}`,
          level: i % 4
        },
        navigationVersion: "v1"
      })
      if (eviction.evicted_lru_count > 0) {
        sawEviction = true
      }
    }

    const store = await resume.readMediaNavigationResumeStore(scopeKey)
    expect(sawEviction).toBe(true)
    expect(store.entries.length).toBe(1000)
    expect(store.entries.some((entry) => entry.media_id === "media-1001")).toBe(
      true
    )
  })
})
