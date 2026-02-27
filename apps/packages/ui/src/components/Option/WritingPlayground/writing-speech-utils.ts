export const clampSpeechRate = (
  value: number | null | undefined,
  fallback = 1
): number => {
  const candidate = typeof value === "number" && Number.isFinite(value) ? value : fallback
  return Math.min(2, Math.max(0.5, candidate))
}

export const resolveSpeechVoice = (
  voices: SpeechSynthesisVoice[],
  voiceURI: string | null | undefined
): SpeechSynthesisVoice | null => {
  if (!voiceURI) return null
  return voices.find((voice) => voice.voiceURI === voiceURI) ?? null
}

export const buildSpeechVoiceOptions = (
  voices: SpeechSynthesisVoice[]
): Array<{ value: string; label: string }> =>
  voices.map((voice) => ({
    value: voice.voiceURI,
    label: `${voice.name} (${voice.lang})`
  }))

export const resolvePauseResumeAction = (
  isSpeaking: boolean,
  isPaused: boolean
): "pause" | "resume" | null => {
  if (!isSpeaking) return null
  return isPaused ? "resume" : "pause"
}
