import { describe, expect, it } from "vitest"

import {
  getProviderLabel,
  inferProviderFromModel
} from "@/utils/provider-registry"

describe("provider-registry TTS inference", () => {
  it("infers KittenTTS from local aliases and repo ids", () => {
    expect(inferProviderFromModel("kitten_tts", "tts")).toBe("kitten_tts")
    expect(inferProviderFromModel("KittenTTS", "tts")).toBe("kitten_tts")
    expect(inferProviderFromModel("KittenML/kitten-tts-micro-0.8", "tts")).toBe(
      "kitten_tts"
    )
  })

  it("returns the KittenTTS label for tts-engine displays", () => {
    expect(getProviderLabel("kitten_tts", "tts-engine")).toBe("KittenTTS")
  })
})
