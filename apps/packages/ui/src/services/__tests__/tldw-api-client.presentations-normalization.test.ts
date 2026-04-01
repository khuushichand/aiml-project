import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  bgUpload: vi.fn(),
  bgStream: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args),
  bgUpload: (...args: unknown[]) => mocks.bgUpload(...args),
  bgStream: (...args: unknown[]) => mocks.bgStream(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: vi.fn(async () => null),
    set: vi.fn(async () => undefined),
    remove: vi.fn(async () => undefined)
  }),
  safeStorageSerde: {
    serialize: (value: unknown) => value,
    deserialize: (value: unknown) => value
  }
}))

import {
  presentationsMethods,
  type TldwApiClientCore
} from "@/services/tldw/domains/presentations"

describe("TldwApiClient presentations normalization", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("trims and filters array-based visual style metadata fields", async () => {
    const client: TldwApiClientCore = {
      ensureConfigForRequest: vi.fn(async () => ({})),
      request: vi.fn(async () => ({
        styles: [
          {
            id: "notebooklm-blueprint",
            name: "Blueprint",
            scope: "builtin",
            tags: [" technical ", " ", "technical_grid"],
            best_for: [" systems explanation ", "", "architecture walkthrough "],
            artifact_preferences: [" timeline ", "comparison_matrix", ""],
            appearance_defaults: { theme: "night" },
            generation_rules: {},
            fallback_policy: {}
          }
        ],
        total_count: 1
      })),
      resolveApiPath: vi.fn(),
      fillPathParams: vi.fn()
    }

    const styles = await presentationsMethods.listVisualStyles.call(client)

    expect(styles).toHaveLength(1)
    expect(styles[0]?.tags).toEqual(["technical", "technical_grid"])
    expect(styles[0]?.best_for).toEqual(["systems explanation", "architecture walkthrough"])
    expect(styles[0]?.artifact_preferences).toEqual(["timeline", "comparison_matrix"])
  })
})
