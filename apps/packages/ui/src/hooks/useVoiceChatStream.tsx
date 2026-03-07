import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { useSttSettings } from "@/hooks/useSttSettings"
import { useVoiceChatSettings } from "@/hooks/useVoiceChatSettings"
import { useMicStream } from "@/hooks/useMicStream"
import { arrayBufferToBase64 } from "@/utils/compress"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { resolveApiProviderForModel } from "@/utils/resolve-api-provider"
import { useStreamingAudioPlayer } from "@/hooks/useStreamingAudioPlayer"

export type VoiceChatState =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "error"

type VoiceChatCallbacks = {
  onPartial?: (text: string) => void
  onTranscript?: (text: string, meta?: { autoCommit?: boolean }) => void
  onAssistantDelta?: (delta: string) => void
  onAssistantMessage?: (text: string) => void
  onError?: (message: string) => void
  onWarning?: (message: string) => void
  onStateChange?: (state: VoiceChatState) => void
}

type VoiceChatOptions = VoiceChatCallbacks & {
  active: boolean
}

const formatToMime = (format: string): string => {
  const normalized = String(format || "").trim().toLowerCase()
  switch (normalized) {
    case "wav":
      return "audio/wav"
    case "opus":
      return "audio/opus"
    case "aac":
      return "audio/aac"
    case "flac":
      return "audio/flac"
    case "ogg":
      return "audio/ogg"
    case "webm":
      return "audio/webm"
    case "ulaw":
      return "audio/basic"
    case "pcm":
      return "audio/L16"
    case "mp3":
    default:
      return "audio/mpeg"
  }
}

const isPlayableFormat = (format: string): boolean => {
  if (typeof Audio === "undefined") return false
  try {
    const probe = new Audio()
    return Boolean(probe.canPlayType(formatToMime(format)))
  } catch {
    return false
  }
}

const normalizeTriggerList = (phrases: string[]) =>
  phrases.map((phrase) => phrase.trim()).filter(Boolean)

const stripTriggerPhrases = (text: string, phrases: string[]): string => {
  if (!phrases.length) return text
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
  if (!phrases.length) return false
  const lower = text.toLowerCase()
  return phrases.some((phrase) => lower.includes(phrase.toLowerCase()))
}

