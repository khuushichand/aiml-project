import { describe, expect, it } from "vitest"
import {
  buildSpeechVoiceOptions,
  clampSpeechRate,
  resolvePauseResumeAction,
  resolveSpeechVoice
} from "../writing-speech-utils"

const makeVoice = (
  voiceURI: string,
  name: string,
  lang = "en-US"
): SpeechSynthesisVoice =>
  ({
    voiceURI,
    name,
    lang,
    default: false,
    localService: true
  }) as SpeechSynthesisVoice

describe("writing speech utils", () => {
  it("clamps speech rate to supported bounds", () => {
    expect(clampSpeechRate(0.1)).toBe(0.5)
    expect(clampSpeechRate(3.2)).toBe(2)
    expect(clampSpeechRate(1.25)).toBe(1.25)
    expect(clampSpeechRate(undefined)).toBe(1)
  })

  it("resolves selected voice by voiceURI", () => {
    const voices = [makeVoice("v1", "Voice One"), makeVoice("v2", "Voice Two")]

    expect(resolveSpeechVoice(voices, "v2")?.name).toBe("Voice Two")
    expect(resolveSpeechVoice(voices, "missing")).toBeNull()
    expect(resolveSpeechVoice([], "v1")).toBeNull()
  })

  it("builds stable voice options", () => {
    const options = buildSpeechVoiceOptions([
      makeVoice("en-voice", "Alex", "en-US"),
      makeVoice("fr-voice", "Thomas", "fr-FR")
    ])

    expect(options).toEqual([
      { value: "en-voice", label: "Alex (en-US)" },
      { value: "fr-voice", label: "Thomas (fr-FR)" }
    ])
  })

  it("resolves pause/resume action state", () => {
    expect(resolvePauseResumeAction(false, false)).toBeNull()
    expect(resolvePauseResumeAction(false, true)).toBeNull()
    expect(resolvePauseResumeAction(true, false)).toBe("pause")
    expect(resolvePauseResumeAction(true, true)).toBe("resume")
  })
})
