import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const TELEMETRY_STORAGE_KEY = "tldw:media:navigation:telemetry"

describe("media-navigation-telemetry", () => {
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

  it("records counters and last-event snapshots for required navigation events", async () => {
    const telemetry = await import("@/utils/media-navigation-telemetry")

    await telemetry.trackMediaNavigationTelemetry({
      type: "media_navigation_payload_truncated",
      scope_key_hash: "scope1",
      media_id: 7,
      requested_max_nodes: 500,
      returned_node_count: 500,
      node_count: 900
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_navigation_resume_state_restored",
      scope_key_hash: "scope1",
      media_id: 7,
      outcome: "path_label"
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_navigation_section_selected",
      media_id: 7,
      node_id: "sec-12-5",
      depth: 2,
      latency_ms: 118,
      source: "restore"
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_navigation_fallback_used",
      scope_key_hash: "scope1",
      media_id: 7,
      fallback_kind: "generated",
      source: "generated"
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_navigation_rollout_control_changed",
      scope_key_hash: "scope1",
      media_id: 7,
      control: "include_generated_fallback",
      enabled: true
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_rich_sanitization_applied",
      removed_node_count: 2,
      removed_attribute_count: 4,
      blocked_url_count: 1
    })
    await telemetry.trackMediaNavigationTelemetry({
      type: "media_rich_sanitization_blocked_url",
      scheme: "javascript"
    })

    const state = storageMap.get(TELEMETRY_STORAGE_KEY) as Record<string, any>
    expect(state.counters.media_navigation_payload_truncated).toBe(1)
    expect(state.counters.media_navigation_resume_state_restored).toBe(1)
    expect(state.counters.media_navigation_section_selected).toBe(1)
    expect(state.counters.media_navigation_fallback_used).toBe(1)
    expect(state.counters.media_navigation_rollout_control_changed).toBe(1)
    expect(state.counters.media_rich_sanitization_applied).toBe(1)
    expect(state.counters.media_rich_sanitization_blocked_url).toBe(1)
    expect(state.last_resume_outcome).toBe("path_label")
    expect(state.last_selection.node_id).toBe("sec-12-5")
    expect(state.last_fallback.fallback_kind).toBe("generated")
    expect(state.last_rollout_control.control).toBe("include_generated_fallback")
    expect(state.last_rollout_control.enabled).toBe(true)
    expect(state.blocked_url_schemes.javascript).toBe(1)
  })

  it("caps recent telemetry events and aggregates blocked-url schemes", async () => {
    const telemetry = await import("@/utils/media-navigation-telemetry")

    for (let i = 0; i < 220; i += 1) {
      await telemetry.trackMediaNavigationTelemetry({
        type: "media_rich_sanitization_blocked_url",
        scheme: i % 2 === 0 ? "javascript" : "data"
      })
    }

    const state = storageMap.get(TELEMETRY_STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.blocked_url_schemes.javascript).toBe(110)
    expect(state.blocked_url_schemes.data).toBe(110)
  })

  it("derives stable hash for scope key", async () => {
    const telemetry = await import("@/utils/media-navigation-telemetry")
    const a = telemetry.hashMediaNavigationScopeKey(
      "server:abc:user:one"
    )
    const b = telemetry.hashMediaNavigationScopeKey(
      "server:abc:user:one"
    )
    const c = telemetry.hashMediaNavigationScopeKey(
      "server:abc:user:two"
    )

    expect(a).toBe(b)
    expect(a).not.toBe(c)
  })
})