export const useVoiceChatStream = ({
  active,
  onPartial,
  onTranscript,
  onAssistantDelta,
  onAssistantMessage,
  onError,
  onWarning,
  onStateChange
}: VoiceChatOptions) => {
  const sttSettings = useSttSettings()
  const {
    voiceChatModel,
    voiceChatPauseMs,
    voiceChatTriggerPhrases,
    voiceChatAutoResume,
    voiceChatBargeIn,
    voiceChatTtsMode
  } = useVoiceChatSettings()
  const [speechToTextLanguage] = useStorage("speechToTextLanguage", "en-US")
  const [selectedModel] = useStorage("selectedModel")

  const [ttsProvider] = useStorage("ttsProvider", "browser")
  const [tldwTtsModel] = useStorage("tldwTtsModel", "kokoro")
  const [tldwTtsVoice] = useStorage("tldwTtsVoice", "af_heart")
  const [tldwTtsResponseFormat] = useStorage("tldwTtsResponseFormat", "mp3")
  const [tldwTtsSpeed] = useStorage("tldwTtsSpeed", 1)
  const [openAITTSModel] = useStorage("openAITTSModel", "tts-1")
  const [openAITTSVoice] = useStorage("openAITTSVoice", "alloy")
  const [elevenLabsModel] = useStorage("elevenLabsModel", "")
  const [elevenLabsVoiceId] = useStorage("elevenLabsVoiceId", "")
  const [speechPlaybackSpeed] = useStorage("speechPlaybackSpeed", 1)

  const wsRef = React.useRef<WebSocket | null>(null)
  const connectingRef = React.useRef(false)
  const closingRef = React.useRef(false)
  const triggeredRef = React.useRef(false)
  const pendingResumeRef = React.useRef(false)
  const resolvedTtsFormatRef = React.useRef<string | null>(null)
  const errorRef = React.useRef<string | null>(null)

  const [state, setState] = React.useState<VoiceChatState>("idle")
  const [error, setError] = React.useState<string | null>(null)
  const [connected, setConnected] = React.useState(false)

  const callbacksRef = React.useRef({
    onPartial,
    onTranscript,
    onAssistantDelta,
    onAssistantMessage,
    onError,
    onWarning,
    onStateChange
  })
  const stateRef = React.useRef<VoiceChatState>(state)
  const activeRef = React.useRef(active)

  React.useEffect(() => {
    callbacksRef.current = {
      onPartial,
      onTranscript,
      onAssistantDelta,
      onAssistantMessage,
      onError,
      onWarning,
      onStateChange
    }
  }, [
    onPartial,
    onTranscript,
    onAssistantDelta,
    onAssistantMessage,
    onError,
    onWarning,
    onStateChange
  ])

  React.useEffect(() => {
    stateRef.current = state
  }, [state])

  React.useEffect(() => {
    activeRef.current = active
  }, [active])

  const updateState = React.useCallback((next: VoiceChatState) => {
    setState(next)
    callbacksRef.current.onStateChange?.(next)
  }, [])

  const {
    start: audioStart,
    append: audioAppend,
    finish: audioFinish,
    stop: audioStop,
    state: audioState
  } = useStreamingAudioPlayer()

  const { start: micStart, stop: micStop, active: micActive } = useMicStream(
    (chunk) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) return
      try {
        if (voiceChatBargeIn && stateRef.current === "speaking") {
          ws.send(JSON.stringify({ type: "interrupt", reason: "barge_in" }))
        }
        const base64 = arrayBufferToBase64(chunk)
        ws.send(JSON.stringify({ type: "audio", data: base64 }))
      } catch {
        // ignore chunk send failures
      }
    }
  )

  const normalizedTriggers = React.useMemo(
    () => normalizeTriggerList(voiceChatTriggerPhrases),
    [voiceChatTriggerPhrases]
  )

  const resolveTtsFormat = React.useCallback((): string => {
    const preferred = String(tldwTtsResponseFormat || "mp3").toLowerCase()
    if (!isPlayableFormat(preferred)) return "mp3"
    if (voiceChatTtsMode === "stream" && preferred === "pcm") return "mp3"
    return preferred
  }, [tldwTtsResponseFormat, voiceChatTtsMode])

  const buildTtsConfig = React.useCallback(() => {
    const provider = String(ttsProvider || "").toLowerCase()
    let model = ""
    let voice = ""
    let speed = 1
    let format = "mp3"

    if (!provider || provider === "browser") {
      model = tldwTtsModel
      voice = tldwTtsVoice
      speed = tldwTtsSpeed
      format = resolveTtsFormat()
    } else if (provider === "tldw") {
      model = tldwTtsModel
      voice = tldwTtsVoice
      speed = tldwTtsSpeed
      format = resolveTtsFormat()
    } else if (provider === "openai") {
      model = openAITTSModel
      voice = openAITTSVoice
      speed = speechPlaybackSpeed
      format = "mp3"
    } else if (provider === "elevenlabs") {
      model = elevenLabsModel
      voice = elevenLabsVoiceId
      speed = speechPlaybackSpeed
      format = "mp3"
    }

    const resolvedFormat = format || "mp3"
    resolvedTtsFormatRef.current = resolvedFormat

    return {
      provider: provider && provider !== "browser" ? provider : undefined,
      model,
      voice,
      speed,
      format: resolvedFormat
    }
  }, [
    ttsProvider,
    tldwTtsModel,
    tldwTtsVoice,
    tldwTtsSpeed,
    openAITTSModel,
    openAITTSVoice,
    elevenLabsModel,
    elevenLabsVoiceId,
    speechPlaybackSpeed,
    resolveTtsFormat
  ])

  const cleanupSession = React.useCallback(() => {
    try {
      micStop()
    } catch {}
    try {
      audioStop()
    } catch {}
    wsRef.current = null
    connectingRef.current = false
    triggeredRef.current = false
    pendingResumeRef.current = false
    resolvedTtsFormatRef.current = null
    setConnected(false)
  }, [audioStop, micStop])

  const stop = React.useCallback(() => {
    const ws = wsRef.current
    closingRef.current = Boolean(ws)
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "stop" }))
      } catch {}
    }
    try {
      ws?.close()
    } catch {}
    cleanupSession()
    if (!ws) {
      closingRef.current = false
    }
  }, [cleanupSession])

  const handleError = React.useCallback(
    (message: string) => {
      errorRef.current = message
      setError(message)
      callbacksRef.current.onError?.(message)
      updateState("error")
      stop()
    },
    [stop, updateState]
  )

  const sendCommit = React.useCallback(() => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    try {
      ws.send(JSON.stringify({ type: "commit" }))
    } catch {}
  }, [])

  const handleMessage = React.useCallback(
    (data: any) => {
      if (!data || typeof data !== "object") return
      const callbacks = callbacksRef.current
      const msgType = String(data.type || "").toLowerCase()

      if (msgType === "partial") {
        const text = String(data.text || "")
        callbacks.onPartial?.(text)
        if (!triggeredRef.current && detectTriggerPhrase(text, normalizedTriggers)) {
          triggeredRef.current = true
          sendCommit()
        }
        return
      }

      if (msgType === "full_transcript") {
        const raw = String(data.text || "")
        const cleaned = stripTriggerPhrases(raw, normalizedTriggers)
        triggeredRef.current = false
        if (!cleaned) {
          updateState("listening")
          return
        }
        callbacks.onTranscript?.(cleaned, { autoCommit: Boolean(data.auto_commit) })
        updateState("thinking")
        if (!voiceChatBargeIn) {
          try {
            micStop()
          } catch {}
        }
        return
      }

      if (msgType === "llm_delta") {
        const delta = String(data.delta || "")
        if (delta) {
          callbacks.onAssistantDelta?.(delta)
        }
        if (stateRef.current !== "speaking") {
          updateState("thinking")
        }
        return
      }

      if (msgType === "llm_message") {
        const text = String(data.text || "")
        callbacks.onAssistantMessage?.(text)
        return
      }

      if (msgType === "tts_start") {
        const format = String(data.format || resolvedTtsFormatRef.current || "mp3")
        audioStart(format, voiceChatTtsMode === "stream")
        updateState("speaking")
        if (!voiceChatBargeIn) {
          try {
            micStop()
          } catch {}
        }
        return
      }

      if (msgType === "tts_done") {
        audioFinish()
        pendingResumeRef.current = true
        return
      }

      if (msgType === "interrupted") {
        pendingResumeRef.current = false
        updateState(activeRef.current ? "listening" : "idle")
        return
      }

      if (msgType === "warning") {
        const message = String(data.message || "")
        if (message) callbacks.onWarning?.(message)
        return
      }

      if (msgType === "error") {
        const message = String(data.message || "Streaming error")
        handleError(message)
        return
      }
    },
    [
      audioFinish,
      audioStart,
      handleError,
      micStop,
      normalizedTriggers,
      sendCommit,
      updateState,
      voiceChatBargeIn,
      voiceChatTtsMode
    ]
  )

  const start = React.useCallback(async () => {
    if (connectingRef.current || wsRef.current) return
    connectingRef.current = true
    errorRef.current = null
    setError(null)
    updateState("connecting")

    try {
      const config = await tldwClient.getConfig()
      const serverUrl = String(config?.serverUrl || "").trim()
      if (!serverUrl) {
        throw new Error("tldw server not configured")
      }
      const token =
        config?.authMode === "multi-user"
          ? String(config?.accessToken || "").trim()
          : String(config?.apiKey || "").trim()
      if (!token) {
        throw new Error("Not authenticated. Configure tldw credentials in Settings.")
      }

      const base = serverUrl.replace(/^http/i, "ws").replace(/\/$/, "")
      const url = `${base}/api/v1/audio/chat/stream?token=${encodeURIComponent(token)}`
      const ws = new WebSocket(url)
      ws.binaryType = "arraybuffer"
      wsRef.current = ws

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          try {
            const payload = JSON.parse(event.data)
            handleMessage(payload)
          } catch {}
        } else if (event.data instanceof ArrayBuffer) {
          audioAppend(event.data)
        }
      }

      ws.onerror = () => {
        handleError("Voice chat websocket error")
      }

      ws.onclose = () => {
        const wasClosing = closingRef.current
        closingRef.current = false
        cleanupSession()
        if (!wasClosing && activeRef.current && !errorRef.current) {
          const message = "Voice chat disconnected"
          errorRef.current = message
          setError(message)
          callbacksRef.current.onError?.(message)
          updateState("error")
          return
        }
        updateState("idle")
      }

      ws.onopen = () => {
        void (async () => {
          try {
            const model = String(voiceChatModel || selectedModel || "").trim()
            const llmProvider = await resolveApiProviderForModel({
              modelId: model
            })
            const ttsConfig = buildTtsConfig()

            const sttConfig: Record<string, any> = {
              enable_vad: true,
              min_silence_ms: voiceChatPauseMs,
              language: speechToTextLanguage
            }
            const modelValue = String(sttSettings.model || "").trim()
            if (modelValue) {
              sttConfig.model = modelValue
            }
            if (sttSettings.timestampGranularities) {
              sttConfig.timestamp_granularities =
                sttSettings.timestampGranularities
            }
            if (sttSettings.prompt && sttSettings.prompt.trim().length > 0) {
              sttConfig.prompt = sttSettings.prompt.trim()
            }
            if (sttSettings.task) {
              sttConfig.task = sttSettings.task
            }
            if (sttSettings.responseFormat) {
              sttConfig.response_format = sttSettings.responseFormat
            }
            if (typeof sttSettings.temperature === "number") {
              sttConfig.temperature = sttSettings.temperature
            }
            if (sttSettings.useSegmentation) {
              sttConfig.segment = true
              if (typeof sttSettings.segK === "number") {
                sttConfig.seg_K = sttSettings.segK
              }
              if (typeof sttSettings.segMinSegmentSize === "number") {
                sttConfig.seg_min_segment_size = sttSettings.segMinSegmentSize
              }
              if (typeof sttSettings.segLambdaBalance === "number") {
                sttConfig.seg_lambda_balance = sttSettings.segLambdaBalance
              }
              if (typeof sttSettings.segUtteranceExpansionWidth === "number") {
                sttConfig.seg_utterance_expansion_width =
                  sttSettings.segUtteranceExpansionWidth
              }
              if (sttSettings.segEmbeddingsProvider?.trim()) {
                sttConfig.seg_embeddings_provider =
                  sttSettings.segEmbeddingsProvider.trim()
              }
              if (sttSettings.segEmbeddingsModel?.trim()) {
                sttConfig.seg_embeddings_model =
                  sttSettings.segEmbeddingsModel.trim()
              }
            }

            ws.send(
              JSON.stringify({
                type: "config",
                stt: sttConfig,
                llm: {
                  model,
                  provider: llmProvider
                },
                tts: ttsConfig
              })
            )

            await micStart()
            setConnected(true)
            connectingRef.current = false
            updateState("listening")
          } catch (err: any) {
            handleError(err?.message || "Voice chat failed to start")
          }
        })()
      }
    } catch (err: any) {
      handleError(err?.message || "Unable to connect to voice chat")
    }
  }, [
    audioAppend,
    buildTtsConfig,
    cleanupSession,
    handleError,
    handleMessage,
    micStart,
    resolveApiProviderForModel,
    selectedModel,
    speechToTextLanguage,
    sttSettings.model,
    sttSettings.temperature,
    sttSettings.task,
    sttSettings.responseFormat,
    sttSettings.timestampGranularities,
    sttSettings.prompt,
    sttSettings.useSegmentation,
    sttSettings.segK,
    sttSettings.segMinSegmentSize,
    sttSettings.segLambdaBalance,
    sttSettings.segUtteranceExpansionWidth,
    sttSettings.segEmbeddingsProvider,
    sttSettings.segEmbeddingsModel,
    updateState,
    voiceChatModel,
    voiceChatPauseMs
  ])

  React.useEffect(() => {
    if (active) {
      void start()
      return
    }
    stop()
    errorRef.current = null
    setError(null)
    updateState("idle")
  }, [active, start, stop, updateState])

  React.useEffect(() => {
    if (!pendingResumeRef.current) return
    if (audioState.playing) return
    pendingResumeRef.current = false
    if (!active) {
      updateState("idle")
      return
    }
    if (voiceChatAutoResume) {
      if (!voiceChatBargeIn) {
        void micStart().then(() => updateState("listening")).catch(() => {
          handleError("Unable to restart microphone")
        })
      } else {
        updateState("listening")
      }
    } else {
      updateState("idle")
    }
  }, [
    active,
    audioState.playing,
    handleError,
    micStart,
    updateState,
    voiceChatAutoResume,
    voiceChatBargeIn
  ])

  React.useEffect(() => {
    return () => {
      stop()
    }
  }, [stop])

  return {
    state,
    error,
    connected,
    micActive,
    start,
    stop,
    sendCommit
  }
}
