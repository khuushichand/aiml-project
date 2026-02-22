import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const STORAGE_KEY = "tldw:flashcards:shortcutHintTelemetry"

describe("flashcards-shortcut-hint-telemetry", () => {
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

  it("records exposure, density transitions, and dismissals", async () => {
    const telemetry = await import("@/utils/flashcards-shortcut-hint-telemetry")

    await telemetry.trackFlashcardsShortcutHintTelemetry({
      type: "flashcards_shortcut_hints_exposed",
      surface: "review",
      density: "expanded"
    })
    await telemetry.trackFlashcardsShortcutHintTelemetry({
      type: "flashcards_shortcut_hint_density_changed",
      surface: "review",
      from_density: "expanded",
      to_density: "compact"
    })
    await telemetry.trackFlashcardsShortcutHintTelemetry({
      type: "flashcards_shortcut_hints_exposed",
      surface: "review",
      density: "compact"
    })
    await telemetry.trackFlashcardsShortcutHintTelemetry({
      type: "flashcards_shortcut_hint_density_changed",
      surface: "review",
      from_density: "compact",
      to_density: "hidden"
    })
    await telemetry.trackFlashcardsShortcutHintTelemetry({
      type: "flashcards_shortcut_hints_dismissed",
      surface: "review",
      from_density: "compact"
    })

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.counters.flashcards_shortcut_hints_exposed).toBe(2)
    expect(state.counters.flashcards_shortcut_hint_density_changed).toBe(2)
    expect(state.counters.flashcards_shortcut_hints_dismissed).toBe(1)
    expect(state.exposures_by_surface_density["review:expanded"]).toBe(1)
    expect(state.exposures_by_surface_density["review:compact"]).toBe(1)
    expect(state.transitions_by_surface["review:expanded->compact"]).toBe(1)
    expect(state.transitions_by_surface["review:compact->hidden"]).toBe(1)
    expect(state.dismissals_by_surface.review).toBe(1)
    expect(state.last_density_by_surface.review).toBe("hidden")
    expect(state.recent_events).toHaveLength(5)
  })

  it("caps recent events to the configured maximum", async () => {
    const telemetry = await import("@/utils/flashcards-shortcut-hint-telemetry")

    for (let i = 0; i < 220; i += 1) {
      await telemetry.trackFlashcardsShortcutHintTelemetry({
        type: "flashcards_shortcut_hints_exposed",
        surface: i % 2 === 0 ? "cards" : "review",
        density: i % 3 === 0 ? "expanded" : "compact"
      })
    }

    const state = storageMap.get(STORAGE_KEY) as Record<string, any>
    expect(state.recent_events.length).toBe(200)
    expect(state.counters.flashcards_shortcut_hints_exposed).toBe(220)
  })
})

