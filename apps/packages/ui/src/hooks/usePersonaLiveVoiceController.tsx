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

export type PersonaLiveVoiceRecoveryMode = "none" | "listening_stuck" | "thinking_stuck"

type UsePersonaLiveVoiceControllerArgs = {
  ws: WebSocket | null
  connected: boolean
  sessionId: string
  personaId: string
  resolvedDefaults: ResolvedPersonaVoiceDefaults
  canUseServerStt: boolean
}

type PersonaLiveVoicePayload = Record<string, unknown> | null | undefined

const LISTENING_RECOVERY_TIMEOUT_MS = 4_000

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
  const [manualModeRequired, setManualModeRequired] = React.useState(false)
  const [textOnlyDueToTtsFailure, setTextOnlyDueToTtsFailure] = React.useState(false)
  const [sessionAutoResume, setSessionAutoResume] = React.useState(resolvedDefaults.autoResume)
  const [sessionBargeIn, setSessionBargeIn] = React.useState(resolvedDefaults.bargeIn)
  const [recoveryMode, setRecoveryMode] =
    React.useState<PersonaLiveVoiceRecoveryMode>("none")
  const [listeningRecoveryRestartKey, setListeningRecoveryRestartKey] = React.useState(0)

  const heardTranscriptRef = React.useRef("")
  const manualModeRequiredRef = React.useRef(false)
  const textOnlyDueToTtsFailureRef = React.useRef(false)
  const pendingBinaryFinishRef = React.useRef(false)
  const pendingResumeRef = React.useRef(false)
  const awaitingTtsTimeoutRef = React.useRef<number | null>(null)
  const browserUtteranceActiveRef = React.useRef(false)
  const resumeListeningRef = React.useRef<() => void>(() => {})
  const listeningRecoveryTimeoutRef = React.useRef<number | null>(null)

  const activeProvider = React.useMemo(
    () => normalizeTtsProvider(resolvedDefaults.ttsProvider),
    [resolvedDefaults.ttsProvider]
  )

  const clearTransientWarning = React.useCallback(() => {
    if (textOnlyDueToTtsFailureRef.current) return
    if (manualModeRequiredRef.current) return
    setWarning(null)
  }, [])

  const clearAwaitingTtsTimeout = React.useCallback(() => {
    if (awaitingTtsTimeoutRef.current != null && typeof window !== "undefined") {
      window.clearTimeout(awaitingTtsTimeoutRef.current)
    }
    awaitingTtsTimeoutRef.current = null
  }, [])

  const clearListeningRecoveryTimeout = React.useCallback(() => {
    if (listeningRecoveryTimeoutRef.current != null && typeof window !== "undefined") {
      window.clearTimeout(listeningRecoveryTimeoutRef.current)
    }
    listeningRecoveryTimeoutRef.current = null
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
    (transcript: string, source = "persona_live_voice_manual") => {
      if (!connected || !sessionId || !ws || ws.readyState !== WebSocket.OPEN) {
        setWarning("Live voice is disconnected. Reconnect Persona Garden to send spoken commands.")
        setState("error")
        return
      }

      const normalizedTranscript = String(transcript || "").trim()
      if (!normalizedTranscript) {
        setWarning("No speech transcript was captured for that live turn.")
        setState("idle")
        return
      }

      try {
        ws.send(
          JSON.stringify({
            type: "voice_commit",
            session_id: sessionId,
            transcript: normalizedTranscript,
            source
          })
        )
        clearTransientWarning()
        setState("thinking")
      } catch (error) {
        handleVoiceError(error)
      }
    },
    [clearTransientWarning, connected, handleVoiceError, sessionId, ws]
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

  const resetTurn = React.useCallback(() => {
    clearListeningRecoveryTimeout()
    if (micActive) {
      stopMicStream()
    }
    setRecoveryMode("none")
    setHeardText("")
    heardTranscriptRef.current = ""
    setLastCommittedText("")
    if (!manualModeRequiredRef.current && !textOnlyDueToTtsFailureRef.current) {
      setWarning(null)
    }
    setState("idle")
  }, [clearListeningRecoveryTimeout, micActive, stopMicStream])

  const keepListening = React.useCallback(() => {
    clearListeningRecoveryTimeout()
    setRecoveryMode("none")
    setListeningRecoveryRestartKey((current) => current + 1)
  }, [clearListeningRecoveryTimeout])

  React.useEffect(() => {
    manualModeRequiredRef.current = manualModeRequired
  }, [manualModeRequired])

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
      setRecoveryMode("none")
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
    setRecoveryMode("none")
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
    clearListeningRecoveryTimeout()
    setRecoveryMode("none")
    stopMicStream()
    setState("idle")
  }, [clearListeningRecoveryTimeout, micActive, stopMicStream])

  const sendCurrentTranscriptNow = React.useCallback(() => {
    if (micActive) {
      stopMicStream()
    }
    sendVoiceCommit(heardTranscriptRef.current, "persona_live_voice_manual")
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
    manualModeRequiredRef.current = false
    setManualModeRequired(false)
    textOnlyDueToTtsFailureRef.current = false
    setTextOnlyDueToTtsFailure(false)
    setWarning(null)
    setHeardText("")
    heardTranscriptRef.current = ""
    setLastCommittedText("")
    setRecoveryMode("none")
    setListeningRecoveryRestartKey(0)
    setState("idle")
    clearAwaitingTtsTimeout()
    clearListeningRecoveryTimeout()
    pendingBinaryFinishRef.current = false
    pendingResumeRef.current = false
    stopMicStream()
    stopCurrentPlayback()
  }, [
    clearAwaitingTtsTimeout,
    clearListeningRecoveryTimeout,
    personaId,
    resolvedDefaults.autoResume,
    resolvedDefaults.bargeIn,
    sessionId,
    stopMicStream,
    stopCurrentPlayback
  ])

  React.useEffect(() => {
    if (!connected) {
      manualModeRequiredRef.current = false
      setManualModeRequired(false)
      setRecoveryMode("none")
      setListeningRecoveryRestartKey(0)
      setState("idle")
      pendingBinaryFinishRef.current = false
      pendingResumeRef.current = false
      clearAwaitingTtsTimeout()
      clearListeningRecoveryTimeout()
      stopMicStream()
      stopCurrentPlayback()
    }
  }, [clearAwaitingTtsTimeout, clearListeningRecoveryTimeout, connected, stopMicStream, stopCurrentPlayback])

  React.useEffect(() => {
    const normalizedHeardText = String(heardText || "").trim()
    if (state !== "listening" || !normalizedHeardText) {
      clearListeningRecoveryTimeout()
      setRecoveryMode((current) => (current === "listening_stuck" ? "none" : current))
      return
    }
    setRecoveryMode((current) => (current === "listening_stuck" ? "none" : current))
    clearListeningRecoveryTimeout()
    if (typeof window === "undefined") return
    listeningRecoveryTimeoutRef.current = window.setTimeout(() => {
      setRecoveryMode("listening_stuck")
    }, LISTENING_RECOVERY_TIMEOUT_MS)
    return () => {
      clearListeningRecoveryTimeout()
    }
  }, [clearListeningRecoveryTimeout, heardText, listeningRecoveryRestartKey, state])

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
            model: resolvedDefaults.sttModel,
            enable_vad: true
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
      clearListeningRecoveryTimeout()
      stopMicStream()
      stopCurrentPlayback()
    }
  }, [clearAwaitingTtsTimeout, clearListeningRecoveryTimeout, stopMicStream, stopCurrentPlayback])

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
        if (reasonCode === "VOICE_MANUAL_MODE_REQUIRED") {
          manualModeRequiredRef.current = true
          setManualModeRequired(true)
          setWarning(
            String(
              payload?.message ||
                "Server VAD unavailable for this live session. Use Send now to commit heard speech manually."
            )
          )
          return
        }
        if (reasonCode === "VOICE_TURN_COMMITTED") {
          clearAwaitingTtsTimeout()
          clearListeningRecoveryTimeout()
          if (micActive) {
            stopMicStream()
          }
          const committedTranscript = String(payload?.transcript || "").trim()
          if (committedTranscript) {
            setLastCommittedText(committedTranscript)
          }
          if (!manualModeRequiredRef.current && !textOnlyDueToTtsFailureRef.current) {
            setWarning(null)
          }
          setRecoveryMode("none")
          setState("thinking")
          return
        }
        if (reasonCode === "VOICE_COMMIT_IGNORED_ALREADY_COMMITTED") {
          setWarning(String(payload?.message || "This utterance was already committed."))
          setState("thinking")
          return
        }
        if (reasonCode === "VOICE_TRIGGER_NOT_HEARD") {
          setHeardText("")
          heardTranscriptRef.current = ""
          setWarning(
            String(payload?.message || "No trigger phrase was heard, so the transcript was ignored.")
          )
          setState(micActive ? "listening" : "idle")
          return
        }
        if (reasonCode === "VOICE_EMPTY_COMMAND_AFTER_TRIGGER") {
          setHeardText("")
          heardTranscriptRef.current = ""
          setWarning(
            String(
              payload?.message ||
                "The trigger phrase was removed, but no spoken command remained."
            )
          )
          setState(micActive ? "listening" : "idle")
          return
        }
        if (reasonCode === "TRANSCRIPT_REQUIRED") {
          setWarning("No speech transcript was captured for that live turn.")
          setState(micActive ? "listening" : "idle")
        }
      }
    },
    [
      activeProvider,
      audioStart,
      clearAwaitingTtsTimeout,
      clearListeningRecoveryTimeout,
      finishVoiceTurn,
      micActive,
      playBrowserSpeech,
      stopMicStream,
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
    recoveryMode,
    heardText,
    lastCommittedText,
    warning,
    manualModeRequired,
    canSendNow: Boolean(String(heardText || heardTranscriptRef.current || "").trim()),
    speechAvailable: canUseServerStt,
    isListening: micActive,
    sessionAutoResume,
    sessionBargeIn,
    textOnlyDueToTtsFailure,
    startListening,
    stopListening,
    toggleListening,
    sendCurrentTranscriptNow,
    keepListening,
    resetTurn,
    setSessionAutoResume,
    setSessionBargeIn,
    handlePayload,
    handleBinaryPayload
  }
}
