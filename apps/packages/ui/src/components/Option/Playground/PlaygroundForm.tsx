import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import React from "react"
import { useMessageOption } from "~/hooks/useMessageOption"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"
import {
  Dropdown,
  Input,
  InputNumber,
  Radio,
  Select,
  Switch,
  Tooltip,
  Modal,
  Button
} from "antd"
import { useWebUI } from "~/store/webui"
import {
  ChevronRight,
  ImageIcon,
  Headphones,
  X,
  CornerUpLeft,
  HelpCircle,
  ArrowRight
} from "lucide-react"
import { getVariable } from "@/utils/select-variable"
import { useTranslation } from "react-i18next"
import type {
  DictationModePreference
} from "@/hooks/useDictationStrategy"
import { isFirefoxTarget } from "@/config/platform"
import { handleChatInputKeyDown } from "@/utils/key-down"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { useStorage } from "@plasmohq/storage/hook"
import { useTabMentions } from "~/hooks/useTabMentions"
import { useFocusShortcuts } from "~/hooks/keyboard"
// isMac moved to PlaygroundSendControl
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { useVoiceChatSettings } from "@/hooks/useVoiceChatSettings"
import { useVoiceChatStream } from "@/hooks/useVoiceChatStream"
import { useVoiceChatMessages } from "@/hooks/useVoiceChatMessages"
import { MentionsDropdown } from "./MentionsDropdown"
import { ComposerTextarea } from "./ComposerTextarea"
import { ComposerToolbar } from "./ComposerToolbar"
// ContextFootprintPanel moved to PlaygroundContextWindowModal
import { CompareToggle } from "./CompareToggle"
import { useMobileComposerViewport } from "./useMobileComposerViewport"
import { PASTED_TEXT_CHAR_LIMIT } from "@/utils/constant"
import { isFireFoxPrivateMode } from "@/utils/is-private-mode"
import { CurrentChatModelSettings } from "@/components/Common/Settings/CurrentChatModelSettings"
import { ActorPopout } from "@/components/Common/Settings/ActorPopout"
import { ChatQueuePanel } from "@/components/Common/ChatQueuePanel"
import { useConnectionState } from "@/hooks/useConnectionState"
import { ConnectionPhase, deriveConnectionUxState } from "@/types/connection"
import { Link, useNavigate } from "react-router-dom"
import { fetchChatModels, fetchImageModels } from "@/services/tldw-server"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useTldwAudioStatus } from "@/hooks/useTldwAudioStatus"
import { useMcpTools } from "@/hooks/useMcpTools"
import {
  tldwClient
} from "@/services/tldw/TldwApiClient"
// ChatRequestDebugSnapshot moved to usePlaygroundRawPreview
import {
  buildDiscussMediaHint,
  getMediaChatHandoffMode,
  normalizeMediaChatHandoffPayload,
  parseMediaIdAsNumber
} from "@/services/tldw/media-chat-handoff"
import {
  normalizeWatchlistChatHandoffPayload,
  buildWatchlistChatHint
} from "@/services/tldw/watchlist-chat-handoff"
// getImageBackendConfigs, normalizeImageBackendConfig, resolveImageBackendConfig moved to usePlaygroundImageGen
import { CharacterSelect } from "@/components/Common/CharacterSelect"
import { ProviderIcons } from "@/components/Common/ProviderIcon"
import type { Character } from "@/types/character"
import { type KnowledgeTab } from "@/components/Knowledge"
import { BetaTag } from "@/components/Common/Beta"
import type { SlashCommandItem } from "@/components/Sidepanel/Chat/SlashCommandMenu"
import { DocumentGeneratorDrawer } from "@/components/Common/Playground/DocumentGeneratorDrawer"
import { useUiModeStore } from "@/store/ui-mode"
import {
  useStoreChatModelSettings,
  type ChatModelSettings
} from "@/store/model"
import { getAllPrompts } from "@/db/dexie/helpers"
import { getPresetByKey } from "./ParameterPresets"
import { TokenProgressBar } from "./TokenProgressBar"
import { AttachmentsSummary } from "./AttachmentsSummary"
import { VoiceChatIndicator } from "./VoiceChatIndicator"
import { VoiceModeSelector } from "./VoiceModeSelector"
import { PlaygroundImageGenModal } from "./PlaygroundImageGenModal"
import { PlaygroundRawRequestModal } from "./PlaygroundRawRequestModal"
import { PlaygroundStartupTemplateModal } from "./PlaygroundStartupTemplateModal"
import { PlaygroundContextWindowModal } from "./PlaygroundContextWindowModal"
import { PlaygroundMcpSettingsModal } from "./PlaygroundMcpSettingsModal"
import { PlaygroundToolsPopover } from "./PlaygroundToolsPopover"
import { PlaygroundModeLauncher } from "./PlaygroundModeLauncher"
import { PlaygroundMcpControl } from "./PlaygroundMcpControl"
import { PlaygroundSendControl, PlaygroundAttachmentButton } from "./PlaygroundSendControl"
import { PlaygroundComposerNotices } from "./PlaygroundComposerNotices"
import { PlaygroundKnowledgeSection } from "./PlaygroundKnowledgeSection"
import { useMobile } from "@/hooks/useMediaQuery"
import { clearSetting, getSetting } from "@/services/settings/registry"
import { DISCUSS_MEDIA_PROMPT_SETTING, DISCUSS_WATCHLIST_PROMPT_SETTING } from "@/services/settings/ui-settings"
// TldwButton moved to extracted sub-components
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useStoreMessageOption } from "@/store/option"
import {
  shouldEnableOptionalResource,
  useChatSurfaceCoordinatorStore
} from "@/store/chat-surface-coordinator"
import { trackOnboardingChatSubmitSuccess } from "@/utils/onboarding-ingestion-telemetry"
// resolveApiProviderForModel moved to usePlaygroundRawPreview and usePlaygroundImageGen
import {
  DEFAULT_CHARACTER_STORAGE_KEY,
  defaultCharacterStorage,
  isFreshChatState,
  resolveCharacterSelectionId,
  shouldApplyDefaultCharacter,
  shouldResetDefaultCharacterBootstrap
} from "@/utils/default-character-preference"
import { resolveStartupSelectedModel } from "@/utils/model-startup-selection"
import {
  useModelSelector,
  useComposerTokens,
  useImageBackend,
  useActionBarVisibility,
  useSlashCommands,
  useMessageCollapse,
  useDeferredComposerInput,
  useMcpToolsControl,
  type CollapsedRange,
  type ModelSortMode
} from "@/hooks/playground"
// useQueuedRequests moved to usePlaygroundQueueManagement
import type { ChatDocuments } from "@/models/ChatTypes"
import { DEFAULT_CHAT_SETTINGS } from "@/types/chat-settings"
import {
  buildConversationSummaryCheckpointPrompt
} from "./conversation-summary-checkpoint"
// SessionInsightsPanel moved to PlaygroundContextWindowModal
import {
  type ModelRecommendationAction
} from "./model-recommendations"
import {
  describeStartupTemplatePrompt,
  resolveStartupTemplatePrompt,
  type StartupTemplateBundle
} from "./startup-template-bundles"
import {
  PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY,
  resolveImageGenerationEventSyncMode,
  normalizeImageGenerationEventSyncMode,
  normalizeImageGenerationEventSyncPolicy,
  type ImageGenerationEventSyncPolicy,
  type ImageGenerationEventSyncMode,
  type ImageGenerationRefineMetadata,
  type ImageGenerationRequestSnapshot
} from "@/utils/image-generation-chat"
// buildImagePromptRefineMessages, extractImagePromptRefineCandidate moved to usePlaygroundImageGen
// QueuedRequest moved to usePlaygroundQueueManagement
// WeightedImagePromptContextEntry moved to usePlaygroundImageGen
// CompareResponseDiff moved to usePlaygroundImageGen
import {
  useModelComparison,
  useContextWindow,
  usePlaygroundVoiceChat,
  usePromptTemplates,
  usePlaygroundAttachments,
  useComposerInput,
  usePlaygroundImageGen,
  usePlaygroundPersistence,
  usePlaygroundRawPreview,
  usePlaygroundQueueManagement,
  usePlaygroundSettings,
  usePlaygroundContextItems,
  usePlaygroundSubmit,
  toText,
  estimateTokensFromText
} from "./hooks"

type Props = {
  droppedFiles: File[]
}

type DefaultCharacterPreferenceQueryResult = {
  defaultCharacterId: string | null
}

type PlaygroundQueuedSourceContext = {
  documents?: ChatDocuments
  imageBackendOverride?: string
  isImageCommand?: boolean
}

