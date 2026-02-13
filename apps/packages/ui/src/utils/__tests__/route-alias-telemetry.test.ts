import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:route:alias:telemetry"

describe("route-alias-telemetry", () => {
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

  it("normalizes source and destination paths in telemetry events", async () => {
    const telemetry = await import("@/utils/route-alias-telemetry")
    const event = telemetry.buildRouteAliasTelemetryEvent({
      sourcePath: "https://localhost/search?q=rag#examples",
      destinationPath: "/knowledge?q=rag#examples",
      preserveParams: true
    })

    expect(event.source_path).toBe("/search")
    expect(event.destination_path).toBe("/knowledge")
    expect(event.source_has_query).toBe(true)
    expect(event.source_has_hash).toBe(true)
    expect(event.destination_has_query).toBe(true)
    expect(event.destination_has_hash).toBe(true)
    expect(event.query_or_hash_carried).toBe(true)
  })

  it("records alias counters and destination counters", async () => {
    const telemetry = await import("@/utils/route-alias-telemetry")

    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/search?q=rag",
      destinationPath: "/knowledge?q=rag",
      preserveParams: true
    })
    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/search?q=ml",
      destinationPath: "/knowledge?q=ml",
      preserveParams: true
    })
    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/claims-review",
      destinationPath: "/content-review",
      preserveParams: false
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.route_alias_redirect).toBe(3)
    expect(state.alias_hits["/search"]).toBe(2)
    expect(state.alias_hits["/claims-review"]).toBe(1)
    expect(state.destination_hits["/knowledge"]).toBe(2)
    expect(state.destination_hits["/content-review"]).toBe(1)
    expect(state.last_redirect.source_path).toBe("/claims-review")
    expect(state.last_redirect.destination_path).toBe("/content-review")
    expect(state.last_redirect.preserve_params).toBe(false)
    expect(state.recent_events).toHaveLength(3)
  })

  it("caps recent events to the configured max", async () => {
    const telemetry = await import("@/utils/route-alias-telemetry")

    for (let i = 0; i < 220; i += 1) {
      await telemetry.trackRouteAliasRedirect({
        sourcePath: `/legacy-${i}`,
        destinationPath: "/knowledge",
        preserveParams: false
      })
    }

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.counters.route_alias_redirect).toBe(220)
    expect(state.alias_hits["/legacy-0"]).toBe(1)
    expect(state.alias_hits["/legacy-219"]).toBe(1)
    expect(state.destination_hits["/knowledge"]).toBe(220)
  })

  it("builds weekly rollup rows for top aliases and destinations", async () => {
    const telemetry = await import("@/utils/route-alias-telemetry")

    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/search?q=rag",
      destinationPath: "/knowledge?q=rag",
      preserveParams: true
    })
    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/search?q=ml",
      destinationPath: "/knowledge?q=ml",
      preserveParams: true
    })
    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/profile",
      destinationPath: "/settings",
      preserveParams: false
    })
    await telemetry.trackRouteAliasRedirect({
      sourcePath: "/claims-review",
      destinationPath: "/content-review",
      preserveParams: false
    })

    const rollup = await telemetry.getRouteAliasTelemetryRollup({ topN: 2 })
    expect(rollup.total_redirects).toBe(4)
    expect(rollup.top_alias_sources).toEqual([
      { path: "/search", hits: 2, share: 0.5 },
      { path: "/claims-review", hits: 1, share: 0.25 }
    ])
    expect(rollup.top_destinations).toEqual([
      { path: "/knowledge", hits: 2, share: 0.5 },
      { path: "/content-review", hits: 1, share: 0.25 }
    ])
  })
})
