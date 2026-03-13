import React from "react"

import { useMicStream } from "@/hooks/useMicStream"
import type { ResolvedPersonaVoiceDefaults } from "@/hooks/useResolvedPersonaVoiceDefaults"
import { useStreamingAudioPlayer } from "@/hooks/useStreamingAudioPlayer"
import { arrayBufferToBase64 } from "@/utils/compress"

export type PersonaLiveVoiceState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "error"

type UsePersonaLiveVoiceControllerArgs = {
  ws: WebSocket | null
  connected: boolean
  sessionId: string
  personaId: string
  resolvedDefaults: ResolvedPersonaVoiceDefaults
  canUseServerStt: boolean
}

type PersonaLiveVoicePayload = Record<string, unknown> | null | undefined

const normalizeTriggerList = (phrases: string[]) =>
  phrases.map((phrase) => phrase.trim()).filter(Boolean)

const stripTriggerPhrases = (text: string, phrases: string[]): string => {
  if (!phrases.length) return text.trim()
  let next = text
  for (const phrase of phrases) {
    if (!phrase) continue
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    const pattern = new RegExp(`\\b${escaped}\\b`, "ig")
    next = next.replace(pattern, " ")
  }
  return next.replace(/\s+/g, " ").trim()
}

const detectTriggerPhrase = (text: string, phrases: string[]): boolean => {
  if (!phrases.length) return true
  const lower = text.toLowerCase()
  return phrases.some((phrase) => lower.includes(phrase.toLowerCase()))
}

const normalizeTtsProvider = (provider: string): string =>
  String(provider || "").trim().toLowerCase()

const browserSpeechSupported = (): boolean =>
  typeof window !== "undefined" && "speechSynthesis" in window

