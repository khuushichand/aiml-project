import { beforeEach, describe, expect, it, vi } from "vitest"

const storageState = vi.hoisted(() => ({
  values: new Map<string, unknown>()
}))

vi.mock("@/services/settings/registry", async () => {
  const actual = await vi.importActual<typeof import("@/services/settings/registry")>(
    "@/services/settings/registry"
  )

  return {
    ...actual,
    getSetting: vi.fn(async (setting: { key: string; defaultValue: unknown }) => {
      return storageState.values.has(setting.key)
        ? storageState.values.get(setting.key)
        : setting.defaultValue
    }),
    setSetting: vi.fn(async (setting: { key: string }, value: unknown) => {
      storageState.values.set(setting.key, value)
    })
  }
})

vi.mock("@/services/tts-providers", () => ({
  TTS_PROVIDER_VALUES: ["browser", "elevenlabs", "tldw"]
}))

import {
  DEFAULT_TLDW_TTS_MODEL,
  DEFAULT_TLDW_TTS_VOICE,
  DEFAULT_TTS_PROVIDER,
  getTTSSettings
} from "@/services/tts"

describe("tts defaults service", () => {
  beforeEach(() => {
    storageState.values.clear()
  })

  it("materializes the canonical fresh-profile Kitten baseline", async () => {
    const settings = await getTTSSettings()

    expect(settings.ttsProvider).toBe(DEFAULT_TTS_PROVIDER)
    expect(settings.tldwTtsModel).toBe(DEFAULT_TLDW_TTS_MODEL)
    expect(settings.tldwTtsVoice).toBe(DEFAULT_TLDW_TTS_VOICE)
  })

  it("preserves stored values when they are already present", async () => {
    storageState.values.set("ttsProvider", "browser")
    storageState.values.set("tldwTtsModel", "kokoro")
    storageState.values.set("tldwTtsVoice", "af_heart")

    const settings = await getTTSSettings()

    expect(settings.ttsProvider).toBe("browser")
    expect(settings.tldwTtsModel).toBe("kokoro")
    expect(settings.tldwTtsVoice).toBe("af_heart")
  })
})
