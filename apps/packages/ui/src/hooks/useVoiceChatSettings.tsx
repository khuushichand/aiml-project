import React from "react"
import { useSetting } from "@/hooks/useSetting"
import {
  VOICE_CHAT_AUTO_RESUME_SETTING,
  VOICE_CHAT_BARGE_IN_SETTING,
  VOICE_CHAT_ENABLED_SETTING,
  VOICE_CHAT_MODEL_SETTING,
  VOICE_CHAT_PAUSE_MS_SETTING,
  VOICE_CHAT_TRIGGER_PHRASES_SETTING,
  VOICE_CHAT_TTS_MODE_SETTING,
  type VoiceChatTtsMode
} from "@/services/settings/ui-settings"

export const useVoiceChatSettings = () => {
  const [voiceChatEnabled, setVoiceChatEnabled] = useSetting(
    VOICE_CHAT_ENABLED_SETTING
  )
  const [voiceChatModel, setVoiceChatModel] = useSetting(
    VOICE_CHAT_MODEL_SETTING
  )
  const [voiceChatPauseMs, setVoiceChatPauseMs] = useSetting(
    VOICE_CHAT_PAUSE_MS_SETTING
  )
  const [voiceChatTriggerPhrases, setVoiceChatTriggerPhrases] = useSetting(
    VOICE_CHAT_TRIGGER_PHRASES_SETTING
  )
  const [voiceChatAutoResume, setVoiceChatAutoResume] = useSetting(
    VOICE_CHAT_AUTO_RESUME_SETTING
  )
  const [voiceChatBargeIn, setVoiceChatBargeIn] = useSetting(
    VOICE_CHAT_BARGE_IN_SETTING
  )
  const [voiceChatTtsMode, setVoiceChatTtsMode] = useSetting(
    VOICE_CHAT_TTS_MODE_SETTING
  )

  const normalizedTriggerPhrases = React.useMemo(
    () =>
      (voiceChatTriggerPhrases || [])
        .map((phrase) => phrase.trim())
        .filter(Boolean),
    [voiceChatTriggerPhrases]
  )

  const wrappedSetVoiceChatTriggerPhrases = React.useCallback(
    (value: string[] | ((prev: string[]) => string[])) => {
      if (typeof value === "function") {
        setVoiceChatTriggerPhrases((prev) => value(prev || []))
        return
      }
      setVoiceChatTriggerPhrases(value)
    },
    [setVoiceChatTriggerPhrases]
  )

  return React.useMemo(
    () => ({
      voiceChatEnabled,
      setVoiceChatEnabled,
      voiceChatModel,
      setVoiceChatModel,
      voiceChatPauseMs,
      setVoiceChatPauseMs,
      voiceChatTriggerPhrases: normalizedTriggerPhrases,
      setVoiceChatTriggerPhrases: wrappedSetVoiceChatTriggerPhrases,
      voiceChatAutoResume,
      setVoiceChatAutoResume,
      voiceChatBargeIn,
      setVoiceChatBargeIn,
      voiceChatTtsMode: voiceChatTtsMode as VoiceChatTtsMode,
      setVoiceChatTtsMode
    }),
    [
      voiceChatEnabled,
      setVoiceChatEnabled,
      voiceChatModel,
      setVoiceChatModel,
      voiceChatPauseMs,
      setVoiceChatPauseMs,
      normalizedTriggerPhrases,
      wrappedSetVoiceChatTriggerPhrases,
      voiceChatAutoResume,
      setVoiceChatAutoResume,
      voiceChatBargeIn,
      setVoiceChatBargeIn,
      voiceChatTtsMode,
      setVoiceChatTtsMode
    ]
  )
}
