import { describe, expect, it } from "vitest"
import { normalizeWritingSpeechPreferences } from "../writing-speech-settings-utils"

describe("writing speech settings utils", () => {
  it("returns defaults for invalid values", () => {
    expect(normalizeWritingSpeechPreferences(undefined)).toEqual({
      rate: 1,
      voiceURI: null
    })

    expect(normalizeWritingSpeechPreferences({ rate: "bad", voiceURI: 1 })).toEqual({
      rate: 1,
      voiceURI: null
    })
  })

  it("clamps rate and keeps valid voice URI", () => {
    expect(
      normalizeWritingSpeechPreferences({ rate: 3.5, voiceURI: "com.voice" })
    ).toEqual({
      rate: 2,
      voiceURI: "com.voice"
    })

    expect(
      normalizeWritingSpeechPreferences({ rate: 0.2, voiceURI: "com.voice" })
    ).toEqual({
      rate: 0.5,
      voiceURI: "com.voice"
    })
  })

  it("normalizes empty voice strings to null", () => {
    expect(normalizeWritingSpeechPreferences({ rate: 1.1, voiceURI: "   " })).toEqual({
      rate: 1.1,
      voiceURI: null
    })
  })
})