export const PlaygroundForm = ({ droppedFiles }: Props) => {
  const { t } = useTranslation(["playground", "common", "option"])
  const notificationApi = useAntdNotification()
  const navigate = useNavigate()

  const [checkWideMode] = useStorage("checkWideMode", false)
  const [allowExternalImages, setAllowExternalImages] = useStorage(
    "allowExternalImages",
    DEFAULT_CHAT_SETTINGS.allowExternalImages
  )
  const [showMoodBadge, setShowMoodBadge] = useStorage(
    "chatShowMoodBadge",
    true
  )
  const {
    onSubmit,
    messages,
    selectedModel,
    selectedModelIsLoading,
    setSelectedModel,
    chatMode,
    setChatMode,
    compareMode,
    setCompareMode,
    compareFeatureEnabled,
    setCompareFeatureEnabled,
    compareSelectedModels,
    setCompareSelectedModels,
    compareMaxModels,
    setCompareMaxModels,
    speechToTextLanguage,
    stopStreamingRequest,
    streaming: isSending,
    webSearch,
    setWebSearch,
    toolChoice,
    setToolChoice,
    selectedQuickPrompt,
    textareaRef,
    setSelectedQuickPrompt,
    selectedSystemPrompt,
    setSelectedSystemPrompt,
    temporaryChat,
    setTemporaryChat,
    clearChat,
    useOCR,
    setUseOCR,
    defaultInternetSearchOn,
    setHistory,
    historyId,
    history,
    uploadedFiles,
    fileRetrievalEnabled,
    setFileRetrievalEnabled,
    handleFileUpload,
    removeUploadedFile,
    clearUploadedFiles,
    queuedMessages,
    setQueuedMessages,
    serverChatId,
    setServerChatId,
    serverChatState,
    setServerChatState,
    serverChatSource,
    setServerChatSource,
    setServerChatVersion,
    replyTarget,
    clearReplyTarget,
    ragPinnedResults,
    messageSteeringMode,
    messageSteeringForceNarrate,
    contextFiles,
    documentContext,
    selectedKnowledge,
    ragMediaIds,
    chatLoopState = {
      status: "idle",
      pendingApprovals: [],
      inflightToolCallIds: []
    }
  } = useMessageOption()
  const setRagMediaIds = useStoreMessageOption((s) => s.setRagMediaIds)
  const setRagPinnedResults = useStoreMessageOption((s) => s.setRagPinnedResults)
  const { settings: chatSettings, updateSettings: updateChatSettings } =
    useChatSettingsRecord({
      historyId,
      serverChatId
    })
  const [imageEventSyncGlobalDefault, setImageEventSyncGlobalDefault] =
    useStorage<ImageGenerationEventSyncMode>(
      PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY,
      "off"
    )
  const imageEventSyncChatMode = React.useMemo(
    () => normalizeImageGenerationEventSyncMode(chatSettings?.imageEventSyncMode, "off"),
    [chatSettings?.imageEventSyncMode]
  )

  const [autoSubmitVoiceMessage] = useStorage("autoSubmitVoiceMessage", false)
  const isMobileViewport = useMobile()
  const mobileComposerViewport = useMobileComposerViewport(isMobileViewport)
  const [openModelSettings, setOpenModelSettings] = React.useState(false)
  const [openActorSettings, setOpenActorSettings] = React.useState(false)
  const [noticesExpanded, setNoticesExpanded] = React.useState(false)
  const systemPrompt = useStoreChatModelSettings((state) => state.systemPrompt)
  const setSystemPrompt = useStoreChatModelSettings(
    (state) => state.setSystemPrompt
  )
  const currentChatModelSettings = useStoreChatModelSettings((state) => ({
    temperature: state.temperature,
    numPredict: state.numPredict,
    topP: state.topP,
    topK: state.topK,
    frequencyPenalty: state.frequencyPenalty,
    presencePenalty: state.presencePenalty,
    repeatPenalty: state.repeatPenalty,
    reasoningEffort: state.reasoningEffort,
    historyMessageLimit: state.historyMessageLimit,
    historyMessageOrder: state.historyMessageOrder,
    slashCommandInjectionMode: state.slashCommandInjectionMode,
    apiProvider: state.apiProvider,
    extraHeaders: state.extraHeaders,
    extraBody: state.extraBody,
    llamaThinkingBudgetTokens: state.llamaThinkingBudgetTokens,
    llamaGrammarMode: state.llamaGrammarMode,
    llamaGrammarId: state.llamaGrammarId,
    llamaGrammarInline: state.llamaGrammarInline,
    llamaGrammarOverride: state.llamaGrammarOverride,
    jsonMode: state.jsonMode
  }))
  const numCtx = useStoreChatModelSettings((state) => state.numCtx)
  const updateChatModelSetting = useStoreChatModelSettings(
    (state) => state.updateSetting
  )
  const updateChatModelSettings = useStoreChatModelSettings(
    (state) => state.updateSettings
  )
  const { data: promptLibrary = [] } = useQuery({
    queryKey: ["playgroundStartupPromptLibrary"],
    queryFn: getAllPrompts
  })
  const {
    voiceChatEnabled,
    setVoiceChatEnabled,
    voiceChatModel,
    setVoiceChatModel,
    voiceChatPauseMs,
    setVoiceChatPauseMs,
    voiceChatTriggerPhrases,
    setVoiceChatTriggerPhrases,
    voiceChatAutoResume,
    setVoiceChatAutoResume,
    voiceChatBargeIn,
    setVoiceChatBargeIn,
    voiceChatTtsMode,
    setVoiceChatTtsMode
  } = useVoiceChatSettings()
  const voiceChatMessages = useVoiceChatMessages()
  const [voiceChatTriggerInput, setVoiceChatTriggerInput] = React.useState(
    voiceChatTriggerPhrases.join(", ")
  )
  React.useEffect(() => {
    const next = voiceChatTriggerPhrases.join(", ")
    setVoiceChatTriggerInput((prev) => (prev === next ? prev : next))
  }, [voiceChatTriggerPhrases])

  const connectionState = useConnectionState()
  const { phase, isConnected } = connectionState
  const connectionUxState = React.useMemo(
    () => deriveConnectionUxState(connectionState),
    [connectionState]
  )
  const setOptionalPanelVisible = useChatSurfaceCoordinatorStore(
    (state) => state.setPanelVisible
  )
  const markOptionalPanelEngaged = useChatSurfaceCoordinatorStore(
    (state) => state.markPanelEngaged
  )
  const mcpToolsEnabled = useChatSurfaceCoordinatorStore((state) =>
    shouldEnableOptionalResource(state, "mcp-tools")
  )
  const audioHealthEnabled = useChatSurfaceCoordinatorStore((state) =>
    shouldEnableOptionalResource(state, "audio-health")
  )
  const modelCatalogEnabled = useChatSurfaceCoordinatorStore((state) =>
    shouldEnableOptionalResource(state, "model-catalog")
  )
  const isConnectionReady = isConnected && phase === ConnectionPhase.CONNECTED
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const {
    hasMcp,
    healthState: mcpHealthState,
    tools: mcpTools,
    toolsLoading: mcpToolsLoading,
    catalogs: mcpCatalogs,
    catalogsLoading: mcpCatalogsLoading,
    toolCatalog,
    toolCatalogId,
    toolModules,
    moduleOptions,
    moduleOptionsLoading,
    toolCatalogStrict,
    setToolCatalog,
    setToolCatalogId,
    setToolModules,
    setToolCatalogStrict
  } = useMcpTools({ enabled: mcpToolsEnabled })
  const mcpCtrl = useMcpToolsControl({
    hasMcp,
    mcpHealthState,
    mcpTools,
    mcpToolsLoading,
    mcpCatalogs,
    toolCatalog,
    toolCatalogId,
    setToolCatalog,
    setToolCatalogId,
    toolChoice
  })
  const handleModuleSelect = React.useCallback(
    (value?: string[]) => {
      setToolModules(Array.isArray(value) ? value : [])
    },
    [setToolModules]
  )
  const hasServerVoiceChat =
    isConnectionReady &&
    !capsLoading &&
    Boolean(
      capabilities?.hasVoiceChat ??
        (capabilities?.hasStt && capabilities?.hasTts)
    )
  const hasServerStt =
    isConnectionReady &&
    !capsLoading &&
    Boolean(capabilities?.hasStt)
  const { healthState: audioHealthState, sttHealthState } = useTldwAudioStatus({
    enabled: audioHealthEnabled
  })
  const canUseServerAudio =
    hasServerVoiceChat && audioHealthState !== "unhealthy"
  const canUseServerStt = hasServerStt && sttHealthState !== "unhealthy"
  const voiceChatAvailable = canUseServerAudio
  const voiceChat = useVoiceChatStream({
    active: voiceChatEnabled && voiceChatAvailable,
    onTranscript: (text) => {
      voiceChatMessages.beginTurn(text)
    },
    onAssistantDelta: (delta) => {
      voiceChatMessages.appendAssistantDelta(delta)
    },
    onAssistantMessage: (text) => {
      void voiceChatMessages.finalizeAssistant(text)
    },
    onError: (msg) => {
      notificationApi.error({
        message: t("playground:voiceChat.errorTitle", "Voice chat error"),
        description: msg
      })
      voiceChatMessages.abandonTurn()
      setVoiceChatEnabled(false)
    },
    onWarning: (msg) => {
      notificationApi.warning({
        message: t("playground:voiceChat.warningTitle", "Voice chat warning"),
        description: msg
      })
    }
  })
  const [hasShownConnectBanner, setHasShownConnectBanner] = React.useState(false)
  const [showConnectBanner, setShowConnectBanner] = React.useState(false)
  const [documentGeneratorOpen, setDocumentGeneratorOpen] =
    React.useState(false)
  const [voiceModeSelectorOpen, setVoiceModeSelectorOpen] = React.useState(false)
  const [modeLauncherOpen, setModeLauncherOpen] = React.useState(false)
  const [modeAnnouncement, setModeAnnouncement] = React.useState<string | null>(
    null
  )
  const previousPresetKeyRef = React.useRef<string | null>(null)
  const previousJsonModeRef = React.useRef<boolean | null>(null)
  const previousCharacterNameRef = React.useRef<string | null>(null)
  const [toolsPopoverOpen, setToolsPopoverOpen] = React.useState(false)
  const [attachmentMenuOpen, setAttachmentMenuOpen] = React.useState(false)
  const [sendMenuOpen, setSendMenuOpen] = React.useState(false)
  const [documentGeneratorSeed, setDocumentGeneratorSeed] = React.useState<{
    conversationId?: string | null
    message?: string | null
    messageId?: string | null
  }>({})
  const [autoStopTimeout] = useStorage("autoStopTimeout", 2000)
  const [dictationAutoFallbackEnabled] = useStorage(
    "dictation_auto_fallback",
    false
  )
  const [dictationModeOverride] = useStorage<DictationModePreference | null>(
    "dictationModeOverride",
    null
  )
  const [sttModel] = useStorage("sttModel", "whisper-1")
  const [sttUseSegmentation] = useStorage("sttUseSegmentation", false)
  const [sttTimestampGranularities] = useStorage(
    "sttTimestampGranularities",
    "segment"
  )
  const [sttPrompt] = useStorage("sttPrompt", "")
  const [sttTask] = useStorage("sttTask", "transcribe")
  const [sttResponseFormat] = useStorage("sttResponseFormat", "json")
  const [sttTemperature] = useStorage("sttTemperature", 0)
  const [sttSegK] = useStorage("sttSegK", 6)
  const [sttSegMinSegmentSize] = useStorage("sttSegMinSegmentSize", 5)
  const [sttSegLambdaBalance] = useStorage("sttSegLambdaBalance", 0.01)
  const [sttSegUtteranceExpansionWidth] = useStorage(
    "sttSegUtteranceExpansionWidth",
    2
  )
  const [sttSegEmbeddingsProvider] = useStorage("sttSegEmbeddingsProvider", "")
  const [sttSegEmbeddingsModel] = useStorage("sttSegEmbeddingsModel", "")
  const [selectedCharacter, setSelectedCharacter] =
    useSelectedCharacter<Character | null>(null)
  const [defaultCharacter, setDefaultCharacter] = useStorage<Character | null>(
    {
      key: DEFAULT_CHARACTER_STORAGE_KEY,
      instance: defaultCharacterStorage
    },
    null
  )
  const { data: defaultCharacterPreference } = useQuery<DefaultCharacterPreferenceQueryResult>({
    queryKey: ["tldw:defaultCharacterPreference:playground"],
    queryFn: async () => {
      await tldwClient.initialize()
      const defaultCharacterId = await tldwClient.getDefaultCharacterPreference()
      return { defaultCharacterId }
    },
    staleTime: 60 * 1000,
    throwOnError: false
  })
  const [showMoodConfidence, setShowMoodConfidence] = useStorage(
    "chatShowMoodConfidence",
    Boolean(selectedCharacter?.id) && !compareMode
  )
  const [startupTemplatesRaw, setStartupTemplatesRaw] = useStorage(
    "playgroundStartupTemplateBundles",
    "[]"
  )
  const [serverPersistenceHintSeen, setServerPersistenceHintSeen] = useStorage(
    "serverPersistenceHintSeen",
    false
  )
  // showServerPersistenceHint and serverSaveInFlightRef moved to usePlaygroundPersistence
  const uiMode = useUiModeStore((state) => state.mode)
  const isProMode = uiMode === "pro"
  const [contextToolsOpen, setContextToolsOpen] = useStorage(
    "playgroundKnowledgeSearchOpen",
    false
  )
  const [simpleInternetSearch, setSimpleInternetSearch] = useStorage(
    "isSimpleInternetSearch",
    true
  )
  const [, setDefaultInternetSearchOnSetting] = useStorage(
    "defaultInternetSearchOn",
    false
  )
  const [knowledgePanelTab, setKnowledgePanelTab] =
    React.useState<KnowledgeTab>("search")
  const [knowledgePanelTabRequestId, setKnowledgePanelTabRequestId] =
    React.useState(0)
  const [lastSubmittedContext, setLastSubmittedContext] = React.useState<{
    model: string | null
    compareEnabled: boolean
    compareCount: number
    characterName: string | null
    promptSummary: string
    jsonMode: boolean
    temporaryChat: boolean
    webSearch: boolean
    contextToolsOpen: boolean
  } | null>(null)
  const replyLabel = replyTarget
    ? [
        t("common:replyingTo", "Replying to"),
        replyTarget.name ? `${replyTarget.name}:` : null,
        replyTarget.preview
      ]
        .filter(Boolean)
        .join(" ")
    : ""

  const storedCharacterId = React.useMemo(
    () => resolveCharacterSelectionId(selectedCharacter),
    [selectedCharacter]
  )
  const localDefaultCharacterId = React.useMemo(
    () => resolveCharacterSelectionId(defaultCharacter),
    [defaultCharacter]
  )
  const serverDefaultCharacterId = defaultCharacterPreference?.defaultCharacterId
  const effectiveDefaultCharacter = React.useMemo<Character | null>(() => {
    if (typeof serverDefaultCharacterId === "undefined") {
      return defaultCharacter
    }
    if (!serverDefaultCharacterId) {
      return null
    }
    if (
      localDefaultCharacterId === serverDefaultCharacterId &&
      defaultCharacter
    ) {
      return defaultCharacter
    }
    return { id: serverDefaultCharacterId } as Character
  }, [defaultCharacter, localDefaultCharacterId, serverDefaultCharacterId])
  const effectiveDefaultCharacterId = React.useMemo(
    () => resolveCharacterSelectionId(effectiveDefaultCharacter),
    [effectiveDefaultCharacter]
  )
  const isFreshChat = React.useMemo(
    () => isFreshChatState(serverChatId, messages.length),
    [messages.length, serverChatId]
  )
  const defaultCharacterBootstrapAppliedRef = React.useRef(false)
  const previousFreshChatRef = React.useRef(isFreshChat)

  React.useEffect(() => {
    if (typeof serverDefaultCharacterId === "undefined") return

    if (!serverDefaultCharacterId) {
      if (localDefaultCharacterId) {
        void setDefaultCharacter(null)
      }
      return
    }

    if (localDefaultCharacterId === serverDefaultCharacterId) return
    void setDefaultCharacter({ id: serverDefaultCharacterId } as Character)
  }, [
    localDefaultCharacterId,
    serverDefaultCharacterId,
    setDefaultCharacter
  ])

  React.useEffect(() => {
    defaultCharacterBootstrapAppliedRef.current = false
  }, [effectiveDefaultCharacterId])

  React.useEffect(() => {
    if (
      shouldResetDefaultCharacterBootstrap(
        previousFreshChatRef.current,
        isFreshChat
      )
    ) {
      defaultCharacterBootstrapAppliedRef.current = false
    }
    previousFreshChatRef.current = isFreshChat
  }, [isFreshChat])

  React.useEffect(() => {
    if (!effectiveDefaultCharacter || !effectiveDefaultCharacterId) return
    if (
      !shouldApplyDefaultCharacter({
        defaultCharacterId: effectiveDefaultCharacterId,
        selectedCharacterId: storedCharacterId,
        isFreshChat,
        hasAppliedInSession: defaultCharacterBootstrapAppliedRef.current
      })
    ) {
      return
    }

    defaultCharacterBootstrapAppliedRef.current = true
    void setSelectedCharacter(effectiveDefaultCharacter)
  }, [
    effectiveDefaultCharacter,
    effectiveDefaultCharacterId,
    isFreshChat,
    setSelectedCharacter,
    storedCharacterId
  ])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handler = () => setOpenActorSettings(true)
    window.addEventListener("tldw:open-actor-settings", handler)
    return () => {
      window.removeEventListener("tldw:open-actor-settings", handler)
    }
  }, [])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handler = () => setOpenModelSettings(true)
    window.addEventListener("tldw:open-model-settings", handler)
    return () => {
      window.removeEventListener("tldw:open-model-settings", handler)
    }
  }, [])

  React.useEffect(() => {
    if (!modeAnnouncement) return
    const timer = window.setTimeout(() => {
      setModeAnnouncement(null)
    }, 3000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [modeAnnouncement])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handler = (event: Event) => {
      const detail = (event as CustomEvent)?.detail || {}
      setDocumentGeneratorSeed({
        conversationId: detail?.conversationId ?? serverChatId ?? null,
        message: detail?.message ?? null,
        messageId: detail?.messageId ?? null
      })
      setDocumentGeneratorOpen(true)
    }
    window.addEventListener("tldw:open-document-generator", handler)
    return () => {
      window.removeEventListener("tldw:open-document-generator", handler)
    }
  }, [serverChatId])

  const {
    tabMentionsEnabled,
    showMentions,
    mentionPosition,
    filteredTabs,
    availableTabs,
    selectedDocuments,
    handleTextChange,
    insertMention,
    closeMentions,
    addDocument,
    removeDocument,
    clearSelectedDocuments,
    reloadTabs,
    handleMentionsOpen
  } = useTabMentions(textareaRef)

  const { data: composerModels } = useQuery({
    queryKey: ["playground:chatModels"],
    queryFn: () => fetchChatModels({ returnEmpty: true }),
    enabled: modelCatalogEnabled
  })
  const { data: imageModels = [] } = useQuery({
    queryKey: ["playground:imageModels"],
    queryFn: () => fetchImageModels({ returnEmpty: true }),
    enabled: true
  })

  const {
    modelDropdownOpen,
    setModelDropdownOpen,
    modelSearchQuery,
    setModelSearchQuery,
    modelSortMode,
    setModelSortMode,
    selectedModelMeta,
    modelContextLength,
    modelCapabilities,
    resolvedMaxContext,
    resolvedProviderKey,
    providerLabel,
    modelSummaryLabel,
    apiModelLabel,
    modelSelectorWarning,
    favoriteModels,
    favoriteModelsIsLoading,
    favoriteModelSet,
    toggleFavoriteModel,
    filteredModels,
    modelDropdownMenuItems,
    isSmallModel
  } = useModelSelector({
    composerModels,
    selectedModel,
    setSelectedModel,
    navigate
  })

  React.useEffect(() => {
    setOptionalPanelVisible("model-catalog", modelDropdownOpen)
    if (modelDropdownOpen) {
      markOptionalPanelEngaged("model-catalog")
    }

    return () => {
      setOptionalPanelVisible("model-catalog", false)
    }
  }, [markOptionalPanelEngaged, modelDropdownOpen, setOptionalPanelVisible])

  React.useEffect(() => {
    setOptionalPanelVisible("audio-health", voiceChatEnabled)
    if (voiceChatEnabled) {
      markOptionalPanelEngaged("audio-health")
    }

    return () => {
      setOptionalPanelVisible("audio-health", false)
    }
  }, [markOptionalPanelEngaged, setOptionalPanelVisible, voiceChatEnabled])

  // Auto-select model on initial load when no model is selected
  // Priority: 1) First favorite model, 2) First available model
  React.useEffect(() => {
    const nextModel = resolveStartupSelectedModel({
      currentModel: selectedModel,
      models: (composerModels as any[]) || [],
      preferredModelIds: favoriteModels,
      isCurrentModelHydrating: selectedModelIsLoading,
      arePreferencesHydrating: favoriteModelsIsLoading
    })
    if (nextModel) {
      setSelectedModel(nextModel)
    }
  }, [
    composerModels,
    favoriteModels,
    favoriteModelsIsLoading,
    selectedModel,
    selectedModelIsLoading,
    setSelectedModel
  ])

  const hasPromptContext = React.useMemo(
    () =>
      Boolean(selectedSystemPrompt) ||
      Boolean(selectedQuickPrompt) ||
      String(systemPrompt || "").trim().length > 0,
    [selectedQuickPrompt, selectedSystemPrompt, systemPrompt]
  )

  const modelComparison = useModelComparison({
    composerModels,
    selectedModel,
    setSelectedModel,
    compareFeatureEnabled,
    compareMode,
    setCompareMode,
    compareSelectedModels,
    setCompareSelectedModels,
    compareMaxModels,
    selectedCharacterName: selectedCharacter?.name || null,
    ragPinnedResultsLength: ragPinnedResults.length,
    webSearch,
    hasPromptContext,
    jsonMode: Boolean(currentChatModelSettings.jsonMode),
    voiceChatEnabled,
    t
  })
  const {
    compareModeActive,
    compareModelMetaById,
    availableCompareModels,
    compareModelLabelById,
    compareSelectedModelLabels,
    compareNeedsMoreModels,
    compareModelsSupportCapability,
    compareCapabilityIncompatibilities,
    toggleCompareMode,
    handleAddCompareModel,
    handleRemoveCompareModel,
    sendLabel
  } = modelComparison

  const voiceChatModelOptions = React.useMemo(() => {
    const options = [
      {
        value: "",
        label: t("playground:voiceChat.useChatModel", "Use chat model")
      }
    ]
    const models = (composerModels as any[]) || []
    for (const model of models) {
      const pLabel = getProviderDisplayName(model.provider || "")
      const modelLabel = model.nickname || model.model || model.name
      const label = pLabel
        ? `${pLabel} - ${modelLabel}`
        : modelLabel
      options.push({
        value: model.model || model.name,
        label
      })
    }
    return options
  }, [composerModels, t])

  const promptTemplates = usePromptTemplates({
    startupTemplatesRaw,
    setStartupTemplatesRaw,
    promptLibrary,
    selectedModel,
    systemPrompt,
    selectedSystemPrompt,
    selectedQuickPrompt,
    selectedCharacter,
    ragPinnedResults,
    currentChatModelSettings,
    setSelectedModel,
    setSelectedSystemPrompt,
    setSelectedQuickPrompt,
    setSystemPrompt,
    setSelectedCharacter,
    setRagPinnedResults,
    updateChatModelSettings,
    compareModeActive,
    setCompareSelectedModels,
    setModeAnnouncement,
    t
  })
  const {
    currentPresetKey,
    currentPreset,
    startupTemplates,
    startupTemplateDraftName,
    setStartupTemplateDraftName,
    startupTemplatePreview,
    setStartupTemplatePreview,
    startupTemplateNameFallback,
    selectedSystemPromptRecord,
    handleSaveStartupTemplate,
    handleOpenStartupTemplatePreview,
    handleApplyStartupTemplate,
    handleDeleteStartupTemplate,
    handleTemplateSelect,
    promptSummaryLabel
  } = promptTemplates
  React.useEffect(() => {
    if (previousPresetKeyRef.current == null) {
      previousPresetKeyRef.current = currentPresetKey
      return
    }
    if (previousPresetKeyRef.current !== currentPresetKey) {
      if (currentPresetKey === "custom") {
        setModeAnnouncement(
          t(
            "playground:composer.presetChangedCustom",
            "Preset switched to Custom."
          )
        )
      } else {
        const presetLabel = currentPreset
          ? t(`playground:presets.${currentPreset.key}.label`, currentPreset.label)
          : currentPresetKey
        setModeAnnouncement(
          toText(
            t("playground:composer.presetChanged", "{{preset}} preset applied.", {
              preset: presetLabel
            } as any)
          )
        )
      }
    }
    previousPresetKeyRef.current = currentPresetKey
  }, [currentPreset, currentPresetKey, t])
  const isJsonModeActive = Boolean(currentChatModelSettings.jsonMode)
  React.useEffect(() => {
    if (previousJsonModeRef.current == null) {
      previousJsonModeRef.current = isJsonModeActive
      return
    }
    if (previousJsonModeRef.current !== isJsonModeActive) {
      setModeAnnouncement(
        isJsonModeActive
          ? t("playground:composer.jsonModeEnabledNotice", "JSON mode enabled.")
          : t("playground:composer.jsonModeDisabledNotice", "JSON mode disabled.")
      )
    }
    previousJsonModeRef.current = isJsonModeActive
  }, [isJsonModeActive, t])
  React.useEffect(() => {
    const currentCharacterName =
      typeof selectedCharacter?.name === "string" &&
      selectedCharacter.name.trim().length > 0
        ? selectedCharacter.name.trim()
        : null
    if (previousCharacterNameRef.current == null) {
      previousCharacterNameRef.current = currentCharacterName
      return
    }
    if (currentCharacterName !== previousCharacterNameRef.current) {
      setModeAnnouncement(
        currentCharacterName
          ? t(
              "playground:composer.characterAppliesNextTurn",
              "Character updates apply on the next turn."
            )
          : t(
              "playground:composer.characterClearedNotice",
              "Character mode cleared."
            )
      )
    }
    previousCharacterNameRef.current = currentCharacterName
  }, [selectedCharacter?.name, t])
  const connectionStatusLabel = React.useMemo(() => {
    if (!isConnectionReady) {
      return t("playground:composer.providerStatusOffline", "Offline")
    }
    if (connectionUxState === "connected_degraded") {
      return t("playground:composer.providerStatusDegraded", "Degraded")
    }
    return t("playground:composer.providerStatusHealthy", "Healthy")
  }, [connectionUxState, isConnectionReady, t])
  const isSessionDegraded = React.useMemo(
    () =>
      !isConnectionReady || connectionUxState === "connected_degraded",
    [connectionUxState, isConnectionReady]
  )
  const currentContextSnapshot = React.useMemo(
    () => ({
      model: selectedModel || null,
      compareEnabled: compareModeActive,
      compareCount: compareSelectedModels.length,
      characterName: selectedCharacter?.name || null,
      promptSummary: promptSummaryLabel,
      jsonMode: Boolean(currentChatModelSettings.jsonMode),
      temporaryChat,
      webSearch,
      contextToolsOpen
    }),
    [
      compareModeActive,
      compareSelectedModels.length,
      contextToolsOpen,
      currentChatModelSettings.jsonMode,
      promptSummaryLabel,
      selectedCharacter?.name,
      selectedModel,
      temporaryChat,
      webSearch
    ]
  )
  const contextDeltaLabels = React.useMemo(() => {
    if (!lastSubmittedContext) return []
    const deltas: string[] = []
    if (lastSubmittedContext.model !== currentContextSnapshot.model) {
      deltas.push(t("playground:composer.delta.model", "Model changed"))
    }
    if (
      lastSubmittedContext.compareEnabled !== currentContextSnapshot.compareEnabled ||
      lastSubmittedContext.compareCount !== currentContextSnapshot.compareCount
    ) {
      deltas.push(t("playground:composer.delta.compare", "Compare settings changed"))
    }
    if (
      lastSubmittedContext.characterName !== currentContextSnapshot.characterName
    ) {
      deltas.push(t("playground:composer.delta.character", "Character changed"))
    }
    if (lastSubmittedContext.promptSummary !== currentContextSnapshot.promptSummary) {
      deltas.push(t("playground:composer.delta.prompt", "Prompt settings changed"))
    }
    if (lastSubmittedContext.jsonMode !== currentContextSnapshot.jsonMode) {
      deltas.push(t("playground:composer.delta.json", "JSON mode changed"))
    }
    if (lastSubmittedContext.temporaryChat !== currentContextSnapshot.temporaryChat) {
      deltas.push(t("playground:composer.delta.temporary", "Save mode changed"))
    }
    if (lastSubmittedContext.webSearch !== currentContextSnapshot.webSearch) {
      deltas.push(t("playground:composer.delta.webSearch", "Web search changed"))
    }
    if (lastSubmittedContext.contextToolsOpen !== currentContextSnapshot.contextToolsOpen) {
      deltas.push(t("playground:composer.delta.knowledge", "Knowledge panel state changed"))
    }
    return deltas
  }, [currentContextSnapshot, lastSubmittedContext, t])
  const characterPendingApply = React.useMemo(() => {
    const currentName =
      typeof selectedCharacter?.name === "string"
        ? selectedCharacter.name.trim()
        : ""
    const previousName =
      typeof lastSubmittedContext?.characterName === "string"
        ? lastSubmittedContext.characterName.trim()
        : ""
    if (!currentName) return false
    if (!lastSubmittedContext) return false
    return currentName !== previousName
  }, [lastSubmittedContext, selectedCharacter?.name])
  const selectedCharacterGreeting = React.useMemo(() => {
    const raw =
      typeof selectedCharacter?.greeting === "string"
        ? selectedCharacter.greeting
        : ""
    const trimmed = raw.trim()
    return trimmed.length > 0 ? trimmed : null
  }, [selectedCharacter?.greeting])

  // Enable focus shortcuts (Shift+Esc to focus textarea)
  useFocusShortcuts(textareaRef, true)

  const [pasteLargeTextAsFile] = useStorage("pasteLargeTextAsFile", false)

  const msgCollapse = useMessageCollapse({ textareaRef })
  const {
    isMessageCollapsed,
    setIsMessageCollapsed,
    collapsedRange,
    setCollapsedRange,
    hasExpandedLargeText,
    setHasExpandedLargeText,
    pendingCaretRef,
    lastDisplaySelectionRef,
    pendingCollapsedStateRef,
    pointerDownRef,
    selectionFromPointerRef,
    normalizeCollapsedRange,
    parseCollapsedRange,
    buildCollapsedMessageLabel,
    getCollapsedDisplayMeta,
    getDisplayCaretFromMessage,
    getMessageCaretFromDisplay,
    collapseLargeMessage,
    expandLargeMessage,
    restoreMessageValue: restoreCollapseState
  } = msgCollapse

  const composerInput = useComposerInput({
    textareaRef,
    isMessageCollapsed,
    setIsMessageCollapsed,
    collapsedRange,
    setCollapsedRange,
    hasExpandedLargeText,
    setHasExpandedLargeText,
    collapseLargeMessage,
    restoreCollapseState,
    getCollapsedDisplayMeta,
    getDisplayCaretFromMessage,
    getMessageCaretFromDisplay,
    normalizeCollapsedRange,
    expandLargeMessage,
    pendingCaretRef,
    lastDisplaySelectionRef,
    pendingCollapsedStateRef,
    pointerDownRef,
    selectionFromPointerRef,
    tabMentionsEnabled,
    handleTextChange,
    isProMode
  })
  const {
    form,
    typing,
    setMessageValue,
    restoreMessageValue,
    messageDisplayValue,
    collapsedDisplayMeta,
    textAreaFocus,
    syncCollapsedCaret,
    commitCollapsedEdit,
    replaceCollapsedRange,
    handleCompositionStart,
    handleCompositionEnd,
    handleTextareaMouseDown,
    handleTextareaMouseUp,
    handleTextareaChange,
    handleTextareaSelect,
    markComposerPerf,
    measureComposerPerf,
    onComposerRenderProfile,
    wrapComposerProfile,
    draftSaved
  } = composerInput

  const { deferredInput: deferredComposerInput } = useDeferredComposerInput(
    form.values.message || ""
  )

  const {
    draftTokenCount,
    conversationTokenCount,
    tokenUsageLabel,
    tokenUsageCompactLabel,
    tokenUsageTooltip,
    estimateTokensForText
  } = useComposerTokens({
    message: form.values.message || "",
    messages,
    systemPrompt,
    resolvedMaxContext,
    apiModelLabel,
    isSending
  })
  const tokenUsageDisplay = isProMode
    ? tokenUsageLabel
    : tokenUsageCompactLabel

  const contextWindow = useContextWindow({
    draftTokenCount,
    conversationTokenCount,
    resolvedMaxContext,
    modelContextLength,
    numCtx,
    updateChatModelSetting,
    selectedCharacter,
    systemPrompt,
    selectedQuickPrompt,
    selectedSystemPrompt,
    ragPinnedResults,
    messages,
    selectedModel,
    resolvedProviderKey,
    deferredComposerInput,
    modelCapabilities,
    webSearch,
    jsonMode: Boolean(currentChatModelSettings.jsonMode),
    hasImageAttachment: Boolean(form.values.image),
    measureComposerPerf,
    t
  })
  const {
    contextWindowModalOpen,
    setContextWindowModalOpen,
    contextWindowDraftValue,
    setContextWindowDraftValue,
    sessionInsightsOpen,
    setSessionInsightsOpen,
    sessionUsageSummary,
    sessionUsageLabel,
    sessionInsights,
    projectedBudget,
    tokenBudgetRisk,
    tokenBudgetRiskLabel,
    showTokenBudgetWarning,
    tokenBudgetWarningText,
    characterContextTokenEstimate,
    systemPromptTokenEstimate,
    pinnedSourceTokenEstimate,
    historyTokenEstimate,
    summaryCheckpointSuggestion,
    modelRecommendations,
    visibleModelRecommendations,
    dismissModelRecommendation,
    contextFootprintRows,
    nonMessageContextTokenEstimate,
    nonMessageContextPercent,
    showNonMessageContextWarning,
    largestContextContributor,
    formatContextWindowValue,
    isContextWindowOverrideActive,
    requestedContextWindowOverride,
    isContextWindowOverrideClamped,
    openContextWindowModal,
    saveContextWindowSetting,
    resetContextWindowSetting,
    openSessionInsightsModal
  } = contextWindow
  const handleModelRecommendationAction = React.useCallback(
    (action: ModelRecommendationAction) => {
      if (action === "open_model_settings") {
        setOpenModelSettings(true)
        return
      }
      if (action === "enable_json_mode") {
        if (!currentChatModelSettings.jsonMode) {
          updateChatModelSetting("jsonMode", true)
        }
        setOpenModelSettings(true)
        return
      }
      if (action === "open_context_window") {
        openContextWindowModal()
        return
      }
      if (action === "open_session_insights") {
        openSessionInsightsModal()
      }
    },
    [
      currentChatModelSettings.jsonMode,
      openContextWindowModal,
      openSessionInsightsModal,
      setOpenModelSettings,
      updateChatModelSetting
    ]
  )
  const openModelApiSelector = React.useCallback(() => {
    setModelDropdownOpen(true)
  }, [setModelDropdownOpen])
  const getModelRecommendationActionLabel = React.useCallback(
    (action: ModelRecommendationAction) => {
      if (action === "enable_json_mode") {
        return t("playground:composer.recommendationEnableJson", "Enable JSON")
      }
      if (action === "open_context_window") {
        return t(
          "playground:composer.recommendationAdjustContext",
          "Adjust context"
        )
      }
      if (action === "open_session_insights") {
        return t(
          "playground:composer.recommendationOpenInsights",
          "Open insights"
        )
      }
      return t("playground:composer.recommendationReviewModels", "Review models")
    },
    [t]
  )
  const clearPromptContext = React.useCallback(() => {
    setSelectedQuickPrompt(null)
    setSelectedSystemPrompt("")
    setSystemPrompt("")
  }, [setSelectedQuickPrompt, setSelectedSystemPrompt, setSystemPrompt])
  const clearPinnedSourceContext = React.useCallback(() => {
    setRagPinnedResults([])
  }, [setRagPinnedResults])
  const clearHistoryContext = React.useCallback(() => {
    clearChat()
  }, [clearChat])
  const trimLargestContextContributor = React.useCallback(() => {
    if (!largestContextContributor) return
    if (largestContextContributor.id === "character") {
      setOpenActorSettings(true)
      return
    }
    if (largestContextContributor.id === "prompt") {
      clearPromptContext()
      return
    }
    if (largestContextContributor.id === "pinned") {
      clearPinnedSourceContext()
      return
    }
    if (largestContextContributor.id === "history") {
      clearHistoryContext()
    }
  }, [
    clearHistoryContext,
    clearPinnedSourceContext,
    clearPromptContext,
    largestContextContributor
  ])
  const insertSummaryCheckpointPrompt = React.useCallback(() => {
    const checkpointPrompt = buildConversationSummaryCheckpointPrompt(messages, {
      maxRecentMessages: 10
    })
    setMessageValue(checkpointPrompt, {
      collapseLarge: true,
      forceCollapse: true
    })
    textAreaFocus()
  }, [messages, setMessageValue, textAreaFocus])

  const {
    imageBackendDefault: imageBackendDefaultTrimmed,
    setImageBackendDefault,
    imageBackendOptions,
    imageBackendLabel,
    imageBackendActiveKey,
    imageBackendMenuItems,
    imageBackendBadgeLabel
  } = useImageBackend({ imageModels })

  const modelSelectButton = (
    <Dropdown
      open={modelDropdownOpen}
      onOpenChange={(open) => {
        setModelDropdownOpen(open)
        if (!open) {
          setModelSearchQuery("")
        }
      }}
      menu={{
        items: modelDropdownMenuItems,
        className: "no-scrollbar",
        activeKey: selectedModel ?? undefined
      }}
      popupRender={(menu) => (
        <div className="bg-surface rounded-lg shadow-lg border border-border">
          <div className="p-2 border-b border-border flex items-center gap-2">
            <Input
              size="small"
              placeholder={t("playground:composer.modelSearchPlaceholder", "Search models")}
              value={modelSearchQuery}
              allowClear
              className="flex-1"
              onChange={(event) => setModelSearchQuery(event.target.value)}
              onKeyDown={(event) => event.stopPropagation()}
            />
            <Select
              size="small"
              value={modelSortMode}
              onChange={(value) => setModelSortMode(value as ModelSortMode)}
              options={[
                { value: "favorites", label: t("playground:composer.sort.favorites", "Favorites") },
                { value: "az", label: t("playground:composer.sort.az", "A-Z") },
                { value: "provider", label: t("playground:composer.sort.provider", "Provider") },
                { value: "localFirst", label: t("playground:composer.sort.localFirst", "Local-first") }
              ]}
              className="min-w-[120px]"
              onKeyDown={(event) => event.stopPropagation()}
            />
          </div>
          <div className="max-h-[400px] overflow-y-auto no-scrollbar">
            {menu}
          </div>
          <div className="p-2 border-t border-border">
            <Link
              to="/docs/models"
              className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors"
              onClick={() => setModelDropdownOpen(false)}
            >
              <HelpCircle className="h-3.5 w-3.5" />
              <span>{t("playground:composer.helpMeChoose", "Help me choose a model")}</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      )}
      trigger={["click"]}
      placement="topLeft"
    >
      <Tooltip title={modelSelectorWarning ? t("playground:composer.selectModelTooltip", "Click to select a model") : apiModelLabel} placement="top">
        <button
          type="button"
          title={apiModelLabel}
          aria-label={apiModelLabel}
          aria-haspopup="listbox"
          aria-expanded={modelDropdownOpen}
          data-testid="model-selector"
          className={`inline-flex min-w-0 items-center gap-1 rounded-full border px-2 min-h-[44px] text-[10px] cursor-pointer transition-colors ${
            modelSelectorWarning
              ? "border-warn/50 bg-warn/10 text-warn hover:bg-warn/20"
              : "border-border bg-surface hover:bg-surface-hover"
          }`}
        >
          <ProviderIcons
            provider={resolvedProviderKey}
            className={`h-3 w-3 ${modelSelectorWarning ? "text-warn" : "text-text-subtle"}`}
          />
          <span className="truncate max-w-[120px]">
            {apiModelLabel}
          </span>
          <span
            className={`rounded-full px-1.5 py-0.5 text-[9px] ${
              !isConnectionReady || connectionUxState === "connected_degraded"
                ? "bg-warn/10 text-warn"
                : "bg-success/10 text-success"
            }`}
            title={t(
              "playground:composer.providerStatusTooltip",
              "Provider status"
            ) as string}
          >
            {connectionStatusLabel}
          </span>
        </button>
      </Tooltip>
    </Dropdown>
  )

  const modelUsageBadge = wrapComposerProfile(
    "token-progress",
    <TokenProgressBar
      conversationTokens={conversationTokenCount}
      draftTokens={draftTokenCount}
      maxTokens={resolvedMaxContext}
      modelLabel={isProMode ? apiModelLabel : undefined}
      compact={!isProMode}
      onClick={openContextWindowModal}
    />
  )
  const compareControl = (
    <CompareToggle
      featureEnabled={compareFeatureEnabled}
      active={compareModeActive}
      onToggle={toggleCompareMode}
      selectedModels={compareSelectedModels}
      availableModels={availableCompareModels}
      maxModels={compareMaxModels}
      onAddModel={handleAddCompareModel}
      onRemoveModel={handleRemoveCompareModel}
      onOpenSettings={() => setOpenModelSettings(true)}
    />
  )
  const imageProviderControl = (
    <Dropdown
      menu={{
        items: imageBackendMenuItems,
        activeKey: imageBackendActiveKey
      }}
      trigger={["hover", "click"]}
      placement="topRight"
    >
      <button
        type="button"
        title={t(
          "playground:imageBackend.tooltip",
          "Default image provider for /generate-image."
        )}
        aria-label={imageBackendBadgeLabel}
        className="flex w-full items-center justify-between rounded-md px-2 py-1 text-sm text-text transition hover:bg-surface2"
      >
        <span className="flex min-w-0 items-center gap-2">
          <ImageIcon className="h-4 w-4 text-text-subtle" />
          <span className="truncate">
            {t("playground:imageBackend.menuLabel", "Default image provider")}
          </span>
        </span>
        <span className="flex min-w-0 items-center gap-1 text-xs text-text-muted">
          <span className="truncate max-w-[140px]">
            {imageBackendDefaultTrimmed
              ? imageBackendLabel
              : t("playground:imageBackend.none", "None")}
          </span>
          <ChevronRight className="h-3.5 w-3.5" />
        </span>
      </button>
    </Dropdown>
  )

  // Allow other components (e.g., connection card) to request focus
  React.useEffect(() => {
    const handler = () => {
      if (document.visibilityState === 'visible') {
        textAreaFocus()
      }
    }
    window.addEventListener('tldw:focus-composer', handler)
    return () => window.removeEventListener('tldw:focus-composer', handler)
  }, [textAreaFocus])

  // Allow other components (e.g., empty state) to set the composer message
  React.useEffect(() => {
    const handler = (event: CustomEvent<{ message: string }>) => {
      if (event.detail?.message) {
        form.setFieldValue("message", event.detail.message)
      }
    }
    window.addEventListener('tldw:set-composer-message', handler as EventListener)
    return () => window.removeEventListener('tldw:set-composer-message', handler as EventListener)
  }, [form])

  React.useEffect(() => {
    const handleToggleCompareMode = () => {
      toggleCompareMode()
    }
    const handleToggleModeLauncher = () => {
      setModeLauncherOpen((prev) => !prev)
    }

    window.addEventListener("tldw:toggle-compare-mode", handleToggleCompareMode)
    window.addEventListener("tldw:toggle-mode-launcher", handleToggleModeLauncher)
    return () => {
      window.removeEventListener(
        "tldw:toggle-compare-mode",
        handleToggleCompareMode
      )
      window.removeEventListener(
        "tldw:toggle-mode-launcher",
        handleToggleModeLauncher
      )
    }
  }, [toggleCompareMode])

  const applyDiscussMediaPayload = React.useCallback(
    (
      rawPayload: unknown,
      options?: {
        clearAfterUse?: boolean
      }
    ) => {
      const payload = normalizeMediaChatHandoffPayload(rawPayload)
      if (!payload) {
        if (options?.clearAfterUse) {
          void clearSetting(DISCUSS_MEDIA_PROMPT_SETTING)
        }
        return
      }
      if (options?.clearAfterUse) {
        void clearSetting(DISCUSS_MEDIA_PROMPT_SETTING)
      }
      const mode = getMediaChatHandoffMode(payload)
      if (mode === "rag_media") {
        const mediaId = parseMediaIdAsNumber(payload)
        if (mediaId != null) {
          setChatMode("rag")
          setRagMediaIds([mediaId])
        }
      } else {
        setChatMode("normal")
        setRagMediaIds(null)
      }
      const hint = buildDiscussMediaHint(payload)
      if (!hint) return
      setMessageValue(hint, { collapseLarge: true, forceCollapse: true })
      textAreaFocus()
    },
    [setChatMode, setMessageValue, setRagMediaIds, textAreaFocus]
  )

  // Seed composer when a media item requests discussion (e.g., from Quick ingest or Review page)
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const payload = await getSetting(DISCUSS_MEDIA_PROMPT_SETTING)
      if (cancelled || !payload) return
      applyDiscussMediaPayload(payload, { clearAfterUse: true })
    })()
    return () => {
      cancelled = true
    }
  }, [applyDiscussMediaPayload])

  React.useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail
      applyDiscussMediaPayload(detail)
    }
    window.addEventListener("tldw:discuss-media", handler as any)
    return () => {
      window.removeEventListener("tldw:discuss-media", handler as any)
    }
  }, [applyDiscussMediaPayload])

  const applyDiscussWatchlistPayload = React.useCallback(
    (
      rawPayload: unknown,
      options?: { clearAfterUse?: boolean }
    ) => {
      const payload = normalizeWatchlistChatHandoffPayload(rawPayload)
      if (!payload) {
        if (options?.clearAfterUse) {
          void clearSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
        }
        return
      }
      if (options?.clearAfterUse) {
        void clearSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
      }
      setChatMode("normal")
      setRagMediaIds(null)
      const hint = buildWatchlistChatHint(payload)
      if (!hint) return
      setMessageValue(hint, { collapseLarge: true, forceCollapse: true })
      textAreaFocus()
    },
    [setChatMode, setMessageValue, setRagMediaIds, textAreaFocus]
  )

  // Seed composer when a watchlist item requests discussion
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const payload = await getSetting(DISCUSS_WATCHLIST_PROMPT_SETTING)
      if (cancelled || !payload) return
      applyDiscussWatchlistPayload(payload, { clearAfterUse: true })
    })()
    return () => {
      cancelled = true
    }
  }, [applyDiscussWatchlistPayload])

  React.useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail
      applyDiscussWatchlistPayload(detail)
    }
    window.addEventListener("tldw:discuss-watchlist", handler as any)
    return () => {
      window.removeEventListener("tldw:discuss-watchlist", handler as any)
    }
  }, [applyDiscussWatchlistPayload])

  React.useEffect(() => {
    textAreaFocus()
  }, [textAreaFocus])

  React.useEffect(() => {
    // Apply global default when the preference changes, but do not override per-chat toggles.
    if (defaultInternetSearchOn) {
      setWebSearch(true)
    }
  }, [defaultInternetSearchOn, setWebSearch])

  React.useEffect(() => {
    if (isConnectionReady) {
      setShowConnectBanner(false)
    }
  }, [isConnectionReady])

  const notifyImageAttachmentDisabled = React.useCallback(() => {
    notificationApi.warning({
      message: t(
        "playground:attachments.imageDisabledTitle",
        "Image attachments disabled"
      ),
      description: t(
        "playground:attachments.imageDisabledBody",
        "Disable Knowledge Search to attach images."
      )
    })
  }, [notificationApi, t])

  const attachments = usePlaygroundAttachments({
    chatMode,
    setFieldValue: form.setFieldValue,
    handleFileUpload,
    notifyImageAttachmentDisabled
  })
  const {
    inputRef,
    fileInputRef,
    onFileInputChange,
    onInputChange,
    handleImageUpload,
    handleDocumentUpload,
    useDroppedFiles
  } = attachments

  // Process dropped files
  useDroppedFiles(droppedFiles)

  const handlePaste = React.useCallback(
    async (e: React.ClipboardEvent) => {
      if (e.clipboardData.files.length > 0) {
        try {
          await onInputChange(e.clipboardData.files[0])
        } catch (error) {
          console.error("Failed to handle pasted file:", error)
        }
        return
      }

      const pastedText = e.clipboardData.getData("text/plain")
      if (!pastedText) return

      if (
        pasteLargeTextAsFile &&
        pastedText.length > PASTED_TEXT_CHAR_LIMIT
      ) {
        e.preventDefault()
        const blob = new Blob([pastedText], { type: "text/plain" })
        const file = new File([blob], `pasted-text-${Date.now()}.txt`, {
          type: "text/plain"
        })

        await handleFileUpload(file)
        return
      }

      if (isMessageCollapsed && collapsedRange) {
        e.preventDefault()
        const currentValue = form.values.message || ""
        const meta = getCollapsedDisplayMeta(currentValue, collapsedRange)
        const textarea = textareaRef.current
        const rawStart = textarea?.selectionStart ?? meta.labelEnd
        const rawEnd = textarea?.selectionEnd ?? rawStart
        const displayStart = Math.min(rawStart, rawEnd)
        const displayEnd = Math.max(rawStart, rawEnd)
        const hasSelection = displayStart !== displayEnd
        const selectionTouchesLabel =
          displayStart < meta.labelEnd && displayEnd > meta.labelStart
        if (hasSelection) {
          const startPrefer =
            displayStart > meta.labelStart && displayStart < meta.labelEnd
              ? "before"
              : undefined
          const endPrefer =
            displayEnd > meta.labelStart && displayEnd < meta.labelEnd
              ? "after"
              : undefined
          let editStart = getMessageCaretFromDisplay(displayStart, meta, {
            prefer: startPrefer
          })
          let editEnd = getMessageCaretFromDisplay(displayEnd, meta, {
            prefer: endPrefer
          })
          if (editStart > editEnd) {
            ;[editStart, editEnd] = [editEnd, editStart]
          }
          if (selectionTouchesLabel) {
            editStart = Math.min(editStart, meta.rangeStart)
            editEnd = Math.max(editEnd, meta.rangeEnd)
          }
          replaceCollapsedRange(
            currentValue,
            meta,
            editStart,
            editEnd,
            pastedText
          )
          return
        }
        const caretPrefer =
          rawStart > meta.labelStart && rawStart < meta.labelEnd
            ? (pendingCaretRef.current !== null &&
              pendingCaretRef.current <= meta.rangeStart
                ? "before"
                : "after")
            : undefined
        let caret = getMessageCaretFromDisplay(rawStart, meta, {
          prefer: caretPrefer
        })
        if (caret > meta.rangeStart && caret < meta.rangeEnd) {
          caret = meta.rangeEnd
        }
        const insertAt =
          caret <= meta.rangeStart
            ? caret
            : caret >= meta.rangeEnd
              ? caret
              : meta.rangeEnd
        replaceCollapsedRange(currentValue, meta, insertAt, insertAt, pastedText)
        return
      }

      const currentValue = form.values.message || ""
      const textarea = textareaRef.current
      const selectionStart = textarea?.selectionStart ?? currentValue.length
      const selectionEnd = textarea?.selectionEnd ?? selectionStart
      const nextValue =
        currentValue.slice(0, selectionStart) +
        pastedText +
        currentValue.slice(selectionEnd)

      if (nextValue.length > PASTED_TEXT_CHAR_LIMIT) {
        e.preventDefault()
        const blockRange = {
          start: selectionStart,
          end: selectionStart + pastedText.length
        }
        pendingCaretRef.current = blockRange.end
        pendingCollapsedStateRef.current = {
          message: nextValue,
          range: blockRange,
          caret: blockRange.end
        }
        setMessageValue(nextValue, {
          collapseLarge: true,
          forceCollapse: true,
          collapsedRange: blockRange
        })
      }
    },
    [
      collapsedRange,
      form.values.message,
      handleFileUpload,
      isMessageCollapsed,
      getCollapsedDisplayMeta,
      getMessageCaretFromDisplay,
      onInputChange,
      pasteLargeTextAsFile,
      replaceCollapsedRange,
      setMessageValue,
      textareaRef
    ]
  )
  const handleDisconnectedFocus = React.useCallback(() => {
    if (!isConnectionReady && !hasShownConnectBanner) {
      setShowConnectBanner(true)
      setHasShownConnectBanner(true)
    }
  }, [hasShownConnectBanner, isConnectionReady])

  const handleTextareaKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (handleCollapsedKeyDown(e)) return
    handleKeyDown(e)
  }

  const handleTextareaFocus = React.useCallback(() => {
    handleDisconnectedFocus()
    if (!isMessageCollapsed) return
    const wasPointer = pointerDownRef.current
    pointerDownRef.current = false
    if (wasPointer) return
    const textarea = textareaRef.current
    if (pendingCaretRef.current === null && textarea) {
      lastDisplaySelectionRef.current = {
        start: textarea.selectionStart ?? 0,
        end: textarea.selectionEnd ?? textarea.selectionStart ?? 0
      }
    }
    syncCollapsedCaret()
  }, [handleDisconnectedFocus, isMessageCollapsed, syncCollapsedCaret, textareaRef])

  const handleMentionSelect = React.useCallback(
    (tab: any) =>
      insertMention(tab, form.values.message, (value: string) =>
        form.setFieldValue("message", value)
      ),
    [insertMention, form]
  )

  const handleMentionRefetch = React.useCallback(async () => {
    await reloadTabs()
  }, [reloadTabs])

  const handleKnowledgeInsert = React.useCallback(
    (text: string) => {
      const current = textareaRef.current?.value || ""
      const next = current ? `${current}\n\n${text}` : text
      setMessageValue(next, { collapseLarge: true })
      textAreaFocus()
    },
    [setMessageValue, textAreaFocus, textareaRef]
  )
  const handleKnowledgePanelOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      setContextToolsOpen(nextOpen)
    },
    []
  )
  const handleKnowledgeRemoveImage = React.useCallback(() => {
    form.setFieldValue("image", "")
  }, [form.setFieldValue])
  const handleKnowledgeAddFile = React.useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const voiceChatHook = usePlaygroundVoiceChat({
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
    stopSpeechRecognition: () => {},
    notificationApi,
    isSending,
    isListening: false,
    isServerDictating: false,
    t
  })
  const {
    isListening,
    browserSupportsSpeechRecognition,
    isServerDictating,
    speechAvailable,
    speechUsesServer,
    voiceChatStatusLabel,
    speechTooltipText,
    handleVoiceChatToggle,
    handleDictationToggle,
    stopListening
  } = voiceChatHook
  const { sendWhenEnter, setSendWhenEnter } = useWebUI()

  React.useEffect(() => {
    if (!selectedQuickPrompt) {
      return
    }

    const currentMessage = form.values.message || ""
    const promptText = selectedQuickPrompt

    const applyOverwrite = () => {
      const word = getVariable(promptText)
      setMessageValue(promptText, { collapseLarge: true })
      if (word) {
        textareaRef.current?.focus()
        const interval = setTimeout(() => {
          textareaRef.current?.setSelectionRange(word.start, word.end)
          setSelectedQuickPrompt(null)
        }, 100)
        return () => {
          clearInterval(interval)
        }
      }
      setSelectedQuickPrompt(null)
      return
    }

    const applyAppend = () => {
      const next =
        currentMessage.trim().length > 0
          ? `${currentMessage}\n\n${promptText}`
          : promptText
      setMessageValue(next, { collapseLarge: true })
      setSelectedQuickPrompt(null)
    }

    if (!currentMessage.trim()) {
      applyOverwrite()
      return
    }

    Modal.confirm({
      title: t("option:promptInsert.confirmTitle", {
        defaultValue: "Use prompt in chat?"
      }),
      content: t("option:promptInsert.confirmDescription", {
        defaultValue:
          "Your message already has text. Do you want to overwrite it with this prompt or append the prompt below it?"
      }),
      okText: t("option:promptInsert.overwrite", {
        defaultValue: "Overwrite message"
      }),
      cancelText: t("option:promptInsert.append", {
        defaultValue: "Append"
      }),
      closable: false,
      maskClosable: false,
      onOk: () => {
        applyOverwrite()
      },
      onCancel: () => {
        applyAppend()
      }
    })
  }, [
    selectedQuickPrompt,
    form.values.message,
    setMessageValue,
    setSelectedQuickPrompt,
    t,
    textareaRef
  ])

  const queryClient = useQueryClient()
  const invalidateServerChatHistory = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
  }, [queryClient])

  const { mutateAsync: sendMessage } = useMutation({
    mutationFn: onSubmit,
    onSuccess: () => {
      void trackOnboardingChatSubmitSuccess(
        typeof window !== "undefined" ? window.location.pathname : "/chat"
      )
      textAreaFocus()
      queryClient.invalidateQueries({
        queryKey: ["fetchChatHistory"]
      })
    },
    onError: (error) => {
      textAreaFocus()
    }
  })

  const queueMgmt = usePlaygroundQueueManagement({
    composerModels,
    isConnectionReady,
    isSending,
    selectedModel,
    chatMode,
    webSearch,
    compareMode,
    compareModeActive,
    compareSelectedModels,
    selectedSystemPrompt,
    selectedQuickPrompt,
    toolChoice,
    useOCR,
    selectedDocuments,
    uploadedFiles,
    contextFiles,
    documentContext,
    queuedMessages,
    setQueuedMessages,
    historyId,
    serverChatId,
    conversationTokenCount,
    resolvedMaxContext,
    estimateTokensForText: estimateTokensForText as any,
    characterContextTokenEstimate,
    pinnedSourceTokenEstimate,
    currentContextSnapshot,
    setLastSubmittedContext,
    setSelectedModel,
    setChatMode,
    setWebSearch,
    setCompareMode,
    setCompareSelectedModels,
    setSelectedSystemPrompt,
    setSelectedQuickPrompt,
    setToolChoice,
    setUseOCR,
    compareModelsSupportCapability,
    sendMessage,
    stopStreamingRequest,
    form,
    clearSelectedDocuments,
    clearUploadedFiles,
    textAreaFocus,
    notificationApi,
    t
  })
  const {
    availableChatModelIds,
    isQueuedDispatchBlockedByComposerState,
    queuedRequestActions,
    queueSubmission,
    cancelCurrentAndRunDisabledReason,
    handleRunQueuedRequest,
    handleRunNextQueuedRequest,
    validateSelectedChatModelsAvailability
  } = queueMgmt

  const handleToggleWebSearch = React.useCallback(() => {
    setWebSearch(!webSearch)
  }, [setWebSearch, webSearch])
  const handleOpenModelSettings = React.useCallback(() => {
    setOpenModelSettings(true)
  }, [setOpenModelSettings])
  const {
    showSlashMenu,
    slashActiveIndex,
    setSlashActiveIndex,
    filteredSlashCommands,
    resolveSubmissionIntent,
    activeImageCommand,
    handleSlashCommandSelect: slashHandleSelect
  } = useSlashCommands({
    chatMode,
    setChatMode,
    webSearch,
    setWebSearch,
    handleImageUpload,
    imageBackendDefaultTrimmed,
    imageBackendLabel,
    setOpenModelSettings,
    currentMessage: form.values.message
  })

  const handleSlashCommandSelect = React.useCallback(
    (command: SlashCommandItem) => {
      slashHandleSelect(command, form.setFieldValue.bind(form), textareaRef)
    },
    [slashHandleSelect, form, textareaRef]
  )

  const { submitForm, submitFormRef } = usePlaygroundSubmit({
    form,
    isSending,
    isConnectionReady,
    webSearch,
    compareModeActive,
    compareSelectedModels,
    selectedModel,
    fileRetrievalEnabled,
    ragPinnedResults,
    selectedDocuments,
    uploadedFiles,
    currentContextSnapshot,
    conversationTokenCount,
    characterContextTokenEstimate,
    pinnedSourceTokenEstimate,
    resolvedMaxContext,
    jsonMode: Boolean(currentChatModelSettings.jsonMode),
    sendMessage,
    clearSelectedDocuments,
    clearUploadedFiles,
    textAreaFocus,
    setLastSubmittedContext,
    estimateTokensForText: estimateTokensForText as any,
    resolveSubmissionIntent,
    queueSubmission,
    validateSelectedChatModelsAvailability,
    compareModelsSupportCapability,
    notificationApi,
    t
  })

  const handleKnowledgeAsk = React.useCallback(
    (text: string, options?: { ignorePinnedResults?: boolean }) => {
      const trimmed = text.trim()
      if (!trimmed) return
      setMessageValue(trimmed, { collapseLarge: true })
      queueMicrotask(() =>
        submitFormRef.current({
          ignorePinnedResults: options?.ignorePinnedResults
        })
      )
    },
    [setMessageValue, submitFormRef]
  )

  const persistence = usePlaygroundPersistence({
    isFireFoxPrivateMode,
    isConnectionReady,
    temporaryChat,
    setTemporaryChat,
    serverChatId,
    setServerChatId,
    serverChatState,
    setServerChatState,
    serverChatSource,
    setServerChatSource,
    setServerChatVersion,
    history,
    clearChat,
    selectedCharacter,
    serverPersistenceHintSeen,
    setServerPersistenceHintSeen,
    invalidateServerChatHistory,
    navigate,
    notificationApi,
    t
  })
  const {
    persistenceTooltip,
    focusConnectionCard,
    getPersistenceModeLabel,
    privateChatLocked,
    showServerPersistenceHint,
    handleToggleTemporaryChat,
    handleSaveChatToServer,
    persistChatMetadata,
    handleDismissServerPersistenceHint
  } = persistence

  const handleClearContext = React.useCallback(() => {
    // Only show confirmation if there's history to clear
    if (history.length === 0) {
      return
    }

    Modal.confirm({
      title: t(
        "playground:composer.clearContextConfirmTitle",
        "Clear conversation?"
      ),
      content: t(
        "playground:composer.clearContextConfirmContent",
        "This will remove all messages from the current conversation. This action cannot be undone."
      ),
      okText: t("common:confirm", "Confirm"),
      okButtonProps: { danger: true },
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => {
        setHistory([])
        notificationApi.success({
          message: t(
            "playground:composer.clearContextSuccess",
            "Conversation cleared"
          ),
          duration: 2
        })
      }
    })
  }, [history.length, notificationApi, setHistory, t])

  const requestKnowledgePanelTab = React.useCallback((tab: KnowledgeTab) => {
    setKnowledgePanelTab(tab)
    setKnowledgePanelTabRequestId((id) => id + 1)
  }, [])

  const openKnowledgePanel = React.useCallback(
    (tab: KnowledgeTab) => {
      requestKnowledgePanelTab(tab)
      setContextToolsOpen(true)
    },
    [requestKnowledgePanelTab, setContextToolsOpen]
  )

  const toggleKnowledgePanel = React.useCallback(
    (tab: KnowledgeTab = "search") => {
      const nextOpen = !contextToolsOpen
      if (nextOpen) {
        requestKnowledgePanelTab(tab)
      }
      setContextToolsOpen(nextOpen)
    },
    [contextToolsOpen, requestKnowledgePanelTab, setContextToolsOpen]
  )

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: KnowledgeTab }>).detail
      const tab = detail?.tab === "context" ? "context" : "search"
      openKnowledgePanel(tab)
      setModeAnnouncement(
        t("playground:starter.noticeKnowledge", "Opened Search & Context panel.")
      )
    }
    window.addEventListener(
      "tldw:open-knowledge-panel",
      handler as EventListener
    )
    return () => {
      window.removeEventListener(
        "tldw:open-knowledge-panel",
        handler as EventListener
      )
    }
  }, [openKnowledgePanel, t])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ mode?: string; prompt?: string }>)
        .detail
      const mode = String(detail?.mode || "").trim().toLowerCase()
      if (mode === "compare") {
        if (!compareFeatureEnabled) {
          notificationApi.warning({
            message: t("playground:starter.compareUnavailable", "Compare mode unavailable")
          })
          return
        }
        setCompareMode(true)
        if (selectedModel && compareSelectedModels.length === 0) {
          setCompareSelectedModels([selectedModel])
        }
        setModeAnnouncement(
          t(
            "playground:starter.noticeCompare",
            "Compare mode enabled. Select models and send your first prompt."
          )
        )
        textAreaFocus()
        return
      }
      if (mode === "character") {
        setOpenActorSettings(true)
        setModeAnnouncement(
          t(
            "playground:starter.noticeCharacter",
            "Character mode starter selected. Choose a character before sending."
          )
        )
        return
      }
      if (mode === "rag" || mode === "knowledge") {
        setChatMode("rag")
        openKnowledgePanel("search")
        setModeAnnouncement(
          t(
            "playground:starter.noticeRag",
            "Knowledge starter selected. Search and pin sources before sending."
          )
        )
        if (detail?.prompt) {
          form.setFieldValue("message", String(detail.prompt))
        }
        textAreaFocus()
        return
      }
      if (detail?.prompt) {
        form.setFieldValue("message", String(detail.prompt))
      }
      setModeAnnouncement(
        t(
          "playground:starter.noticeGeneral",
          "General chat starter selected."
        )
      )
      textAreaFocus()
    }
    window.addEventListener("tldw:playground-starter", handler as EventListener)
    return () => {
      window.removeEventListener(
        "tldw:playground-starter",
        handler as EventListener
      )
    }
  }, [
    compareFeatureEnabled,
    compareSelectedModels.length,
    form,
    notificationApi,
    openKnowledgePanel,
    selectedModel,
    setChatMode,
    setCompareMode,
    setCompareSelectedModels,
    t,
    textAreaFocus
  ])

  const voiceChatSettingsFields = (
    <>
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.modelLabel", "Voice model")}
        </span>
        <Select
          size="small"
          value={voiceChatModel || ""}
          options={voiceChatModelOptions}
          onChange={(value) => setVoiceChatModel(value)}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.pauseLabel", "Auto-send pause (ms)")}
        </span>
        <InputNumber
          size="small"
          min={200}
          max={5000}
          value={voiceChatPauseMs}
          onChange={(value) =>
            setVoiceChatPauseMs(typeof value === "number" ? value : 900)
          }
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.triggerLabel", "Trigger phrases")}
        </span>
        <Input
          size="small"
          placeholder={t(
            "playground:voiceChat.triggerPlaceholder",
            "e.g. send it, over"
          )}
          value={voiceChatTriggerInput}
          onChange={(e) => {
            const value = e.target.value
            setVoiceChatTriggerInput(value)
            const parsed = value
              .split(",")
              .map((entry) => entry.trim())
              .filter(Boolean)
            setVoiceChatTriggerPhrases(parsed)
          }}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.ttsModeLabel", "Response audio")}
        </span>
        <Radio.Group
          size="small"
          optionType="button"
          value={voiceChatTtsMode}
          onChange={(e) => setVoiceChatTtsMode(e.target.value)}
        >
          <Radio.Button value="stream">
            {t("playground:voiceChat.ttsModeStream", "Stream")}
          </Radio.Button>
          <Radio.Button value="full">
            {t("playground:voiceChat.ttsModeFull", "Full")}
          </Radio.Button>
        </Radio.Group>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.autoResume", "Continue listening after response")}
        </span>
        <Switch
          size="small"
          checked={voiceChatAutoResume}
          onChange={(checked) => setVoiceChatAutoResume(checked)}
        />
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-text-muted">
          {t("playground:voiceChat.bargeIn", "Interrupt while speaking")}
        </span>
        <Switch
          size="small"
          checked={voiceChatBargeIn}
          onChange={(checked) => setVoiceChatBargeIn(checked)}
        />
      </div>
    </>
  )

  React.useEffect(() => {
    if (contextToolsOpen) {
      reloadTabs()
    }
  }, [contextToolsOpen, reloadTabs])

  // State for collapsible advanced section in tools popover
  const [advancedToolsExpanded, setAdvancedToolsExpanded] = React.useState(isProMode)

  const imageGen = usePlaygroundImageGen({
    imageBackendDefaultTrimmed: imageBackendDefaultTrimmed,
    imageBackendOptions,
    imageEventSyncChatMode,
    imageEventSyncGlobalDefault,
    updateChatSettings,
    setImageEventSyncGlobalDefault: setImageEventSyncGlobalDefault as any,
    messages: messages as any,
    selectedCharacterName: selectedCharacter?.name ?? null,
    selectedModel,
    currentApiProvider: currentChatModelSettings.apiProvider,
    formMessage: form.values.message || "",
    sendMessage,
    textAreaFocus,
    notificationApi,
    t,
    setToolsPopoverOpen
  })
  const {
    imageGenerateModalOpen, setImageGenerateModalOpen,
    imageGenerateBackend, setImageGenerateBackend,
    imageGeneratePrompt, setImageGeneratePrompt,
    imageGeneratePromptMode, setImageGeneratePromptMode,
    imageGenerateFormat, setImageGenerateFormat,
    imageGenerateNegativePrompt, setImageGenerateNegativePrompt,
    imageGenerateWidth, setImageGenerateWidth,
    imageGenerateHeight, setImageGenerateHeight,
    imageGenerateSteps, setImageGenerateSteps,
    imageGenerateCfgScale, setImageGenerateCfgScale,
    imageGenerateSeed, setImageGenerateSeed,
    imageGenerateSampler, setImageGenerateSampler,
    imageGenerateModel, setImageGenerateModel,
    imageGenerateExtraParams, setImageGenerateExtraParams,
    imageGenerateSyncPolicy, setImageGenerateSyncPolicy,
    imagePromptContextBreakdown,
    imagePromptRefineSubmitting,
    imagePromptRefineBaseline,
    imagePromptRefineCandidate,
    imagePromptRefineModel,
    imagePromptRefineLatencyMs,
    imagePromptRefineDiff,
    imageGenerateRefineMetadata,
    imageGenerateSubmitting,
    imagePromptStrategies,
    imageGenerationCharacterMood,
    imageGenerateBackendOptions,
    imageGenerateBusy,
    imageEventSyncBaselineMode,
    imageGenerateResolvedSyncMode,
    clearImagePromptRefineState,
    hydrateImageGenerateSettings,
    openImageGenerateModal,
    handleCreateImagePromptDraft,
    handleRefineImagePromptDraft,
    applyRefinedImagePromptCandidate,
    rejectRefinedImagePromptCandidate,
    submitImageGenerateModal,
    normalizeImageGenerationEventSyncMode: normalizeImageGenSyncMode,
    normalizeImageGenerationEventSyncPolicy: normalizeImageGenSyncPolicy
  } = imageGen
  const { mcpSettingsOpen, setMcpSettingsOpen } = mcpCtrl
  React.useEffect(() => {
    setOptionalPanelVisible("mcp-tools", mcpSettingsOpen)
    if (mcpSettingsOpen || toolChoice !== "none") {
      markOptionalPanelEngaged("mcp-tools")
    }

    return () => {
      setOptionalPanelVisible("mcp-tools", false)
    }
  }, [
    markOptionalPanelEngaged,
    mcpSettingsOpen,
    setOptionalPanelVisible,
    toolChoice
  ])

  // Image generation logic is now in usePlaygroundImageGen hook above.

  // handleCreateImagePromptDraft - extracted to usePlaygroundImageGen

  const rawPreview = usePlaygroundRawPreview({
    composerModels,
    selectedModel,
    compareModeActive,
    compareSelectedModels,
    compareMaxModels,
    currentChatModelSettings,
    history,
    systemPrompt,
    hasMcp,
    mcpHealthState,
    mcpTools,
    toolChoice,
    temporaryChat,
    serverChatId,
    serverChatState,
    serverChatSource,
    selectedCharacter,
    messageSteeringMode,
    messageSteeringForceNarrate,
    ragMediaIds,
    selectedKnowledge: selectedKnowledge as any,
    fileRetrievalEnabled,
    contextFiles,
    documentContext,
    selectedDocuments,
    imageBackendDefaultTrimmed: imageBackendDefaultTrimmed,
    resolveSubmissionIntent,
    formImage: form.values.image || "",
    formMessage: form.values.message || "",
    notificationApi,
    t,
    setToolsPopoverOpen
  })
  const {
    rawRequestModalOpen,
    setRawRequestModalOpen,
    rawRequestSnapshot,
    rawRequestJson,
    refreshRawRequestSnapshot,
    openRawRequestModal,
    copyRawRequestJson
  } = rawPreview

  const navigateToWebSearchSettings = React.useCallback(() => {
    navigate("/settings")
  }, [navigate])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isFirefoxTarget) {
      if (e.key === "Process" || e.key === "229") return
    }

    if (showSlashMenu) {
      if (e.key === "ArrowDown" && filteredSlashCommands.length > 0) {
        e.preventDefault()
        setSlashActiveIndex((prev) =>
          prev + 1 >= filteredSlashCommands.length ? 0 : prev + 1
        )
        return
      }
      if (e.key === "ArrowUp" && filteredSlashCommands.length > 0) {
        e.preventDefault()
        setSlashActiveIndex((prev) =>
          prev <= 0 ? filteredSlashCommands.length - 1 : prev - 1
        )
        return
      }
      if (
        (e.key === "Enter" || (e.key === "Tab" && !e.shiftKey)) &&
        filteredSlashCommands.length > 0
      ) {
        e.preventDefault()
        const command = filteredSlashCommands[slashActiveIndex]
        if (command) {
          handleSlashCommandSelect(command)
        }
        return
      }
      if (e.key === "Escape") {
        e.preventDefault()
        form.setFieldValue(
          "message",
          form.values.message.replace(/^\s*\//, "")
        )
        return
      }
    }

    if (
      showMentions &&
      (e.key === "ArrowDown" ||
        e.key === "ArrowUp" ||
        e.key === "Enter" ||
        e.key === "Escape")
    ) {
      return
    }

    if (!isConnectionReady) {
      if (e.key === "Enter") {
        e.preventDefault()
      }
      return
    }

    if (
      handleChatInputKeyDown({
        e,
        sendWhenEnter,
        typing,
        isSending: false
      })
    ) {
      e.preventDefault()
      stopListening()
      submitForm()
    }
  }

  const handleCollapsedKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (!isMessageCollapsed || !collapsedRange) return false

      const shouldSend = handleChatInputKeyDown({
        e,
        sendWhenEnter,
        typing,
        isSending: false
      })
      if (shouldSend) return false

      const currentValue = form.values.message || ""
      const meta = getCollapsedDisplayMeta(currentValue, collapsedRange)
      const textarea = textareaRef.current
      const rawStart = textarea?.selectionStart ?? meta.labelEnd
      const rawEnd = textarea?.selectionEnd ?? rawStart
      const displayStart = Math.min(rawStart, rawEnd)
      const displayEnd = Math.max(rawStart, rawEnd)
      const hasSelection = displayStart !== displayEnd
      const selectionTouchesLabel =
        displayStart < meta.labelEnd && displayEnd > meta.labelStart
      const startPrefer =
        displayStart > meta.labelStart && displayStart < meta.labelEnd
          ? "before"
          : undefined
      const endPrefer =
        displayEnd > meta.labelStart && displayEnd < meta.labelEnd
          ? "after"
          : undefined
      let selectionStart = getMessageCaretFromDisplay(displayStart, meta, {
        prefer: startPrefer
      })
      let selectionEnd = getMessageCaretFromDisplay(displayEnd, meta, {
        prefer: endPrefer
      })
      if (selectionStart > selectionEnd) {
        ;[selectionStart, selectionEnd] = [selectionEnd, selectionStart]
      }
      if (selectionTouchesLabel) {
        selectionStart = Math.min(selectionStart, meta.rangeStart)
        selectionEnd = Math.max(selectionEnd, meta.rangeEnd)
      }
      const caretPrefer =
        rawStart > meta.labelStart && rawStart < meta.labelEnd
          ? (pendingCaretRef.current !== null &&
            pendingCaretRef.current <= meta.rangeStart
              ? "before"
              : "after")
          : undefined
      let caret = getMessageCaretFromDisplay(rawStart, meta, {
        prefer: caretPrefer
      })
      if (caret > meta.rangeStart && caret < meta.rangeEnd) {
        caret = meta.rangeEnd
      }

      const deleteCollapsedBlock = () => {
        const nextValue =
          currentValue.slice(0, meta.rangeStart) +
          currentValue.slice(meta.rangeEnd)
        const nextCaret = Math.min(meta.rangeStart, nextValue.length)
        commitCollapsedEdit(nextValue, nextCaret, null)
      }

      const insertAtCaret = (text: string) => {
        const insertAt =
          caret <= meta.rangeStart
            ? caret
            : caret >= meta.rangeEnd
              ? caret
              : meta.rangeEnd
        replaceCollapsedRange(currentValue, meta, insertAt, insertAt, text)
      }

      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        if (e.shiftKey) return false
        e.preventDefault()
        let nextCaret = caret
        if (hasSelection) {
          nextCaret =
            e.key === "ArrowLeft" ? selectionStart : selectionEnd
        } else {
          nextCaret =
            e.key === "ArrowLeft"
              ? Math.max(0, caret - 1)
              : Math.min(meta.messageLength, caret + 1)
          if (nextCaret > meta.rangeStart && nextCaret < meta.rangeEnd) {
            nextCaret =
              e.key === "ArrowLeft" ? meta.rangeStart : meta.rangeEnd
          }
        }
        pendingCaretRef.current = nextCaret
        syncCollapsedCaret({ caret: nextCaret })
        return true
      }

      if (e.key === "Backspace") {
        if (hasSelection) {
          e.preventDefault()
          replaceCollapsedRange(
            currentValue,
            meta,
            selectionStart,
            selectionEnd,
            ""
          )
          return true
        }
        if (caret === meta.rangeEnd) {
          e.preventDefault()
          deleteCollapsedBlock()
          return true
        }
        if (caret === 0) {
          e.preventDefault()
          return true
        }
        if (caret > meta.rangeStart && caret <= meta.rangeEnd) {
          e.preventDefault()
          deleteCollapsedBlock()
          return true
        }
        e.preventDefault()
        replaceCollapsedRange(
          currentValue,
          meta,
          Math.max(0, caret - 1),
          caret,
          ""
        )
        return true
      }

      if (e.key === "Delete") {
        if (hasSelection) {
          e.preventDefault()
          replaceCollapsedRange(
            currentValue,
            meta,
            selectionStart,
            selectionEnd,
            ""
          )
          return true
        }
        if (caret === meta.rangeStart) {
          e.preventDefault()
          deleteCollapsedBlock()
          return true
        }
        if (caret >= meta.messageLength) {
          e.preventDefault()
          return true
        }
        if (caret >= meta.rangeStart && caret < meta.rangeEnd) {
          e.preventDefault()
          deleteCollapsedBlock()
          return true
        }
        e.preventDefault()
        replaceCollapsedRange(currentValue, meta, caret, caret + 1, "")
        return true
      }

      if (e.key === "Enter") {
        e.preventDefault()
        if (hasSelection) {
          replaceCollapsedRange(
            currentValue,
            meta,
            selectionStart,
            selectionEnd,
            "\n"
          )
        } else {
          insertAtCaret("\n")
        }
        return true
      }

      if (e.key === " " || e.key === "Spacebar") {
        e.preventDefault()
        if (hasSelection) {
          replaceCollapsedRange(
            currentValue,
            meta,
            selectionStart,
            selectionEnd,
            " "
          )
        } else {
          insertAtCaret(" ")
        }
        return true
      }

      const isPrintable =
        e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey
      if (isPrintable) {
        e.preventDefault()
        if (hasSelection) {
          replaceCollapsedRange(
            currentValue,
            meta,
            selectionStart,
            selectionEnd,
            e.key
          )
        } else {
          insertAtCaret(e.key)
        }
        return true
      }

      return false
    },
    [
      collapsedRange,
      commitCollapsedEdit,
      form.values.message,
      getCollapsedDisplayMeta,
      getMessageCaretFromDisplay,
      isMessageCollapsed,
      isSending,
      replaceCollapsedRange,
      sendWhenEnter,
      syncCollapsedCaret,
      textareaRef,
      typing
    ]
  )

  const contextItems = usePlaygroundContextItems({
    selectedModel,
    modelSummaryLabel,
    isSessionDegraded,
    connectionStatusLabel,
    compareModeActive,
    compareSelectedModels,
    currentPreset,
    selectedCharacterName: selectedCharacter?.name || null,
    characterPendingApply,
    contextToolsOpen,
    ragPinnedResultsLength: ragPinnedResults.length,
    webSearch,
    sessionUsageTotalTokens: sessionUsageSummary.totalTokens,
    sessionUsageLabel,
    selectedSystemPrompt,
    selectedQuickPrompt,
    systemPrompt,
    promptSummaryLabel,
    jsonMode: Boolean(currentChatModelSettings.jsonMode),
    showTokenBudgetWarning,
    tokenBudgetRiskLevel: tokenBudgetRisk.level,
    tokenBudgetRiskLabel,
    projectedBudgetUtilizationPercent: projectedBudget.utilizationPercent,
    nonMessageContextPercent,
    showNonMessageContextWarning,
    temporaryChat,
    openModelApiSelector,
    focusConnectionCard,
    setOpenModelSettings,
    setOpenActorSettings,
    setContextToolsOpen,
    handleToggleWebSearch,
    openKnowledgePanel,
    openContextWindowModal,
    openSessionInsightsModal,
    updateChatModelSetting,
    t
  })

  const settingsHook = usePlaygroundSettings({
    selectedCharacterName: selectedCharacter?.name || null,
    selectedSystemPrompt,
    selectedQuickPrompt,
    systemPrompt,
    ragPinnedResultsLength: ragPinnedResults.length,
    webSearch,
    jsonMode: Boolean(currentChatModelSettings.jsonMode),
    compareModeActive,
    compareNeedsMoreModels,
    compareCapabilityIncompatibilities,
    voiceChatEnabled,
    showTokenBudgetWarning,
    tokenBudgetWarningText,
    summaryCheckpointSuggestion,
    messagesLength: messages.length,
    showNonMessageContextWarning,
    nonMessageContextPercent,
    largestContextContributor,
    openKnowledgePanel,
    openContextWindowModal,
    openModelApiSelector,
    setOpenModelSettings,
    setModeLauncherOpen,
    setOpenActorSettings,
    trimLargestContextContributor,
    insertSummaryCheckpointPrompt,
    t
  })
  const {
    compareSharedContextLabels,
    compareInteroperabilityNotices,
    contextConflictWarnings
  } = settingsHook

  const modeLauncherButton = (
    <PlaygroundModeLauncher
      open={modeLauncherOpen}
      onOpenChange={setModeLauncherOpen}
      compareModeActive={compareModeActive}
      compareFeatureEnabled={compareFeatureEnabled}
      onToggleCompare={toggleCompareMode}
      selectedCharacterName={selectedCharacter?.name || null}
      onOpenActorSettings={() => setOpenActorSettings(true)}
      contextToolsOpen={contextToolsOpen}
      onToggleKnowledgePanel={toggleKnowledgePanel}
      voiceChatEnabled={voiceChatEnabled}
      voiceChatAvailable={voiceChatAvailable}
      isSending={isSending}
      onVoiceChatToggle={handleVoiceChatToggle}
      webSearch={webSearch}
      hasWebSearch={!!capabilities?.hasWebSearch}
      onToggleWebSearch={handleToggleWebSearch}
      onModeAnnouncement={setModeAnnouncement}
      t={t}
    />
  )

  const externalPinSources =
    contextToolsOpen ||
    contextWindowModalOpen ||
    sessionInsightsOpen ||
    imageGenerateModalOpen ||
    mcpSettingsOpen ||
    openModelSettings ||
    openActorSettings ||
    documentGeneratorOpen ||
    voiceModeSelectorOpen ||
    modelDropdownOpen ||
    mcpCtrl.mcpPopoverOpen ||
    modeLauncherOpen ||
    toolsPopoverOpen ||
    attachmentMenuOpen ||
    sendMenuOpen

  const {
    actionBarVisible,
    composerFocusWithin,
    actionBarVisibilityClass,
    handlers: actionBarHandlers
  } = useActionBarVisibility({ externalPinSources })
  const shouldCompactComposerTextarea =
    !composerFocusWithin &&
    !contextToolsOpen &&
    !showSlashMenu &&
    !showMentions &&
    !isSending &&
    !isMessageCollapsed &&
    messageDisplayValue.trim().length === 0
  const composerShellRef = React.useRef<HTMLDivElement>(null)

  const keepComposerBottomInView = React.useCallback(() => {
    if (typeof window === "undefined") return
    const composerEl = composerShellRef.current
    if (!composerEl) return

    const bottomPadding = 8
    const scrollingElement = document.scrollingElement as HTMLElement | null

    const adjustAncestor = (ancestor: HTMLElement | null) => {
      if (!ancestor) return
      const composerRect = composerEl.getBoundingClientRect()

      if (ancestor === scrollingElement) {
        const viewportBottom = window.innerHeight - bottomPadding
        const overflow = composerRect.bottom - viewportBottom
        if (overflow > 0) {
          window.scrollBy({ top: overflow, behavior: "auto" })
        }
        return
      }

      const ancestorRect = ancestor.getBoundingClientRect()
      const overflow = composerRect.bottom - (ancestorRect.bottom - bottomPadding)
      if (overflow > 0) {
        ancestor.scrollTop += overflow
      }
    }

    let parent = composerEl.parentElement
    while (parent) {
      const style = window.getComputedStyle(parent)
      const allowsVerticalScroll = /(auto|scroll|overlay)/.test(
        `${style.overflowY} ${style.overflow}`
      )
      if (allowsVerticalScroll && parent.scrollHeight > parent.clientHeight + 1) {
        adjustAncestor(parent)
      }
      parent = parent.parentElement
    }

    adjustAncestor(scrollingElement)
  }, [])

  const previousActionBarVisibleRef = React.useRef(actionBarVisible)

  React.useEffect(() => {
    const wasVisible = previousActionBarVisibleRef.current
    previousActionBarVisibleRef.current = actionBarVisible

    if (!actionBarVisible || wasVisible) return

    let timeoutId: number | null = null
    const rafId = window.requestAnimationFrame(() => {
      keepComposerBottomInView()
      timeoutId = window.setTimeout(() => {
        keepComposerBottomInView()
      }, 220)
    })

    return () => {
      window.cancelAnimationFrame(rafId)
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [actionBarVisible, keepComposerBottomInView])

  const previousKeyboardOpenRef = React.useRef(false)
  React.useEffect(() => {
    if (!isMobileViewport) return
    if (typeof window === "undefined") return

    const wasOpen = previousKeyboardOpenRef.current
    previousKeyboardOpenRef.current = mobileComposerViewport.keyboardOpen

    if (!mobileComposerViewport.keyboardOpen && !wasOpen) {
      return
    }

    let timeoutId: number | null = null
    const rafId = window.requestAnimationFrame(() => {
      keepComposerBottomInView()
      timeoutId = window.setTimeout(() => {
        keepComposerBottomInView()
      }, 120)
    })

    return () => {
      window.cancelAnimationFrame(rafId)
      if (timeoutId != null) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [
    isMobileViewport,
    keepComposerBottomInView,
    mobileComposerViewport.keyboardInsetPx,
    mobileComposerViewport.keyboardOpen
  ])

  React.useEffect(() => {
    if (typeof document === "undefined") return

    const handleFocusIn = (event: FocusEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (!composerShellRef.current?.contains(target)) return
      keepComposerBottomInView()
      if (typeof window !== "undefined") {
        window.setTimeout(() => {
          keepComposerBottomInView()
        }, 80)
      }
    }

    document.addEventListener("focusin", handleFocusIn)
    return () => {
      document.removeEventListener("focusin", handleFocusIn)
    }
  }, [keepComposerBottomInView])

  const previousSendStateRef = React.useRef(isSending)
  React.useEffect(() => {
    if (!isMobileViewport) {
      previousSendStateRef.current = isSending
      return
    }
    if (typeof window === "undefined") {
      previousSendStateRef.current = isSending
      return
    }

    const wasSending = previousSendStateRef.current
    previousSendStateRef.current = isSending

    if (!isSending && !wasSending) {
      return
    }

    let timeoutId: number | null = null
    const rafId = window.requestAnimationFrame(() => {
      keepComposerBottomInView()
      timeoutId = window.setTimeout(() => {
        keepComposerBottomInView()
      }, 100)
    })

    return () => {
      window.cancelAnimationFrame(rafId)
      if (timeoutId != null) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [isMobileViewport, isSending, keepComposerBottomInView])

  const toolRunStatusLabel = React.useMemo(() => {
    if (chatLoopState.pendingApprovals.length > 0) {
      return t("playground:composer.toolRunPending", "Pending approval")
    }
    if (
      chatLoopState.inflightToolCallIds.length > 0 ||
      chatLoopState.status === "running"
    ) {
      return t("playground:composer.toolRunRunning", "Running")
    }
    if (chatLoopState.status === "error") {
      return t("playground:composer.toolRunFailed", "Failed")
    }
    if (chatLoopState.status === "complete") {
      return t("playground:composer.toolRunDone", "Done")
    }
    return t("playground:composer.toolRunIdle", "Idle")
  }, [chatLoopState, t])

  const mcpControl = (
    <PlaygroundMcpControl
      hasMcp={hasMcp}
      mcpHealthState={mcpHealthState}
      mcpToolsLoading={mcpToolsLoading}
      mcpToolsCount={mcpTools.length}
      toolChoice={toolChoice}
      onToolChoiceChange={setToolChoice}
      toolRunStatusLabel={toolRunStatusLabel}
      mcpAriaLabel={mcpCtrl.mcpAriaLabel}
      mcpSummaryLabel={mcpCtrl.mcpSummaryLabel}
      mcpChoiceLabel={mcpCtrl.mcpChoiceLabel}
      mcpDisabledReason={mcpCtrl.mcpDisabledReason}
      mcpPopoverOpen={mcpCtrl.mcpPopoverOpen}
      onMcpPopoverChange={mcpCtrl.setMcpPopoverOpen}
      onOpenMcpSettings={() => setMcpSettingsOpen(true)}
      t={t}
    />
  )

  const voiceChatButton = voiceChatAvailable ? (
    <Tooltip
      title={
        voiceChatEnabled
          ? t("playground:voiceChat.toolbarStop", "Stop voice chat")
          : t("playground:voiceChat.toolbarStart", "Start voice chat")
      }
    >
      <button
        type="button"
        onClick={handleVoiceChatToggle}
        disabled={isSending}
        aria-label={voiceChatStatusLabel}
        data-testid="voice-chat-button"
        className={`flex items-center gap-1.5 rounded-full px-2 py-1.5 text-sm transition ${
          voiceChat.state === "error"
            ? "bg-danger/10 text-danger"
            : voiceChatEnabled && voiceChat.state !== "idle"
              ? "bg-primary/10 text-primary animate-pulse"
              : "hover:bg-surface2 text-text-muted"
        }`}
      >
        <Headphones className="h-4 w-4" />
        {voiceChatEnabled && voiceChat.state !== "idle" && (
          <span className="text-xs">{voiceChatStatusLabel}</span>
        )}
      </button>
    </Tooltip>
  ) : null

  const toolsButton = (
    <PlaygroundToolsPopover
      toolsPopoverOpen={toolsPopoverOpen}
      onToolsPopoverChange={setToolsPopoverOpen}
      isProMode={isProMode}
      onOpenImageGenerate={openImageGenerateModal}
      onOpenKnowledgePanel={openKnowledgePanel}
      useOCR={useOCR}
      onUseOCRChange={setUseOCR}
      hasWebSearch={!!capabilities?.hasWebSearch}
      webSearch={webSearch}
      onWebSearchChange={setWebSearch}
      simpleInternetSearch={simpleInternetSearch}
      onSimpleInternetSearchChange={setSimpleInternetSearch}
      defaultInternetSearchOn={defaultInternetSearchOn}
      onDefaultInternetSearchOnChange={setDefaultInternetSearchOnSetting}
      onNavigateWebSearchSettings={navigateToWebSearchSettings}
      advancedToolsExpanded={advancedToolsExpanded}
      onAdvancedToolsExpandedChange={setAdvancedToolsExpanded}
      allowExternalImages={allowExternalImages}
      onAllowExternalImagesChange={setAllowExternalImages}
      showMoodBadge={showMoodBadge}
      onShowMoodBadgeChange={setShowMoodBadge}
      showMoodConfidence={showMoodConfidence}
      onShowMoodConfidenceChange={setShowMoodConfidence}
      onOpenRawRequest={openRawRequestModal}
      voiceChatAvailable={voiceChatAvailable}
      voiceChatEnabled={voiceChatEnabled}
      voiceChatState={voiceChat.state}
      voiceChatStatusLabel={voiceChatStatusLabel}
      onVoiceChatToggle={handleVoiceChatToggle}
      isSending={isSending}
      voiceChatSettingsFields={voiceChatSettingsFields}
      imageProviderControl={imageProviderControl}
      historyLength={history.length}
      onClearContext={handleClearContext}
      t={t}
    />
  )

  const attachmentButton = (
    <PlaygroundAttachmentButton
      isProMode={isProMode}
      isMobileViewport={isMobileViewport}
      chatMode={chatMode}
      onImageUpload={handleImageUpload}
      onDocumentUpload={handleDocumentUpload}
      onOpenKnowledgePanel={openKnowledgePanel}
      attachmentMenuOpen={attachmentMenuOpen}
      onAttachmentMenuChange={setAttachmentMenuOpen}
      t={t}
    />
  )
  const sendControl = (
    <PlaygroundSendControl
      isProMode={isProMode}
      isMobileViewport={isMobileViewport}
      isSending={isSending}
      isConnectionReady={isConnectionReady}
      sendWhenEnter={sendWhenEnter}
      onSendWhenEnterChange={setSendWhenEnter}
      sendLabel={sendLabel}
      compareNeedsMoreModels={compareNeedsMoreModels}
      onStopStreaming={stopStreamingRequest}
      onStopListening={stopListening}
      onSubmitForm={submitForm}
      sendMenuOpen={sendMenuOpen}
      onSendMenuChange={setSendMenuOpen}
      t={t}
    />
  )

  const startupTemplatePromptResolution = startupTemplatePreview
    ? resolveStartupTemplatePrompt(startupTemplatePreview, promptLibrary)
    : null
  const startupTemplatePromptDescription = startupTemplatePreview
    ? describeStartupTemplatePrompt(startupTemplatePreview, promptLibrary)
    : null
  const startupTemplatePreset = startupTemplatePreview
    ? getPresetByKey(startupTemplatePreview.presetKey)
    : undefined

  return (
    <React.Profiler
      id="playground-form-root"
      onRender={onComposerRenderProfile}
    >
      <div className="flex w-full flex-col items-center px-4 pb-6">
      <div
        data-checkwidemode={checkWideMode}
        data-ui-mode={uiMode}
        className="relative z-10 flex w-full max-w-[64rem] flex-col items-center justify-center gap-2 text-base data-[checkwidemode='true']:max-w-none">
        <div className="relative flex w-full flex-row justify-center">
          <div
            ref={composerShellRef}
            data-istemporary-chat={temporaryChat}
            data-mobile-keyboard={
              isMobileViewport
                ? mobileComposerViewport.keyboardOpen
                  ? "open"
                  : "closed"
                : "desktop"
            }
            onMouseEnter={actionBarHandlers.onMouseEnter}
            onMouseLeave={actionBarHandlers.onMouseLeave}
            onFocusCapture={actionBarHandlers.onFocusCapture}
            onBlurCapture={actionBarHandlers.onBlurCapture}
            style={
              isMobileViewport
                ? {
                    scrollMarginBottom: `${Math.max(
                      mobileComposerViewport.keyboardInsetPx,
                      16
                    )}px`,
                    paddingBottom:
                      "calc(env(safe-area-inset-bottom, 0px) + 0.75rem)"
                  }
                : undefined
            }
            className={`relative w-full rounded-3xl border border-transparent bg-surface/95 p-3 text-text shadow-card backdrop-blur-lg transition-all duration-200 data-[istemporary-chat='true']:border-t-4 data-[istemporary-chat='true']:border-t-purple-500 data-[istemporary-chat='true']:border-dashed data-[istemporary-chat='true']:opacity-90 ${
              !isConnectionReady ? "opacity-80" : ""
            }`}>
            {/* Attachments summary (collapsed context management) */}
            {wrapComposerProfile(
              "attachments-summary",
              <AttachmentsSummary
                image={form.values.image}
                documents={selectedDocuments}
                files={uploadedFiles}
                onRemoveImage={() => form.setFieldValue("image", "")}
                onRemoveDocument={removeDocument}
                onClearDocuments={clearSelectedDocuments}
                onRemoveFile={removeUploadedFile}
                onClearFiles={clearUploadedFiles}
                onOpenKnowledgePanel={() => openKnowledgePanel("context")}
                readOnly
              />
            )}
            {/* Link to Model Playground for Compare mode */}
            <div>
              <div className="flex w-full min-w-0 bg-transparent">
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    stopListening()
                    submitForm()
                  }}
                  className="flex w-full min-w-0 flex-col items-center">
                  <input
                    id="file-upload"
                    name="file-upload"
                    type="file"
                    className="sr-only"
                    ref={inputRef}
                    accept="image/*"
                    multiple={false}
                    tabIndex={-1}
                    aria-hidden="true"
                    aria-label={t("playground:actions.attachImage", "Attach image") as string}
                    onChange={onInputChange}
                  />
                  <input
                    id="document-upload"
                    name="document-upload"
                    type="file"
                    className="sr-only"
                    ref={fileInputRef}
                    accept=".pdf,.doc,.docx,.txt,.csv,.md,.markdown,text/markdown"
                    multiple={false}
                    tabIndex={-1}
                    aria-hidden="true"
                    aria-label={t("playground:actions.attachDocument", "Attach document") as string}
                    onChange={onFileInputChange}
                  />

                  <div
                    className={`w-full flex flex-col px-2 ${
                      !isConnectionReady
                        ? "rounded-md border border-dashed border-border bg-surface2"
                        : ""
                    }`}>
                    <PlaygroundKnowledgeSection
                      contextToolsOpen={contextToolsOpen}
                      isConnectionReady={isConnectionReady}
                      knowledgePanelTab={knowledgePanelTab}
                      knowledgePanelTabRequestId={knowledgePanelTabRequestId}
                      deferredComposerInput={deferredComposerInput}
                      attachedImage={form.values.image}
                      attachedTabs={selectedDocuments}
                      availableTabs={availableTabs}
                      attachedFiles={uploadedFiles}
                      fileRetrievalEnabled={fileRetrievalEnabled}
                      onInsert={handleKnowledgeInsert}
                      onAsk={handleKnowledgeAsk}
                      onOpenChange={handleKnowledgePanelOpenChange}
                      onRemoveImage={handleKnowledgeRemoveImage}
                      onRemoveTab={removeDocument}
                      onAddTab={addDocument}
                      onClearTabs={clearSelectedDocuments}
                      onRefreshTabs={reloadTabs}
                      onAddFile={handleKnowledgeAddFile}
                      onRemoveFile={removeUploadedFile}
                      onClearFiles={clearUploadedFiles}
                      onFileRetrievalChange={setFileRetrievalEnabled}
                      wrapComposerProfile={wrapComposerProfile}
                      t={t}
                    />
                    <div className="relative">
                      {isProMode && replyTarget && (
                        <div className="mb-2 flex items-center justify-between gap-2 rounded-md border border-border bg-surface2 px-3 py-2 text-xs text-text">
                          <div className="flex min-w-0 items-center gap-2">
                            <CornerUpLeft className="h-3.5 w-3.5 text-text-subtle" />
                            <span className="min-w-0 truncate">
                              {replyLabel}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={clearReplyTarget}
                            aria-label={t(
                              "common:clearReply",
                              "Clear reply target"
                            )}
                            title={t(
                              "common:clearReply",
                              "Clear reply target"
                            ) as string}
                            className="rounded p-1 text-text-subtle hover:bg-surface hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                            <X className="h-3.5 w-3.5" aria-hidden="true" />
                          </button>
                        </div>
                      )}
                      {wrapComposerProfile(
                        "composer-textarea",
                        <ComposerTextarea
                          textareaRef={textareaRef}
                          value={form.values.message}
                          displayValue={messageDisplayValue}
                          onChange={handleTextareaChange}
                          onKeyDown={handleTextareaKeyDown}
                          onPaste={handlePaste}
                          onFocus={handleTextareaFocus}
                          onSelect={handleTextareaSelect}
                          onCompositionStart={handleCompositionStart}
                          onCompositionEnd={handleCompositionEnd}
                          onMouseDown={handleTextareaMouseDown}
                          onMouseUp={handleTextareaMouseUp}
                          placeholder={
                            isConnectionReady
                              ? t(
                                  "playground:composer.placeholderWithMentions",
                                  "Type a message... (/ commands, @ mentions)"
                                )
                              : t(
                                  "playground:composer.connectionPlaceholder",
                                  "Connect to tldw to start chatting."
                                )
                          }
                          isProMode={isProMode}
                          isMobile={isMobileViewport}
                          isConnectionReady={isConnectionReady}
                          isCollapsed={isMessageCollapsed}
                          ariaExpanded={!isMessageCollapsed}
                          compactWhenInactive={shouldCompactComposerTextarea}
                          formInputProps={form.getInputProps("message")}
                          showSlashMenu={showSlashMenu}
                          slashCommands={filteredSlashCommands}
                          slashActiveIndex={slashActiveIndex}
                          onSlashSelect={handleSlashCommandSelect}
                          onSlashActiveIndexChange={setSlashActiveIndex}
                          slashEmptyLabel={t(
                            "common:commandPalette.noResults",
                            "No results found"
                          )}
                          showMentions={showMentions}
                          filteredTabs={filteredTabs}
                          mentionPosition={mentionPosition}
                          onMentionSelect={handleMentionSelect}
                          onMentionsClose={closeMentions}
                          onMentionRefetch={handleMentionRefetch}
                          onMentionsOpen={handleMentionsOpen}
                          draftSaved={draftSaved}
                        />
                      )}
                    </div>
                    {/* Inline error message with shake animation */}
                    {form.errors.message && (
                      <div
                        role="alert"
                        aria-live="assertive"
                        aria-atomic="true"
                        className="flex items-center justify-between gap-2 px-2 py-1 text-xs text-danger animate-shake"
                      >
                        <div className="flex items-center gap-2">
                          <svg className="h-3.5 w-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                          </svg>
                          <span>{form.errors.message}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => form.clearFieldError("message")}
                          className="flex-shrink-0 text-danger hover:text-danger"
                          aria-label={t("common:dismiss", "Dismiss") as string}
                          title={t("common:dismiss", "Dismiss") as string}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                    {/* Proactive validation hints - show why send might be disabled */}
                    {!form.errors.message && isConnectionReady && !isSending && isProMode && (
                      <div className="px-2 py-1 text-label text-text-subtle">
                        {!selectedModel && !activeImageCommand ? (
                          <span className="flex items-center gap-1">
                            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            {t("sidepanel:composer.hints.selectModel", "Select a model above to start chatting")}
                          </span>
                        ) : form.values.message.trim().length === 0 && form.values.image.length === 0 ? (
                          <span>
                            {sendWhenEnter
                              ? t("sidepanel:composer.hints.typeAndEnter", "Type a message and press Enter to send")
                              : t("sidepanel:composer.hints.typeAndClick", "Type a message and click Send")}
                          </span>
                        ) : null}
                      </div>
                    )}
                    <PlaygroundComposerNotices
                      modeAnnouncement={modeAnnouncement}
                      characterPendingApply={characterPendingApply}
                      selectedCharacterGreeting={selectedCharacterGreeting}
                      selectedCharacterName={selectedCharacter?.name || null}
                      compareModeActive={compareModeActive}
                      compareSelectedModels={compareSelectedModels}
                      compareSelectedModelLabels={compareSelectedModelLabels}
                      compareNeedsMoreModels={compareNeedsMoreModels}
                      compareSharedContextLabels={compareSharedContextLabels}
                      compareInteroperabilityNotices={compareInteroperabilityNotices}
                      noticesExpanded={noticesExpanded}
                      setNoticesExpanded={setNoticesExpanded}
                      contextDeltaLabels={contextDeltaLabels}
                      contextConflictWarnings={contextConflictWarnings}
                      visibleModelRecommendations={visibleModelRecommendations}
                      sessionInsightsTotalTokens={sessionInsights.totals.totalTokens}
                      jsonMode={Boolean(currentChatModelSettings.jsonMode)}
                      isConnectionReady={isConnectionReady}
                      connectionUxState={connectionUxState}
                      isProMode={isProMode}
                      selectedModel={selectedModel}
                      systemPrompt={systemPrompt}
                      selectedCharacter={selectedCharacter}
                      ragPinnedResultsLength={ragPinnedResults.length}
                      startupTemplateDraftName={startupTemplateDraftName}
                      setStartupTemplateDraftName={setStartupTemplateDraftName}
                      startupTemplates={startupTemplates}
                      handleSaveStartupTemplate={handleSaveStartupTemplate}
                      handleOpenStartupTemplatePreview={handleOpenStartupTemplatePreview}
                      setOpenModelSettings={setOpenModelSettings}
                      setOpenActorSettings={setOpenActorSettings}
                      setMessageValue={setMessageValue}
                      textAreaFocus={textAreaFocus}
                      openModelApiSelector={openModelApiSelector}
                      openSessionInsightsModal={openSessionInsightsModal}
                      handleModelRecommendationAction={handleModelRecommendationAction}
                      dismissModelRecommendation={dismissModelRecommendation}
                      getModelRecommendationActionLabel={getModelRecommendationActionLabel}
                      wrapComposerProfile={wrapComposerProfile}
                      t={t}
                    />
                    <div
                      aria-hidden={!actionBarVisible}
                      className={`transition-all duration-200 overflow-hidden ${actionBarVisibilityClass}`}
                    >
                      {wrapComposerProfile(
                        "composer-toolbar",
                        <ComposerToolbar
                          isProMode={isProMode}
                          isMobile={isMobileViewport}
                          isConnectionReady={isConnectionReady}
                          isSending={isSending}
                          modeLauncherButton={modeLauncherButton}
                          compareControl={compareControl}
                          modelSelectButton={modelSelectButton}
                          mcpControl={mcpControl}
                          sendControl={sendControl}
                          attachmentButton={attachmentButton}
                          toolsButton={toolsButton}
                          voiceChatButton={voiceChatButton}
                          modelUsageBadge={modelUsageBadge}
                          selectedSystemPrompt={selectedSystemPrompt}
                          setSelectedSystemPrompt={setSelectedSystemPrompt}
                          setSelectedQuickPrompt={setSelectedQuickPrompt}
                          temporaryChat={temporaryChat}
                          onToggleTemporaryChat={handleToggleTemporaryChat}
                          privateChatLocked={privateChatLocked}
                          isFireFoxPrivateMode={isFireFoxPrivateMode}
                          persistenceTooltip={persistenceTooltip}
                          contextToolsOpen={contextToolsOpen}
                          onToggleKnowledgePanel={toggleKnowledgePanel}
                          webSearch={webSearch}
                          onToggleWebSearch={handleToggleWebSearch}
                          hasWebSearch={!!capabilities?.hasWebSearch}
                          onOpenModelSettings={handleOpenModelSettings}
                          modelSummaryLabel={modelSummaryLabel}
                          promptSummaryLabel={promptSummaryLabel}
                          hasDictation={!!(browserSupportsSpeechRecognition || hasServerStt)}
                          speechAvailable={speechAvailable}
                          speechUsesServer={speechUsesServer}
                          isListening={isListening}
                          isServerDictating={isServerDictating}
                          voiceChatEnabled={voiceChatEnabled}
                          speechTooltip={speechTooltipText}
                          onDictationToggle={handleDictationToggle}
                          onTemplateSelect={handleTemplateSelect}
                          selectedModel={selectedModel}
                          resolvedProviderKey={resolvedProviderKey}
                          messages={messages}
                          selectedDocumentsCount={selectedDocuments.length}
                          uploadedFilesCount={uploadedFiles.length}
                          serverChatId={serverChatId}
                          showServerPersistenceHint={showServerPersistenceHint}
                          onDismissServerPersistenceHint={handleDismissServerPersistenceHint}
                          onFocusConnectionCard={focusConnectionCard}
                          contextItems={contextItems}
                        />
                      )}
                    </div>
                    {showConnectBanner && !isConnectionReady && (
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
                        <p className="max-w-xs text-left">
                          {t(
                            "playground:composer.connectNotice",
                            "Connect to your tldw server in Settings to send messages."
                          )}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to="/settings/tldw"
                            className="text-xs font-medium text-warn underline hover:text-warn"
                          >
                            {t("settings:tldw.setupLink", "Set up server")}
                          </Link>
                          <Link
                            to="/settings/health"
                            className="text-xs font-medium text-warn underline hover:text-warn"
                          >
                            {t(
                              "settings:healthSummary.diagnostics",
                              "Health & diagnostics"
                            )}
                          </Link>
                          <button
                            type="button"
                            onClick={() => setShowConnectBanner(false)}
                            className="inline-flex items-center rounded-full p-1 text-warn hover:bg-warn/10"
                            aria-label={t("common:close", "Dismiss")}
                            title={t("common:close", "Dismiss") as string}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    )}
                    <ChatQueuePanel
                      queue={queuedMessages}
                      isConnectionReady={isConnectionReady}
                      isStreaming={isSending}
                      onRunNext={handleRunNextQueuedRequest}
                      onRunNow={handleRunQueuedRequest}
                      onDelete={queuedRequestActions.remove}
                      onMove={queuedRequestActions.move}
                      onUpdate={queuedRequestActions.update}
                      onClearAll={queuedRequestActions.clear}
                      onOpenDiagnostics={() => navigate("/settings/health")}
                      forceRunDisabledReason={cancelCurrentAndRunDisabledReason}
                    />
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
      <PlaygroundImageGenModal
        open={imageGenerateModalOpen}
        onClose={() => setImageGenerateModalOpen(false)}
        busy={imageGenerateBusy}
        backend={imageGenerateBackend}
        backendOptions={imageGenerateBackendOptions}
        onBackendChange={setImageGenerateBackend}
        onHydrateSettings={hydrateImageGenerateSettings}
        promptMode={imageGeneratePromptMode}
        onPromptModeChange={setImageGeneratePromptMode}
        promptStrategies={imagePromptStrategies}
        syncPolicy={imageGenerateSyncPolicy}
        onSyncPolicyChange={setImageGenerateSyncPolicy}
        syncChatMode={imageEventSyncChatMode}
        onSyncChatModeChange={(next) => void updateChatSettings({ imageEventSyncMode: next })}
        syncGlobalDefault={imageEventSyncGlobalDefault}
        onSyncGlobalDefaultChange={(next) => void setImageEventSyncGlobalDefault(next)}
        resolvedSyncMode={imageGenerateResolvedSyncMode}
        prompt={imageGeneratePrompt}
        onPromptChange={setImageGeneratePrompt}
        contextBreakdown={imagePromptContextBreakdown}
        onClearRefineState={clearImagePromptRefineState}
        refineSubmitting={imagePromptRefineSubmitting}
        refineBaseline={imagePromptRefineBaseline}
        refineCandidate={imagePromptRefineCandidate}
        refineModel={imagePromptRefineModel}
        refineLatencyMs={imagePromptRefineLatencyMs}
        refineDiff={imagePromptRefineDiff}
        onCreateDraft={handleCreateImagePromptDraft}
        onRefine={handleRefineImagePromptDraft}
        onApplyRefined={applyRefinedImagePromptCandidate}
        onRejectRefined={rejectRefinedImagePromptCandidate}
        format={imageGenerateFormat}
        onFormatChange={setImageGenerateFormat}
        width={imageGenerateWidth}
        onWidthChange={setImageGenerateWidth}
        height={imageGenerateHeight}
        onHeightChange={setImageGenerateHeight}
        steps={imageGenerateSteps}
        onStepsChange={setImageGenerateSteps}
        cfgScale={imageGenerateCfgScale}
        onCfgScaleChange={setImageGenerateCfgScale}
        seed={imageGenerateSeed}
        onSeedChange={setImageGenerateSeed}
        sampler={imageGenerateSampler}
        onSamplerChange={setImageGenerateSampler}
        model={imageGenerateModel}
        onModelChange={setImageGenerateModel}
        negativePrompt={imageGenerateNegativePrompt}
        onNegativePromptChange={setImageGenerateNegativePrompt}
        extraParams={imageGenerateExtraParams}
        onExtraParamsChange={setImageGenerateExtraParams}
        submitting={imageGenerateSubmitting}
        onSubmit={submitImageGenerateModal}
        t={t}
      />
      <PlaygroundRawRequestModal
        open={rawRequestModalOpen}
        onClose={() => setRawRequestModalOpen(false)}
        snapshot={rawRequestSnapshot}
        json={rawRequestJson}
        onRefresh={refreshRawRequestSnapshot}
        onCopy={copyRawRequestJson}
        t={t}
      />
      <PlaygroundStartupTemplateModal
        preview={startupTemplatePreview}
        onClose={() => setStartupTemplatePreview(null)}
        onDelete={handleDeleteStartupTemplate}
        onApply={handleApplyStartupTemplate}
        promptDescription={startupTemplatePromptDescription}
        promptResolution={startupTemplatePromptResolution}
        preset={startupTemplatePreset}
        t={t}
      />
      <PlaygroundContextWindowModal
        contextWindowModalOpen={contextWindowModalOpen}
        onCloseContextWindow={() => setContextWindowModalOpen(false)}
        onSaveContextWindow={saveContextWindowSetting}
        onResetContextWindow={resetContextWindowSetting}
        contextWindowDraftValue={contextWindowDraftValue}
        onContextWindowDraftChange={setContextWindowDraftValue}
        resolvedMaxContext={resolvedMaxContext}
        requestedContextWindowOverride={requestedContextWindowOverride}
        modelContextLength={modelContextLength}
        isContextWindowOverrideActive={isContextWindowOverrideActive}
        isContextWindowOverrideClamped={isContextWindowOverrideClamped}
        nonMessageContextPercent={nonMessageContextPercent}
        showNonMessageContextWarning={showNonMessageContextWarning}
        tokenBudgetRiskLabel={tokenBudgetRiskLabel}
        tokenBudgetRisk={tokenBudgetRisk}
        contextFootprintRows={contextFootprintRows}
        formatContextWindowValue={formatContextWindowValue}
        onClearPromptContext={clearPromptContext}
        onClearPinnedSourceContext={clearPinnedSourceContext}
        onClearHistoryContext={clearHistoryContext}
        onCreateSummaryCheckpoint={insertSummaryCheckpointPrompt}
        onReviewCharacterContext={() => setOpenActorSettings(true)}
        onTrimLargestContextContributor={trimLargestContextContributor}
        sessionInsightsOpen={sessionInsightsOpen}
        onCloseSessionInsights={() => setSessionInsightsOpen(false)}
        sessionInsights={sessionInsights}
        t={t}
      />
      <PlaygroundMcpSettingsModal
        open={mcpSettingsOpen}
        onClose={() => setMcpSettingsOpen(false)}
        hasMcp={hasMcp}
        mcpStatusLabel={mcpCtrl.mcpStatusLabel}
        catalogsLoading={mcpCatalogsLoading}
        catalogGroups={mcpCtrl.catalogGroups}
        catalogDraft={mcpCtrl.catalogDraft}
        onCatalogDraftChange={mcpCtrl.setCatalogDraft}
        onCatalogCommit={mcpCtrl.commitCatalog}
        onCatalogSelect={mcpCtrl.handleCatalogSelect}
        toolCatalogId={toolCatalogId}
        onToolCatalogIdChange={setToolCatalogId}
        toolCatalogStrict={toolCatalogStrict}
        onToolCatalogStrictChange={setToolCatalogStrict}
        moduleOptions={moduleOptions}
        moduleOptionsLoading={moduleOptionsLoading}
        toolModules={toolModules}
        onModuleSelect={handleModuleSelect}
        isSmallModel={isSmallModel}
        t={t}
      />
      {openModelSettings && (
        <CurrentChatModelSettings
          open={openModelSettings}
          setOpen={setOpenModelSettings}
          isOCREnabled={useOCR}
        />
      )}
      {openActorSettings && (
        <ActorPopout open={openActorSettings} setOpen={setOpenActorSettings} />
      )}
      {documentGeneratorOpen && (
        <DocumentGeneratorDrawer
          open={documentGeneratorOpen}
          onClose={() => {
            setDocumentGeneratorOpen(false)
            setDocumentGeneratorSeed({})
          }}
          conversationId={
            documentGeneratorSeed?.conversationId ?? serverChatId ?? null
          }
          defaultModel={selectedModel || null}
          seedMessage={documentGeneratorSeed?.message ?? null}
          seedMessageId={documentGeneratorSeed?.messageId ?? null}
        />
      )}
      {voiceChatEnabled && voiceChat.state !== "idle" && (
        <VoiceChatIndicator
          state={voiceChat.state}
          statusLabel={voiceChatStatusLabel}
          onStop={handleVoiceChatToggle}
        />
      )}
        {voiceModeSelectorOpen && (
          <VoiceModeSelector
            open={voiceModeSelectorOpen}
            onClose={() => setVoiceModeSelectorOpen(false)}
            onSelectDictation={handleDictationToggle}
            onSelectConversation={handleVoiceChatToggle}
            dictationAvailable={speechAvailable}
            conversationAvailable={voiceChatAvailable}
          />
        )}
      </div>
    </React.Profiler>
  )
}