export const usePersonaLiveVoiceController = ({
  ws,
  connected,
  sessionId,
  personaId,
  resolvedDefaults,
  canUseServerStt
}: UsePersonaLiveVoiceControllerArgs) => {
  const [state, setState] = React.useState<PersonaLiveVoiceState>("idle")
  const [heardText, setHeardText] = React.useState("")
  const [lastCommittedText, setLastCommittedText] = React.useState("")
  const [warning, setWarning] = React.useState<string | null>(null)
  const [textOnlyDueToTtsFailure, setTextOnlyDueToTtsFailure] = React.useState(false)
  const [sessionAutoResume, setSessionAutoResume] = React.useState(resolvedDefaults.autoResume)
  const [sessionBargeIn, setSessionBargeIn] = React.useState(resolvedDefaults.bargeIn)

  const heardTranscriptRef = React.useRef("")
  const textOnlyDueToTtsFailureRef = React.useRef(false)
  const pendingBinaryFinishRef = React.useRef(false)
  const pendingResumeRef = React.useRef(false)
  const awaitingTtsTimeoutRef = React.useRef<number | null>(null)
  const browserUtteranceActiveRef = React.useRef(false)
  const resumeListeningRef = React.useRef<() => void>(() => {})

  const normalizedTriggers = React.useMemo(
    () => normalizeTriggerList(resolvedDefaults.voiceChatTriggerPhrases),
    [resolvedDefaults.voiceChatTriggerPhrases]
  )
  const activeProvider = React.useMemo(
    () => normalizeTtsProvider(resolvedDefaults.ttsProvider),
    [resolvedDefaults.ttsProvider]
  )

  const clearTransientWarning = React.useCallback(() => {
    if (textOnlyDueToTtsFailureRef.current) return
    setWarning(null)
  }, [])

  const clearAwaitingTtsTimeout = React.useCallback(() => {
    if (awaitingTtsTimeoutRef.current != null && typeof window !== "undefined") {
      window.clearTimeout(awaitingTtsTimeoutRef.current)
    }
    awaitingTtsTimeoutRef.current = null
  }, [])

  const {
    start: audioStart,
    append: audioAppend,
    finish: audioFinish,
    stop: audioStop,
    state: audioState
  } = useStreamingAudioPlayer()

  const finishVoiceTurn = React.useCallback(() => {
    pendingResumeRef.current = false
    if (sessionAutoResume && canUseServerStt && connected) {
      resumeListeningRef.current()
      return
    }
    setState("idle")
  }, [canUseServerStt, connected, sessionAutoResume])

  const stopBrowserSpeech = React.useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel()
      } catch {}
    }
    browserUtteranceActiveRef.current = false
  }, [])

  const stopCurrentPlayback = React.useCallback(() => {
    clearAwaitingTtsTimeout()
    pendingResumeRef.current = false
    pendingBinaryFinishRef.current = false
    audioStop()
    stopBrowserSpeech()
  }, [audioStop, clearAwaitingTtsTimeout, stopBrowserSpeech])

  const handleVoiceError = React.useCallback((error: unknown) => {
    const message =
      error instanceof Error
        ? error.message
        : "Live voice capture failed. Check microphone permissions and audio setup."
    setWarning(message)
    setState("error")
  }, [])

  const sendVoiceCommit = React.useCallback(
    (transcript: string) => {
      if (!connected || !sessionId || !ws || ws.readyState !== WebSocket.OPEN) {
        setWarning("Live voice is disconnected. Reconnect Persona Garden to send spoken commands.")
        setState("error")
        return
      }

      const normalizedTranscript = String(transcript || "").trim()
      if (normalizedTranscript && !detectTriggerPhrase(normalizedTranscript, normalizedTriggers)) {
        setWarning("No trigger phrase was heard, so nothing was sent.")
        setState("idle")
        return
      }

      const cleanedTranscript = normalizedTranscript
        ? stripTriggerPhrases(normalizedTranscript, normalizedTriggers)
        : ""
      if (normalizedTranscript && !cleanedTranscript) {
        setWarning("The trigger phrase was removed, but no spoken command remained.")
        setState("idle")
        return
      }

      try {
        ws.send(
          JSON.stringify({
            type: "voice_commit",
            session_id: sessionId,
            ...(cleanedTranscript ? { transcript: cleanedTranscript } : {}),
            source: "persona_live_voice"
          })
        )
        clearTransientWarning()
        setLastCommittedText(cleanedTranscript)
        setState("thinking")
      } catch (error) {
        handleVoiceError(error)
      }
    },
    [
      connected,
      handleVoiceError,
      normalizedTriggers,
      sessionId,
      ws
    ]
  )

  const { start: startMicStream, stop: stopMicStream, active: micActive } = useMicStream(
    (chunk) => {
      if (!connected || !sessionId || !ws || ws.readyState !== WebSocket.OPEN) return
      try {
        ws.send(
          JSON.stringify({
            type: "audio_chunk",
            session_id: sessionId,
            audio_format: "pcm16",
            bytes_base64: arrayBufferToBase64(chunk)
          })
        )
      } catch {
        // Ignore transient websocket send errors while the session reconnects.
      }
    }
  )

  React.useEffect(() => {
    textOnlyDueToTtsFailureRef.current = textOnlyDueToTtsFailure
  }, [textOnlyDueToTtsFailure])

  React.useEffect(() => {
    resumeListeningRef.current = () => {
      if (!sessionAutoResume || !canUseServerStt || !connected || micActive) {
        setState("idle")
        return
      }
      clearTransientWarning()
      setHeardText("")
      heardTranscriptRef.current = ""
      void startMicStream()
        .then(() => {
          setState("listening")
        })
        .catch((error) => {
          handleVoiceError(error)
        })
    }
  }, [
    canUseServerStt,
    connected,
    clearTransientWarning,
    handleVoiceError,
    micActive,
    sessionAutoResume,
    startMicStream
  ])

  const startListening = React.useCallback(async () => {
    if (!canUseServerStt) {
      setWarning("This tldw connection does not expose server speech transcription.")
      setState("error")
      return
    }
    if (!connected || !sessionId || !ws || ws.readyState !== WebSocket.OPEN) {
      setWarning("Connect Persona Garden before starting live voice.")
      setState("error")
      return
    }
    if (state === "speaking") {
      if (!sessionBargeIn) {
        setWarning("Barge-in is off for this live session.")
        return
      }
      stopCurrentPlayback()
    }
    clearTransientWarning()
    setHeardText("")
    heardTranscriptRef.current = ""
    setState("listening")
    try {
      await startMicStream()
    } catch (error) {
      handleVoiceError(error)
    }
  }, [
    canUseServerStt,
    clearTransientWarning,
    connected,
    handleVoiceError,
    sessionBargeIn,
    sessionId,
    startMicStream,
    state,
    stopCurrentPlayback,
    ws
  ])

  const stopListening = React.useCallback(() => {
    if (!micActive) return
    stopMicStream()
    sendVoiceCommit(heardTranscriptRef.current)
  }, [micActive, sendVoiceCommit, stopMicStream])

  const toggleListening = React.useCallback(() => {
    if (micActive) {
      stopListening()
      return
    }
    void startListening()
  }, [micActive, startListening, stopListening])

  const playBrowserSpeech = React.useCallback(
    (text: string) => {
      const spokenText = String(text || "").trim()
      if (!spokenText) {
        finishVoiceTurn()
        return
      }
      if (!browserSpeechSupported()) {
        textOnlyDueToTtsFailureRef.current = true
        setTextOnlyDueToTtsFailure(true)
        setWarning("Browser speech playback is unavailable. Continuing in text-only mode.")
        finishVoiceTurn()
        return
      }

      stopBrowserSpeech()
      const synthesis = window.speechSynthesis
      const utterance = new SpeechSynthesisUtterance(spokenText)
      if (resolvedDefaults.sttLanguage) {
        utterance.lang = resolvedDefaults.sttLanguage
      }
      const availableVoices = synthesis.getVoices()
      const matchedVoice = availableVoices.find(
        (voice) =>
          voice.voiceURI === resolvedDefaults.ttsVoice ||
          voice.name === resolvedDefaults.ttsVoice
      )
      if (matchedVoice) {
        utterance.voice = matchedVoice
      }
      browserUtteranceActiveRef.current = true
      utterance.onend = () => {
        browserUtteranceActiveRef.current = false
        finishVoiceTurn()
      }
      utterance.onerror = () => {
        browserUtteranceActiveRef.current = false
        textOnlyDueToTtsFailureRef.current = true
        setTextOnlyDueToTtsFailure(true)
        setWarning("Browser speech playback failed. Continuing in text-only mode.")
        finishVoiceTurn()
      }
      setState("speaking")
      synthesis.speak(utterance)
    },
    [
      finishVoiceTurn,
      resolvedDefaults.sttLanguage,
      resolvedDefaults.ttsVoice,
      stopBrowserSpeech
    ]
  )

  React.useEffect(() => {
    setSessionAutoResume(resolvedDefaults.autoResume)
    setSessionBargeIn(resolvedDefaults.bargeIn)
    textOnlyDueToTtsFailureRef.current = false
    setTextOnlyDueToTtsFailure(false)
    setWarning(null)
    setHeardText("")
    heardTranscriptRef.current = ""
    setLastCommittedText("")
    setState("idle")
    clearAwaitingTtsTimeout()
    pendingBinaryFinishRef.current = false
    pendingResumeRef.current = false
    stopMicStream()
    stopCurrentPlayback()
  }, [
    clearAwaitingTtsTimeout,
    personaId,
    resolvedDefaults.autoResume,
    resolvedDefaults.bargeIn,
    sessionId,
    stopMicStream,
    stopCurrentPlayback
  ])

  React.useEffect(() => {
    if (!connected) {
      setState("idle")
      pendingBinaryFinishRef.current = false
      pendingResumeRef.current = false
      clearAwaitingTtsTimeout()
      stopMicStream()
      stopCurrentPlayback()
    }
  }, [clearAwaitingTtsTimeout, connected, stopMicStream, stopCurrentPlayback])

  React.useEffect(() => {
    if (!connected || !sessionId || !ws || ws.readyState !== WebSocket.OPEN) return
    try {
      ws.send(
        JSON.stringify({
          type: "voice_config",
          session_id: sessionId,
          voice: {
            trigger_phrases: resolvedDefaults.voiceChatTriggerPhrases,
            auto_resume: sessionAutoResume,
            barge_in: sessionBargeIn
          },
          stt: {
            language: resolvedDefaults.sttLanguage,
            model: resolvedDefaults.sttModel
          },
          tts: {
            provider: resolvedDefaults.ttsProvider,
            voice: resolvedDefaults.ttsVoice
          }
        })
      )
    } catch {
      // Ignore transient websocket send errors; the next runtime change will retry.
    }
  }, [
    connected,
    resolvedDefaults.sttLanguage,
    resolvedDefaults.sttModel,
    resolvedDefaults.ttsProvider,
    resolvedDefaults.ttsVoice,
    resolvedDefaults.voiceChatTriggerPhrases,
    sessionAutoResume,
    sessionBargeIn,
    sessionId,
    ws
  ])

  React.useEffect(() => {
    if (!pendingResumeRef.current) return
    if (audioState.playing) return
    pendingResumeRef.current = false
    finishVoiceTurn()
  }, [audioState.playing, finishVoiceTurn])

  React.useEffect(() => {
    return () => {
      clearAwaitingTtsTimeout()
      stopMicStream()
      stopCurrentPlayback()
    }
  }, [clearAwaitingTtsTimeout, stopMicStream, stopCurrentPlayback])

  const handlePayload = React.useCallback(
    (payload: PersonaLiveVoicePayload) => {
      const eventType = String(payload?.event || payload?.type || "").trim().toLowerCase()
      if (!eventType) return

      if (eventType === "assistant_delta") {
        const text = String(payload?.text_delta || "").trim()
        if (!text) return
        clearAwaitingTtsTimeout()
        if (textOnlyDueToTtsFailure) {
          finishVoiceTurn()
          return
        }
        if (activeProvider === "browser") {
          playBrowserSpeech(text)
          return
        }
        if (typeof window !== "undefined") {
          awaitingTtsTimeoutRef.current = window.setTimeout(() => {
            finishVoiceTurn()
          }, 1200)
        }
        setState("thinking")
        return
      }

      if (eventType === "partial_transcript") {
        const delta = String(payload?.text_delta || "").trim()
        if (!delta) return
        setHeardText((current) => {
          const next = current ? `${current} ${delta}` : delta
          heardTranscriptRef.current = next
          return next
        })
        return
      }

      if (eventType === "tts_audio") {
        clearAwaitingTtsTimeout()
        const chunkIndex =
          typeof payload?.chunk_index === "number"
            ? payload.chunk_index
            : Number.parseInt(String(payload?.chunk_index ?? "0"), 10)
        const chunkCount =
          typeof payload?.chunk_count === "number"
            ? payload.chunk_count
            : Number.parseInt(String(payload?.chunk_count ?? "1"), 10)
        const audioFormat = String(payload?.audio_format || "mp3")
        if (chunkIndex <= 0) {
          audioStart(audioFormat, true)
          setState("speaking")
        }
        pendingBinaryFinishRef.current = chunkIndex >= chunkCount - 1
        return
      }

      if (eventType === "notice") {
        const reasonCode = String(payload?.reason_code || "").trim().toUpperCase()
        if (reasonCode === "TTS_UNAVAILABLE_TEXT_ONLY") {
          clearAwaitingTtsTimeout()
          textOnlyDueToTtsFailureRef.current = true
          setTextOnlyDueToTtsFailure(true)
          setWarning(
            String(payload?.message || "Live TTS is unavailable. Continuing in text-only mode.")
          )
          finishVoiceTurn()
          return
        }
        if (reasonCode === "TRANSCRIPT_REQUIRED") {
          setWarning("No speech transcript was captured for that live turn.")
          setState("idle")
        }
      }
    },
    [
      activeProvider,
      audioStart,
      clearAwaitingTtsTimeout,
      finishVoiceTurn,
      playBrowserSpeech,
      textOnlyDueToTtsFailure
    ]
  )

  const handleBinaryPayload = React.useCallback(
    (data: ArrayBuffer) => {
      if (!(data instanceof ArrayBuffer)) return
      audioAppend(data)
      if (pendingBinaryFinishRef.current) {
        pendingBinaryFinishRef.current = false
        pendingResumeRef.current = true
        audioFinish()
      }
    },
    [audioAppend, audioFinish]
  )

  return {
    state,
    heardText,
    lastCommittedText,
    warning,
    speechAvailable: canUseServerStt,
    isListening: micActive,
    sessionAutoResume,
    sessionBargeIn,
    textOnlyDueToTtsFailure,
    startListening,
    stopListening,
    toggleListening,
    setSessionAutoResume,
    setSessionBargeIn,
    handlePayload,
    handleBinaryPayload
  }
}
