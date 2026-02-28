import { clampSpeechRate } from "./writing-speech-utils"

export type WritingSpeechPreferences = {
  rate: number
  voiceURI: string | null
}

const DEFAULT_SPEECH_PREFERENCES: WritingSpeechPreferences = {
  rate: 1,
  voiceURI: null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export const normalizeWritingSpeechPreferences = (
  value: unknown
): WritingSpeechPreferences => {
  if (!isRecord(value)) {
    return DEFAULT_SPEECH_PREFERENCES
  }

  const rate = clampSpeechRate(
    typeof value.rate === "number" ? value.rate : DEFAULT_SPEECH_PREFERENCES.rate
  )

  const rawVoiceURI =
    typeof value.voiceURI === "string"
      ? value.voiceURI.trim()
      : typeof value.voice_uri === "string"
        ? value.voice_uri.trim()
        : ""

  return {
    rate,
    voiceURI: rawVoiceURI.length > 0 ? rawVoiceURI : null
  }
}
