import { describe, expect, it } from "vitest"

import { normalizeBuiltExtensionSeedConfig } from "./extension-build"

describe("normalizeBuiltExtensionSeedConfig", () => {
  it("wraps a plain connection config under tldwConfig for built extension storage", () => {
    const seedConfig = {
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "test-key"
    }

    const normalized = normalizeBuiltExtensionSeedConfig(seedConfig)

    expect(normalized.connectionConfig).toEqual(seedConfig)
    expect(normalized.storagePayload).toMatchObject({
      __tldw_first_run_complete: true,
      tldw_skip_landing_hub: true,
      quickIngestInspectorIntroDismissed: true,
      quickIngestOnboardingDismissed: true,
      tldwConfig: seedConfig,
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "test-key"
    })
  })

  it("preserves a full seeded storage payload without nesting it again", () => {
    const seedConfig = {
      __tldw_first_run_complete: true,
      tldw_skip_landing_hub: true,
      quickIngestInspectorIntroDismissed: true,
      quickIngestOnboardingDismissed: true,
      "tldw:workflow:landing-config": {
        showOnFirstRun: true,
        dismissedAt: 123,
        completedWorkflows: []
      },
      tldwConfig: {
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user",
        apiKey: "test-key"
      }
    }

    const normalized = normalizeBuiltExtensionSeedConfig(seedConfig)

    expect(normalized.connectionConfig).toEqual(seedConfig.tldwConfig)
    expect(normalized.storagePayload).toMatchObject({
      tldwConfig: {
        serverUrl: "http://127.0.0.1:8000",
        authMode: "single-user",
        apiKey: "test-key"
      }
    })
    expect(normalized.storagePayload.tldwConfig).not.toHaveProperty("tldwConfig")
  })
})
