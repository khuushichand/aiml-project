import React from "react"
import { resolveAudioCapturePlan } from "@/audio"
import { useAudioSourceCatalog } from "@/hooks/useAudioSourceCatalog"
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition"
import type {
  AudioCaptureRequestedSource,
  DictationErrorClass,
  DictationModePreference,
  DictationResolvedMode,
  DictationServerErrorTransition
} from "@/hooks/useDictationStrategy"
import { useDictationStrategy } from "@/hooks/useDictationStrategy"
import { useServerDictation } from "@/hooks/useServerDictation"
import type { SttSettings } from "@/hooks/useSttSettings"
import { useAudioSourcePreferences } from "@/hooks/useAudioSourcePreferences"
import { emitDictationDiagnostics } from "@/utils/dictation-diagnostics"
import { withTemplateFallback } from "@/utils/template-guards"

// ---------------------------------------------------------------------------
// Deps interface
// ---------------------------------------------------------------------------

export interface UsePlaygroundVoiceChatDeps {
  /** Whether voice chat is available (server supports audio) */
  voiceChatAvailable: boolean
  /** Voice chat enabled toggle */
  voiceChatEnabled: boolean
  setVoiceChatEnabled: (enabled: boolean) => void
  /** Voice chat stream hook instance */
  voiceChat: {
    state: string
    [key: string]: any
  }
  voiceChatMessages: {
    abandonTurn: () => void
    [key: string]: any
  }
  /** Server capabilities */
  canUseServerStt: boolean
  /** STT settings from storage */
  sttModel: string
  sttTemperature: number
  sttTask: string
  sttResponseFormat: string
  sttTimestampGranularities: string
  sttPrompt: string
  sttUseSegmentation: boolean
  sttSegK: number
  sttSegMinSegmentSize: number
  sttSegLambdaBalance: number
  sttSegUtteranceExpansionWidth: number
  sttSegEmbeddingsProvider: string
  sttSegEmbeddingsModel: string
  /** Dictation preferences from storage */
  dictationModeOverride: DictationModePreference | null
  dictationAutoFallbackEnabled: boolean
  autoStopTimeout: number
  autoSubmitVoiceMessage: boolean
  /** Language */
  speechToTextLanguage: string
  /** Callbacks */
  setMessageValue: (value: string, options?: any) => void
  submitForm: () => void
  /** Notification API */
  notificationApi: { error: (opts: any) => void; warning: (opts: any) => void }
  isSending: boolean
  isListening: boolean
  isServerDictating: boolean
  /** i18n */
  t: (key: string, ...args: any[]) => string
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function usePlaygroundVoiceChat(deps: UsePlaygroundVoiceChatDeps) {
  const {
    voiceChatAvailable,
    voiceChatEnabled,
    setVoiceChatEnabled,
    voiceChat,
    voiceChatMessages,
    canUseServerStt,
    sttModel,
    sttTemperature,
    sttTask,
    sttResponseFormat,
    sttTimestampGranularities,
    sttPrompt,
    sttUseSegmentation,
    sttSegK,
    sttSegMinSegmentSize,
    sttSegLambdaBalance,
    sttSegUtteranceExpansionWidth,
    sttSegEmbeddingsProvider,
    sttSegEmbeddingsModel,
    dictationModeOverride,
    dictationAutoFallbackEnabled,
    autoStopTimeout,
    autoSubmitVoiceMessage,
    speechToTextLanguage,
    setMessageValue,
    submitForm,
    notificationApi,
    isSending,
    t
  } = deps
  const {
    preference: dictationAudioSourcePreference,
    isLoading: dictationSourceLoading,
    setPreference: setDictationAudioSourcePreference
  } = useAudioSourcePreferences("dictation")
  const {
    devices: audioInputDevices,
    isSettled: hasAudioCatalogSettled
  } = useAudioSourceCatalog()

  const {
    transcript,
    isListening,
    resetTranscript,
    start: startListening,
    stop: stopSpeechRecognition,
    supported: browserSupportsSpeechRecognition
  } = useSpeechRecognition({
    autoStop: autoSubmitVoiceMessage,
    autoStopTimeout,
    onEnd: async () => {
      if (autoSubmitVoiceMessage) {
        submitForm()
      }
    }
  })
  const [pendingDictationStart, setPendingDictationStart] = React.useState(false)

  const dictationCapturePlan = React.useMemo(
    () =>
      resolveAudioCapturePlan({
        featureGroup: "dictation",
        requestedSource: dictationAudioSourcePreference,
        requestedSpeechPath:
          dictationModeOverride === "browser"
            ? "browser_dictation"
            : "server_dictation",
        capabilities: {
          browserDictationSupported: browserSupportsSpeechRecognition,
          serverDictationSupported: canUseServerStt,
          liveVoiceSupported: false,
          secureContextAvailable:
            typeof window === "undefined" ? true : window.isSecureContext
        }
      }),
    [
      browserSupportsSpeechRecognition,
      canUseServerStt,
      dictationAudioSourcePreference,
      dictationModeOverride
    ]
  )
  const dictationSourceReady = hasAudioCatalogSettled && !dictationSourceLoading
  const resolvedDictationSourcePreference = React.useMemo(() => {
    if (!dictationSourceReady) {
      return dictationAudioSourcePreference
    }

    if (dictationAudioSourcePreference.sourceKind !== "mic_device") {
      return dictationAudioSourcePreference
    }

    const requestedDeviceId = String(dictationAudioSourcePreference.deviceId || "").trim()
    const deviceStillAvailable = audioInputDevices.some(
      (device) => device.deviceId === requestedDeviceId
    )

    if (deviceStillAvailable) {
      return dictationAudioSourcePreference
    }

    return {
      featureGroup: "dictation" as const,
      sourceKind: "default_mic" as const,
      deviceId: null,
      lastKnownLabel: null
    }
  }, [audioInputDevices, dictationAudioSourcePreference, dictationSourceReady])
  const resolvedDictationSourceKind = resolvedDictationSourcePreference.sourceKind
  const browserDictationCompatible =
    resolvedDictationSourcePreference.sourceKind === "default_mic"
  const resolvedModeOverride =
    dictationModeOverride === "browser" && !browserDictationCompatible
      ? (canUseServerStt ? ("server" as const) : ("unavailable" as const))
      : null
  const requestedServerDictationSource = React.useMemo<
    AudioCaptureRequestedSource | undefined
  >(
    () =>
      resolvedDictationSourcePreference.sourceKind === "mic_device"
        ? resolvedDictationSourcePreference
        : undefined,
    [resolvedDictationSourcePreference]
  )

  const dictationDiagnosticsSnapshotRef = React.useRef<{
    requestedMode: DictationModePreference
    resolvedMode: DictationResolvedMode
    requestedSourceKind: "default_mic" | "mic_device" | "tab_audio" | "system_audio"
    resolvedSourceKind: "default_mic" | "mic_device" | "tab_audio" | "system_audio"
    speechAvailable: boolean
    speechUsesServer: boolean
    fallbackReason: DictationErrorClass | null
  }>({
    requestedMode: "auto",
    resolvedMode: "unavailable",
    requestedSourceKind: "default_mic",
    resolvedSourceKind: "default_mic",
    speechAvailable: false,
    speechUsesServer: false,
    fallbackReason: null
  })

  const serverDictationErrorBridgeRef = React.useRef<
    (error: unknown) => DictationServerErrorTransition
  >(
    () => ({
      errorClass: "unknown_error",
      appliedFallback: false,
      requestedMode: "auto",
      resolvedModeBeforeError: "unavailable",
      speechAvailableBeforeError: false,
      speechUsesServerBeforeError: false,
      browserSupportsSpeechRecognition: false,
      autoFallbackEnabled: false
    })
  )
  const serverDictationSuccessBridgeRef = React.useRef<() => void>(() => {})

  const handleServerDictationError = React.useCallback((error: unknown) => {
    const transition = serverDictationErrorBridgeRef.current(error)
    const snapshot = dictationDiagnosticsSnapshotRef.current
    emitDictationDiagnostics({
      surface: "playground",
      kind: "server_error",
      requestedMode: transition.requestedMode,
      resolvedMode: transition.resolvedModeBeforeError,
      requestedSourceKind: snapshot.requestedSourceKind,
      resolvedSourceKind: snapshot.resolvedSourceKind,
      speechAvailable: transition.speechAvailableBeforeError,
      speechUsesServer: transition.speechUsesServerBeforeError,
      errorClass: transition.errorClass,
      fallbackApplied: transition.appliedFallback,
      fallbackReason: transition.appliedFallback ? transition.errorClass : null
    })
  }, [])

  const handleServerDictationSuccess = React.useCallback(() => {
    serverDictationSuccessBridgeRef.current()
    const snapshot = dictationDiagnosticsSnapshotRef.current
    emitDictationDiagnostics({
      surface: "playground",
      kind: "server_success",
      requestedMode: snapshot.requestedMode,
      resolvedMode: snapshot.resolvedMode,
      requestedSourceKind: snapshot.requestedSourceKind,
      resolvedSourceKind: snapshot.resolvedSourceKind,
      speechAvailable: snapshot.speechAvailable,
      speechUsesServer: snapshot.speechUsesServer,
      fallbackReason: snapshot.fallbackReason
    })
  }, [])

  const sttSettings = React.useMemo<SttSettings>(
    () => ({
      model: sttModel,
      temperature: sttTemperature,
      task: sttTask,
      responseFormat: sttResponseFormat,
      timestampGranularities: sttTimestampGranularities,
      prompt: sttPrompt,
      useSegmentation: sttUseSegmentation,
      segK: sttSegK,
      segMinSegmentSize: sttSegMinSegmentSize,
      segLambdaBalance: sttSegLambdaBalance,
      segUtteranceExpansionWidth: sttSegUtteranceExpansionWidth,
      segEmbeddingsProvider: sttSegEmbeddingsProvider,
      segEmbeddingsModel: sttSegEmbeddingsModel
    }),
    [
      sttModel,
      sttPrompt,
      sttResponseFormat,
      sttSegEmbeddingsModel,
      sttSegEmbeddingsProvider,
      sttSegK,
      sttSegLambdaBalance,
      sttSegMinSegmentSize,
      sttSegUtteranceExpansionWidth,
      sttTask,
      sttTemperature,
      sttTimestampGranularities,
      sttUseSegmentation
    ]
  )

  const {
    isServerDictating,
    startServerDictation,
    stopServerDictation
  } = useServerDictation({
    canUseServerStt,
    speechToTextLanguage,
    sttSettings,
    onTranscript: (text) => {
      setMessageValue(text, { collapseLarge: true, forceCollapse: true })
    },
    onError: handleServerDictationError,
    onSuccess: handleServerDictationSuccess
  })

  const dictationStrategy = useDictationStrategy({
    canUseServerStt,
    browserSupportsSpeechRecognition,
    browserDictationCompatible,
    resolvedModeOverride,
    isServerDictating,
    isBrowserDictating: isListening,
    modeOverride: dictationModeOverride,
    autoFallbackEnabled: Boolean(dictationAutoFallbackEnabled)
  })

  const speechAvailable = dictationStrategy.speechAvailable
  const speechUsesServer = dictationStrategy.speechUsesServer
  const dictationToggleIntent = dictationStrategy.toggleIntent

  // Keep snapshot ref up to date
  dictationDiagnosticsSnapshotRef.current = {
    requestedMode: dictationStrategy.requestedMode,
    resolvedMode: dictationStrategy.resolvedMode,
    requestedSourceKind: dictationCapturePlan.requestedSourceKind,
    resolvedSourceKind: resolvedDictationSourceKind,
    speechAvailable: dictationStrategy.speechAvailable,
    speechUsesServer: dictationStrategy.speechUsesServer,
    fallbackReason: dictationStrategy.autoFallbackErrorClass
  }
  serverDictationErrorBridgeRef.current = dictationStrategy.recordServerError
  serverDictationSuccessBridgeRef.current = dictationStrategy.recordServerSuccess

  // --- Tooltip ---
  const speechTooltipText = React.useMemo(() => {
    if (!speechAvailable) {
      return t(
        "playground:actions.speechUnavailableBody",
        "Connect to a tldw server that exposes the audio transcriptions API to use dictation."
      ) as string
    }
    if (dictationStrategy.autoFallbackActive) {
      return t(
        "playground:tooltip.speechToTextBrowser",
        "Dictation via browser speech recognition"
      ) as string
    }
    if (speechUsesServer) {
      const sttModelLabel = sttModel || "whisper-1"
      const sttTaskLabel = sttTask === "translate" ? "translate" : "transcribe"
      const sttFormatLabel = (sttResponseFormat || "json").toUpperCase()
      const speechDetails = withTemplateFallback(
        t(
          "playground:tooltip.speechToTextDetails",
          "Uses {{model}} · {{task}} · {{format}}. Configure in Settings → General → Speech-to-Text.",
          {
            model: sttModelLabel,
            task: sttTaskLabel,
            format: sttFormatLabel
          } as any
        ),
        `Uses ${sttModelLabel} · ${sttTaskLabel} · ${sttFormatLabel}. Configure in Settings -> General -> Speech-to-Text.`
      )
      return (
        (t(
          "playground:tooltip.speechToTextServer",
          "Dictation via your tldw server"
        ) as string) +
        " " +
        speechDetails
      )
    }
    return t(
      "playground:tooltip.speechToTextBrowser",
      "Dictation via browser speech recognition"
    ) as string
  }, [
    dictationStrategy.autoFallbackActive,
    speechAvailable,
    speechUsesServer,
    sttModel,
    sttTask,
    sttResponseFormat,
    t
  ])

  // --- Browser dictation start ---
  const startBrowserDictation = React.useCallback(() => {
    resetTranscript()
    startListening({
      continuous: true,
      lang: speechToTextLanguage
    })
  }, [resetTranscript, speechToTextLanguage, startListening])
  const runPendingDictationStart = React.useCallback(() => {
    switch (dictationToggleIntent) {
      case "start_server":
        void startServerDictation(requestedServerDictationSource)
        return true
      case "start_browser":
        startBrowserDictation()
        return true
      default:
        return false
    }
  }, [
    dictationToggleIntent,
    requestedServerDictationSource,
    startBrowserDictation,
    startServerDictation
  ])

  // --- Voice chat status label ---
  const voiceChatStatusLabel = React.useMemo(() => {
    switch (voiceChat.state) {
      case "connecting":
        return t("playground:voiceChat.statusConnecting", "Connecting")
      case "listening":
        return t("playground:voiceChat.statusListening", "Listening")
      case "thinking":
        return t("playground:voiceChat.statusThinking", "Thinking")
      case "speaking":
        return t("playground:voiceChat.statusSpeaking", "Speaking")
      case "error":
        return t("playground:voiceChat.statusError", "Error")
      default:
        return t("playground:voiceChat.statusIdle", "Voice chat")
    }
  }, [t, voiceChat.state])

  // Update window title when voice chat is active
  React.useEffect(() => {
    if (!voiceChatEnabled || voiceChat.state === "idle") return
    const originalTitle = document.title
    const emoji = {
      connecting: "\u{1F50C}",
      listening: "\u{1F3A4}",
      thinking: "\u{1F4AD}",
      speaking: "\u{1F50A}",
      error: "\u26A0\uFE0F"
    }[voiceChat.state] || ""
    if (emoji) {
      document.title = `${emoji} ${voiceChatStatusLabel} - Chat`
    }
    return () => {
      document.title = originalTitle
    }
  }, [voiceChatEnabled, voiceChat.state, voiceChatStatusLabel])

  // --- Voice chat toggle ---
  const handleVoiceChatToggle = React.useCallback(() => {
    if (!voiceChatAvailable) {
      notificationApi.error({
        message: t("playground:voiceChat.unavailableTitle", "Voice chat unavailable"),
        description: t(
          "playground:voiceChat.unavailableBody",
          "Connect to a tldw server with audio chat streaming enabled."
        )
      })
      return
    }
    if (!voiceChatEnabled) {
      if (isListening) stopSpeechRecognition()
      if (isServerDictating) stopServerDictation()
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("tldw:playground-starter-selected", {
            detail: { mode: "voice" }
          })
        )
      }
    }
    if (voiceChatEnabled) {
      voiceChatMessages.abandonTurn()
    }
    setVoiceChatEnabled(!voiceChatEnabled)
  }, [
    voiceChatAvailable,
    voiceChatEnabled,
    isListening,
    isServerDictating,
    notificationApi,
    setVoiceChatEnabled,
    stopSpeechRecognition,
    stopServerDictation,
    t,
    voiceChatMessages
  ])

  // --- Dictation toggle ---
  const handleDictationToggle = React.useCallback(() => {
    if (pendingDictationStart) {
      setPendingDictationStart(false)
      return
    }

    switch (dictationToggleIntent) {
      case "start_server":
        if (!dictationSourceReady) {
          setPendingDictationStart(true)
          return
        }
        void startServerDictation(requestedServerDictationSource)
        break
      case "stop_server":
        setPendingDictationStart(false)
        stopServerDictation()
        break
      case "start_browser":
        if (!dictationSourceReady) {
          setPendingDictationStart(true)
          return
        }
        startBrowserDictation()
        break
      case "stop_browser":
        setPendingDictationStart(false)
        stopSpeechRecognition()
        break
      default:
        break
    }
    const snapshot = dictationDiagnosticsSnapshotRef.current
    emitDictationDiagnostics({
      surface: "playground",
      kind: "toggle",
      requestedMode: snapshot.requestedMode,
      resolvedMode: snapshot.resolvedMode,
      requestedSourceKind: snapshot.requestedSourceKind,
      resolvedSourceKind: snapshot.resolvedSourceKind,
      speechAvailable: snapshot.speechAvailable,
      speechUsesServer: snapshot.speechUsesServer,
      toggleIntent: dictationToggleIntent,
      fallbackReason: snapshot.fallbackReason
    })
  }, [
    dictationSourceReady,
    dictationToggleIntent,
    pendingDictationStart,
    startBrowserDictation,
    startServerDictation,
    requestedServerDictationSource,
    stopServerDictation,
    stopSpeechRecognition
  ])

  React.useEffect(() => {
    if (!pendingDictationStart) return
    if (!dictationSourceReady) return
    if (!runPendingDictationStart()) {
      setPendingDictationStart(false)
      return
    }
    setPendingDictationStart(false)
  }, [dictationSourceReady, pendingDictationStart, runPendingDictationStart])

  // Sync transcript to message value
  React.useEffect(() => {
    if (isListening) {
      setMessageValue(transcript, { collapseLarge: true, forceCollapse: true })
    }
  }, [transcript, isListening, setMessageValue])

  const stopListening = React.useCallback(async () => {
    if (isListening) {
      stopSpeechRecognition()
    }
  }, [isListening, stopSpeechRecognition])

  return {
    // Speech recognition state
    transcript,
    isListening,
    resetTranscript,
    browserSupportsSpeechRecognition,
    dictationAudioSourcePreference,
    dictationResolvedSourceKind: resolvedDictationSourceKind,
    setDictationAudioSourcePreference,
    // Server dictation
    isServerDictating,
    startServerDictation,
    stopServerDictation,
    // Dictation strategy
    speechAvailable,
    speechUsesServer,
    dictationToggleIntent,
    // STT settings
    sttSettings,
    // Labels & tooltip
    voiceChatStatusLabel,
    speechTooltipText,
    // Handlers
    handleVoiceChatToggle,
    handleDictationToggle,
    startBrowserDictation,
    stopListening
  }
}
