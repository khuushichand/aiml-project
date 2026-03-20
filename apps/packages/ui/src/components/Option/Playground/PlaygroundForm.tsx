import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import React from "react"
import useDynamicTextareaSize from "@/hooks/useDynamicTextareaSize"
import { toBase64 } from "@/libs/to-base64"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"
import {
  Checkbox,
  Dropdown,
  Input,
  InputNumber,
  Radio,
  Select,
  Switch,
  Tooltip,
  Popover,
  Modal,
  Button,
  Space
} from "antd"
import { useWebUI } from "@/store/webui"
import { defaultEmbeddingModelForRag } from "@/services/tldw-server"
import {
  ChevronDown,
  ChevronRight,
  EraserIcon,
  GitBranch,
  ImageIcon,
  Globe,
  MicIcon,
  Headphones,
  SlidersHorizontal,
  StopCircleIcon,
  X,
  FileIcon,
  FileText,
  PaperclipIcon,
  Gauge,
  Search,
  CornerUpLeft,
  Settings2,
  HelpCircle,
  ArrowRight,
  WandSparkles
} from "lucide-react"
import { getVariable } from "@/utils/select-variable"
import { useTranslation } from "react-i18next"
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition"
import type {
  DictationErrorClass,
  DictationModePreference,
  DictationResolvedMode,
  DictationServerErrorTransition
} from "@/hooks/useDictationStrategy"
import { useDictationStrategy } from "@/hooks/useDictationStrategy"
import { useServerDictation } from "@/hooks/useServerDictation"
import type { SttSettings } from "@/hooks/useSttSettings"
import { isFirefoxTarget } from "@/config/platform"
import { handleChatInputKeyDown } from "@/utils/key-down"
import { getIsSimpleInternetSearch } from "@/services/search"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { formatPinnedResults } from "@/utils/rag-format"
import { useStorage } from "@plasmohq/storage/hook"
import { useTabMentions } from "@/hooks/useTabMentions"
import { useFocusShortcuts } from "@/hooks/keyboard"
import { isMac } from "@/hooks/useKeyboardShortcuts"
import { useDraftPersistence } from "@/hooks/useDraftPersistence"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { useVoiceChatSettings } from "@/hooks/useVoiceChatSettings"
import { useVoiceChatStream } from "@/hooks/useVoiceChatStream"
import { useVoiceChatMessages } from "@/hooks/useVoiceChatMessages"
import { MentionsDropdown } from "./MentionsDropdown"
import { AttachedResearchContextChip } from "./AttachedResearchContextChip"
import { ComposerTextarea } from "./ComposerTextarea"
import { ComposerToolbar, type ComposerContextItem } from "./ComposerToolbar"
import { ContextFootprintPanel } from "./ContextFootprintPanel"
import { CompareToggle } from "./CompareToggle"
import { detectCurrentPreset, getPresetByKey } from "./ParameterPresets"
import {
  buildCompareModelMetaById,
  compareModelsSupportCapability as compareModelsSupportCapabilityCheck,
  getCompareCapabilityIncompatibilities
} from "./compare-preflight"
import { buildCompareInteroperabilityNotices } from "./compare-interoperability"
import { useMobileComposerViewport } from "./useMobileComposerViewport"
import { otherUnsupportedTypes } from "../Knowledge/utils/unsupported-types"
import { PASTED_TEXT_CHAR_LIMIT } from "@/utils/constant"
import { isFireFoxPrivateMode } from "@/utils/is-private-mode"
import { CurrentChatModelSettings } from "@/components/Common/Settings/CurrentChatModelSettings"
import { ActorPopout } from "@/components/Common/Settings/ActorPopout"
import { useConnectionState } from "@/hooks/useConnectionState"
import { ConnectionPhase, deriveConnectionUxState } from "@/types/connection"
import { Link, useNavigate } from "react-router-dom"
import { fetchChatModels, fetchImageModels } from "@/services/tldw-server"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useTldwAudioStatus } from "@/hooks/useTldwAudioStatus"
import { useMcpTools } from "@/hooks/useMcpTools"
import {
  tldwClient,
  type ConversationState,
  type ChatCompletionRequest,
  type ChatMessage,
  type ResearchRunCreateRequest,
  type ResearchRunFollowUpBackground
} from "@/services/tldw/TldwApiClient"
import {
  captureChatRequestDebugSnapshot,
  type ChatRequestDebugSnapshot
} from "@/services/tldw/chat-request-debug"
import {
  buildDiscussMediaHint,
  getMediaChatHandoffMode,
  normalizeMediaChatHandoffPayload,
  parseMediaIdAsNumber
} from "@/services/tldw/media-chat-handoff"
import {
  getImageBackendConfigs,
  normalizeImageBackendConfig,
  resolveImageBackendConfig
} from "@/services/image-generation"
import { CharacterSelect } from "@/components/Common/CharacterSelect"
import { ProviderIcons } from "@/components/Common/ProviderIcon"
import type { Character } from "@/types/character"
import { KnowledgePanel, type KnowledgeTab } from "@/components/Knowledge"
import { BetaTag } from "@/components/Common/Beta"
import type { SlashCommandItem } from "@/components/Sidepanel/Chat/SlashCommandMenu"
import { DocumentGeneratorDrawer } from "@/components/Common/Playground/DocumentGeneratorDrawer"
import { useUiModeStore } from "@/store/ui-mode"
import {
  useStoreChatModelSettings,
  type ChatModelSettings
} from "@/store/model"
import type { Prompt } from "@/db/dexie/types"
import { getAllPrompts } from "@/db/dexie/helpers"
import { TokenProgressBar } from "./TokenProgressBar"
import { AttachmentsSummary } from "./AttachmentsSummary"
import { VoiceChatIndicator } from "./VoiceChatIndicator"
import { VoiceModeSelector } from "./VoiceModeSelector"
import { useMobile } from "@/hooks/useMediaQuery"
import { clearSetting, getSetting } from "@/services/settings/registry"
import { DISCUSS_MEDIA_PROMPT_SETTING } from "@/services/settings/ui-settings"
import { Button as TldwButton } from "@/components/Common/Button"
import { useSimpleForm } from "@/hooks/useSimpleForm"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useStoreMessageOption } from "@/store/option"
import { trackOnboardingChatSubmitSuccess } from "@/utils/onboarding-ingestion-telemetry"
import { resolveApiProviderForModel } from "@/utils/resolve-api-provider"
import { withTemplateFallback } from "@/utils/template-guards"
import { emitDictationDiagnostics } from "@/utils/dictation-diagnostics"
import {
  buildAvailableChatModelIds,
  findUnavailableChatModel,
  normalizeChatModelId
} from "@/utils/chat-model-availability"
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
  usePersistenceMode,
  useSlashCommands,
  useMessageCollapse,
  useDeferredComposerInput,
  useMcpToolsControl,
  type CollapsedRange,
  type ModelSortMode
} from "@/hooks/playground"
import { DEFAULT_CHAT_SETTINGS } from "@/types/chat-settings"
import { formatCost } from "@/utils/model-pricing"
import {
  aggregateSessionUsage,
  projectTokenBudget,
  resolveTokenBudgetRisk
} from "./usage-metrics"
import {
  buildConversationSummaryCheckpointPrompt,
  evaluateSummaryCheckpointSuggestion
} from "./conversation-summary-checkpoint"
import { SessionInsightsPanel } from "./SessionInsightsPanel"
import { ModelRecommendationsPanel } from "./ModelRecommendationsPanel"
import { buildSessionInsights } from "./session-insights"
import {
  buildModelRecommendations,
  type ModelRecommendationAction
} from "./model-recommendations"
import {
  createStartupTemplateBundle,
  describeStartupTemplatePrompt,
  inferStartupTemplatePromptSource,
  parseStartupTemplateBundles,
  removeStartupTemplateBundle,
  resolveStartupTemplatePrompt,
  sanitizeStartupTemplateName,
  serializeStartupTemplateBundles,
  upsertStartupTemplateBundle,
  type StartupTemplateBundle
} from "./startup-template-bundles"
import {
  IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
  PLAYGROUND_IMAGE_EVENT_SYNC_DEFAULT_STORAGE_KEY,
  resolveImageGenerationEventSyncMode,
  normalizeImageGenerationEventSyncMode,
  normalizeImageGenerationEventSyncPolicy,
  type ImageGenerationEventSyncPolicy,
  type ImageGenerationEventSyncMode,
  type ImageGenerationRefineMetadata,
  IMAGE_GENERATION_USER_MESSAGE_TYPE,
  type ImageGenerationPromptMode,
  type ImageGenerationRequestSnapshot
} from "@/utils/image-generation-chat"
import {
  buildImagePromptRefineMessages,
  extractImagePromptRefineCandidate
} from "@/utils/image-prompt-refinement"
import {
  createImagePromptDraftFromStrategy,
  deriveImagePromptRawContext,
  getImagePromptStrategies,
  type WeightedImagePromptContextEntry
} from "@/utils/image-prompt-strategies"
import {
  computeResponseDiffPreview,
  type CompareResponseDiff
} from "./compare-response-diff"
import { createComposerPerfTracker } from "@/utils/perf/composer-perf"
import { createRenderPerfTracker } from "@/utils/perf/render-profiler"
import { buildResearchLaunchPath } from "@/routes/route-paths"
import {
  applyAttachedResearchContextEdits,
  resetAttachedResearchContext,
  toChatResearchContext,
  type AttachedResearchContext,
  type ResearchFollowUpTarget
} from "./research-chat-context"

const FOLLOW_UP_RESEARCH_PROMPT_PREFIX = "Follow up on this research:"

type Props = {
  droppedFiles: File[]
  attachedResearchContext?: AttachedResearchContext | null
  attachedResearchContextBaseline?: AttachedResearchContext | null
  attachedResearchContextPinned?: AttachedResearchContext | null
  attachedResearchContextHistory?: AttachedResearchContext[]
  onApplyAttachedResearchContext?: (context: AttachedResearchContext) => void
  onResetAttachedResearchContext?: () => void
  onRemoveAttachedResearchContext?: () => void
  onPinAttachedResearchContext?: () => void
  onUnpinAttachedResearchContext?: () => void
  onRestorePinnedResearchContext?: () => void
  onPinAttachedResearchContextHistory?: (
    context: AttachedResearchContext
  ) => void
  onSelectAttachedResearchContextHistory?: (
    context: AttachedResearchContext
  ) => void
  onPrepareResearchFollowUp?: (target: ResearchFollowUpTarget) => void
}

type DefaultCharacterPreferenceQueryResult = {
  defaultCharacterId: string | null
}

const CONTEXT_FOOTPRINT_THRESHOLD_PERCENT = 40

const estimateTokensFromText = (value: string): number => {
  const normalized = value.trim()
  if (!normalized) return 0
  return Math.max(1, Math.ceil(normalized.length / 4))
}

const buildFollowUpResearchBackground = (
  context: AttachedResearchContext
): ResearchRunFollowUpBackground => {
  const unsupportedClaimCount =
    typeof context.verification_summary?.unsupported_claim_count === "number" &&
    Number.isFinite(context.verification_summary.unsupported_claim_count) &&
    context.verification_summary.unsupported_claim_count >= 0
      ? Math.trunc(context.verification_summary.unsupported_claim_count)
      : 0
  const highTrustCount =
    typeof context.source_trust_summary?.high_trust_count === "number" &&
    Number.isFinite(context.source_trust_summary.high_trust_count) &&
    context.source_trust_summary.high_trust_count >= 0
      ? Math.trunc(context.source_trust_summary.high_trust_count)
      : 0

  return {
    question: context.question || context.query,
    outline: Array.isArray(context.outline)
      ? context.outline
          .filter(
            (section) =>
              typeof section?.title === "string" && section.title.trim().length > 0
          )
          .map((section) => ({ title: section.title.trim() }))
      : [],
    key_claims: Array.isArray(context.key_claims)
      ? context.key_claims
          .map((claim, index) =>
            typeof claim?.text === "string" && claim.text.trim().length > 0
              ? {
                  claim_id: `claim_${index + 1}`,
                  text: claim.text.trim()
                }
              : null
          )
          .filter(
            (claim): claim is { claim_id: string; text: string } => claim !== null
          )
      : [],
    unresolved_questions: Array.isArray(context.unresolved_questions)
      ? context.unresolved_questions.filter(
          (question): question is string =>
            typeof question === "string" && question.trim().length > 0
        )
      : [],
    verification_summary: {
      supported_claim_count: 0,
      unsupported_claim_count: unsupportedClaimCount
    },
    source_trust_summary: {
      high_trust_count: highTrustCount,
      low_trust_count: 0
    }
  }
}

const collectStringSegments = (
  value: unknown,
  segments: string[],
  depth = 0
) => {
  if (depth > 4 || value == null) return
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.length > 0) {
      segments.push(trimmed)
    }
    return
  }
  if (Array.isArray(value)) {
    value.forEach((entry) => collectStringSegments(entry, segments, depth + 1))
    return
  }
  if (typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach((entry) =>
      collectStringSegments(entry, segments, depth + 1)
    )
  }
}

const cloneAttachedResearchContext = (
  context: AttachedResearchContext | null
): AttachedResearchContext | null =>
  context
    ? {
        ...context,
        outline: context.outline.map((section) => ({ ...section })),
        key_claims: context.key_claims.map((claim) => ({ ...claim })),
        unresolved_questions: [...context.unresolved_questions],
        verification_summary: context.verification_summary
          ? { ...context.verification_summary }
          : undefined,
        source_trust_summary: context.source_trust_summary
          ? { ...context.source_trust_summary }
          : undefined
      }
    : null

const stringifyOutline = (context: AttachedResearchContext | null): string =>
  context?.outline.map((section) => section.title).join("\n") ?? ""

const stringifyKeyClaims = (context: AttachedResearchContext | null): string =>
  context?.key_claims.map((claim) => claim.text).join("\n") ?? ""

const stringifyUnresolvedQuestions = (
  context: AttachedResearchContext | null
): string => context?.unresolved_questions.join("\n") ?? ""

export const PlaygroundForm = ({
  droppedFiles,
  attachedResearchContext = null,
  attachedResearchContextBaseline = null,
  attachedResearchContextPinned = null,
  attachedResearchContextHistory = [],
  onApplyAttachedResearchContext,
  onResetAttachedResearchContext,
  onRemoveAttachedResearchContext,
  onPinAttachedResearchContext,
  onUnpinAttachedResearchContext,
  onRestorePinnedResearchContext,
  onPinAttachedResearchContextHistory,
  onSelectAttachedResearchContextHistory,
  onPrepareResearchFollowUp
}: Props) => {
  const { t } = useTranslation(["playground", "common", "option"])
  const notificationApi = useAntdNotification()
  const inputRef = React.useRef<HTMLInputElement>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const processedFilesRef = React.useRef<WeakSet<File>>(new WeakSet())
  const navigate = useNavigate()

  const [typing, setTyping] = React.useState<boolean>(false)
  const [attachedResearchContextDraft, setAttachedResearchContextDraft] =
    React.useState<AttachedResearchContext | null>(null)
  const [followUpResearchModalOpen, setFollowUpResearchModalOpen] =
    React.useState(false)
  const [
    includeAttachedResearchAsBackground,
    setIncludeAttachedResearchAsBackground
  ] = React.useState(Boolean(attachedResearchContext))
  const [pendingAttachmentFollowUp, setPendingAttachmentFollowUp] =
    React.useState<ResearchFollowUpTarget | null>(null)
  const [followUpResearchPending, setFollowUpResearchPending] =
    React.useState(false)
  const followUpResearchPendingRef = React.useRef(false)
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
    addQueuedMessage,
    clearQueuedMessages,
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
    compareAutoDisabledFlag,
    setCompareAutoDisabledFlag,
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
  } = useMcpTools()
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
  const { healthState: audioHealthState, sttHealthState } = useTldwAudioStatus()
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
  const [showQueuedBanner, setShowQueuedBanner] = React.useState(true)
  const [documentGeneratorOpen, setDocumentGeneratorOpen] =
    React.useState(false)
  const [voiceModeSelectorOpen, setVoiceModeSelectorOpen] = React.useState(false)
  const [contextWindowModalOpen, setContextWindowModalOpen] =
    React.useState(false)
  const [contextWindowDraftValue, setContextWindowDraftValue] = React.useState<
    number | undefined
  >(undefined)
  const [sessionInsightsOpen, setSessionInsightsOpen] = React.useState(false)
  const [dismissedRecommendationIds, setDismissedRecommendationIds] =
    React.useState<string[]>([])
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
  const [startupTemplateDraftName, setStartupTemplateDraftName] =
    React.useState("")
  const [startupTemplatePreview, setStartupTemplatePreview] =
    React.useState<StartupTemplateBundle | null>(null)
  const [serverPersistenceHintSeen, setServerPersistenceHintSeen] = useStorage(
    "serverPersistenceHintSeen",
    false
  )
  const [showServerPersistenceHint, setShowServerPersistenceHint] =
    React.useState(false)
  const serverSaveInFlightRef = React.useRef(false)
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
    enabled: true
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

  // Ensure compare selection has a sensible default when enabling compare mode
  React.useEffect(() => {
    if (
      compareFeatureEnabled &&
      compareMode &&
      compareSelectedModels.length === 0 &&
      selectedModel
    ) {
      setCompareSelectedModels([selectedModel])
    }
  }, [
    compareFeatureEnabled,
    compareMode,
    compareSelectedModels.length,
    selectedModel,
    setCompareSelectedModels
  ])

  React.useEffect(() => {
    if (!compareFeatureEnabled && compareMode) {
      setCompareMode(false)
    }
  }, [compareFeatureEnabled, compareMode, setCompareMode])

  React.useEffect(() => {
    if (compareAutoDisabledFlag) {
      notificationApi.info({
        message: t(
          "playground:compareDisabledNotice",
          "Compare mode was turned off"
        ),
        description: t(
          "playground:compareDisabledNoticeDesc",
          "The compare feature was disabled. Your model selections are saved."
        ),
        duration: 4
      })
      setCompareAutoDisabledFlag(false)
    }
  }, [compareAutoDisabledFlag, setCompareAutoDisabledFlag, notificationApi, t])

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

  const compareModeActive = compareFeatureEnabled && compareMode
  const compareModelMetaById = React.useMemo(() => {
    return buildCompareModelMetaById((composerModels as any[]) || [])
  }, [composerModels])
  const availableCompareModels = React.useMemo(
    () =>
      ((composerModels as any[]) || [])
        .filter((model) => model?.model)
        .map((model) => ({
          model: String(model.model),
          nickname:
            typeof model.nickname === "string" ? model.nickname : undefined,
          provider:
            typeof model.provider === "string" ? model.provider : undefined
        })),
    [composerModels]
  )
  const compareModelLabelById = React.useMemo(() => {
    return new Map(
      availableCompareModels.map((model) => [
        model.model,
        model.nickname || model.model
      ])
    )
  }, [availableCompareModels])
  const compareSelectedModelLabels = React.useMemo(
    () =>
      compareSelectedModels.map(
        (modelId) => compareModelLabelById.get(modelId) || modelId
      ),
    [compareModelLabelById, compareSelectedModels]
  )
  const compareNeedsMoreModels =
    compareModeActive && compareSelectedModels.length < 2
  const compareModelsSupportCapability = React.useCallback(
    (modelIds: string[], capability: string) => {
      return compareModelsSupportCapabilityCheck(
        modelIds,
        capability,
        compareModelMetaById
      )
    },
    [compareModelMetaById]
  )
  const compareCapabilityIncompatibilities = React.useMemo(() => {
    if (!compareModeActive || compareSelectedModels.length < 2) return []
    return getCompareCapabilityIncompatibilities({
      modelIds: compareSelectedModels,
      modelMetaById: compareModelMetaById,
      labels: {
        vision: t(
          "playground:composer.compareIncompatVision",
          "Mixed vision support"
        ),
        tools: t(
          "playground:composer.compareIncompatTools",
          "Mixed tool support"
        ),
        streaming: t(
          "playground:composer.compareIncompatStreaming",
          "Mixed streaming behavior"
        ),
        context: t(
          "playground:composer.compareIncompatContext",
          "Large context-window differences"
        )
      }
    })
  }, [
    compareModeActive,
    compareModelMetaById,
    compareSelectedModels,
    t
  ])
  const toggleCompareMode = React.useCallback(() => {
    if (!compareFeatureEnabled) {
      return
    }
    const next = !compareModeActive
    setCompareMode(next)
    if (
      next &&
      compareSelectedModels.length === 0 &&
      selectedModel
    ) {
      setCompareSelectedModels([selectedModel])
    }
  }, [
    compareFeatureEnabled,
    compareModeActive,
    compareSelectedModels.length,
    selectedModel,
    setCompareMode,
    setCompareSelectedModels
  ])
  const handleAddCompareModel = React.useCallback(
    (modelId: string) => {
      if (!modelId) return
      if (compareSelectedModels.includes(modelId)) return
      if (compareSelectedModels.length >= compareMaxModels) return
      setCompareSelectedModels([...compareSelectedModels, modelId])
    },
    [
      compareMaxModels,
      compareSelectedModels,
      setCompareSelectedModels
    ]
  )
  const handleRemoveCompareModel = React.useCallback(
    (modelId: string) => {
      if (!modelId) return
      setCompareSelectedModels(
        compareSelectedModels.filter((id) => id !== modelId)
      )
    },
    [compareSelectedModels, setCompareSelectedModels]
  )
  const availableChatModelIds = React.useMemo(
    () => buildAvailableChatModelIds(Array.isArray(composerModels) ? (composerModels as any[]) : []),
    [composerModels]
  )

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

  const sendLabel = React.useMemo(() => {
    if (compareNeedsMoreModels) {
      return t(
        "playground:composer.compareAddModelToSend",
        "Add one more model"
      )
    }
    if (compareModeActive && compareSelectedModels.length > 1) {
      return t("playground:composer.compareSendToModels", "Send to {{count}} models", {
        count: compareSelectedModels.length
      })
    }
    return t("common:send", "Send")
  }, [
    compareModeActive,
    compareNeedsMoreModels,
    compareSelectedModels.length,
    t
  ])

  const promptSummaryLabel = React.useMemo(() => {
    if (selectedSystemPrompt) {
      return t(
        "playground:composer.summary.systemPrompt",
        "System prompt"
      )
    }
    if (selectedQuickPrompt) {
      return t(
        "playground:composer.summary.customPrompt",
        "Custom prompt"
      )
    }
    return t(
      "playground:composer.summary.noPrompt",
      "No prompt"
    )
  }, [selectedQuickPrompt, selectedSystemPrompt, t])
  const currentPresetKey = React.useMemo(
    () =>
      detectCurrentPreset(
        currentChatModelSettings as unknown as ChatModelSettings
      ),
    [currentChatModelSettings]
  )
  const currentPreset = React.useMemo(
    () => getPresetByKey(currentPresetKey),
    [currentPresetKey]
  )
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
          t("playground:composer.presetChanged", "{{preset}} preset applied.", {
            preset: presetLabel
          } as any)
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
  const startupTemplates = React.useMemo(
    () => parseStartupTemplateBundles(startupTemplatesRaw),
    [startupTemplatesRaw]
  )
  const selectedSystemPromptRecord = React.useMemo<Prompt | null>(() => {
    if (!selectedSystemPrompt) return null
    return (
      promptLibrary.find((prompt) => prompt.id === selectedSystemPrompt) || null
    )
  }, [promptLibrary, selectedSystemPrompt])
  const startupTemplateNameFallback = React.useMemo(() => {
    const nameParts = [
      selectedCharacter?.name?.trim(),
      currentPreset && currentPreset.key !== "custom"
        ? t(`playground:presets.${currentPreset.key}.label`, currentPreset.label)
        : null,
      selectedModel
    ].filter((part): part is string => Boolean(part && part.trim().length > 0))
    if (nameParts.length > 0) {
      return sanitizeStartupTemplateName(
        `${nameParts.join(" · ")} template`,
        "New startup template"
      )
    }
    return "New startup template"
  }, [currentPreset, selectedCharacter?.name, selectedModel, t])
  const persistStartupTemplates = React.useCallback(
    (nextTemplates: StartupTemplateBundle[]) => {
      setStartupTemplatesRaw(serializeStartupTemplateBundles(nextTemplates))
    },
    [setStartupTemplatesRaw]
  )
  const handleSaveStartupTemplate = React.useCallback(() => {
    const trimmedSystemPrompt = String(systemPrompt || "").trim()
    const promptSource = inferStartupTemplatePromptSource(
      selectedSystemPromptRecord,
      trimmedSystemPrompt.length > 0
    )
    const templateName = sanitizeStartupTemplateName(
      startupTemplateDraftName,
      startupTemplateNameFallback
    )
    const nextTemplate = createStartupTemplateBundle({
      name: templateName,
      selectedModel,
      systemPrompt: trimmedSystemPrompt,
      selectedSystemPromptId: selectedSystemPrompt || null,
      promptStudioPromptId:
        selectedSystemPromptRecord?.studioPromptId ??
        selectedSystemPromptRecord?.serverId ??
        null,
      promptTitle: selectedSystemPromptRecord?.title || null,
      promptSource,
      presetKey: currentPresetKey,
      character: selectedCharacter || null,
      ragPinnedResults
    })
    const nextTemplates = upsertStartupTemplateBundle(startupTemplates, nextTemplate)
    persistStartupTemplates(nextTemplates)
    setStartupTemplateDraftName(templateName)
    setModeAnnouncement(
      t(
        "playground:composer.startupTemplateSavedNotice",
        "Startup template saved."
      )
    )
  }, [
    currentPresetKey,
    persistStartupTemplates,
    ragPinnedResults,
    selectedCharacter,
    selectedModel,
    selectedSystemPrompt,
    selectedSystemPromptRecord,
    startupTemplateDraftName,
    startupTemplateNameFallback,
    startupTemplates,
    systemPrompt,
    t
  ])
  const handleOpenStartupTemplatePreview = React.useCallback(
    (templateId: string) => {
      const template = startupTemplates.find((entry) => entry.id === templateId) || null
      setStartupTemplatePreview(template)
    },
    [startupTemplates]
  )
  const handleApplyStartupTemplate = React.useCallback(() => {
    if (!startupTemplatePreview) return

    const promptResolution = resolveStartupTemplatePrompt(
      startupTemplatePreview,
      promptLibrary
    )
    const resolvedPromptContent =
      promptResolution.prompt?.content ?? startupTemplatePreview.systemPrompt
    const resolvedPromptId = promptResolution.prompt?.id || null

    if (startupTemplatePreview.selectedModel) {
      setSelectedModel(startupTemplatePreview.selectedModel)
      if (compareModeActive) {
        setCompareSelectedModels([startupTemplatePreview.selectedModel])
      }
    }

    if (resolvedPromptId) {
      setSelectedSystemPrompt(resolvedPromptId)
    } else {
      setSelectedSystemPrompt(undefined)
    }
    setSystemPrompt(resolvedPromptContent)

    const preset = getPresetByKey(startupTemplatePreview.presetKey)
    if (preset && preset.key !== "custom") {
      updateChatModelSettings(preset.settings)
    }

    void setSelectedCharacter(startupTemplatePreview.character || null)
    setRagPinnedResults(startupTemplatePreview.ragPinnedResults || [])
    setStartupTemplatePreview(null)
    setModeAnnouncement(
      t(
        "playground:composer.startupTemplateAppliedNotice",
        "Startup template applied."
      )
    )
  }, [
    compareModeActive,
    promptLibrary,
    setCompareSelectedModels,
    setRagPinnedResults,
    setSelectedCharacter,
    setSelectedModel,
    setSelectedSystemPrompt,
    setSystemPrompt,
    startupTemplatePreview,
    t,
    updateChatModelSettings
  ])
  const handleDeleteStartupTemplate = React.useCallback(
    (templateId: string) => {
      const nextTemplates = removeStartupTemplateBundle(startupTemplates, templateId)
      persistStartupTemplates(nextTemplates)
      if (startupTemplatePreview?.id === templateId) {
        setStartupTemplatePreview(null)
      }
      setModeAnnouncement(
        t(
          "playground:composer.startupTemplateRemovedNotice",
          "Startup template removed."
        )
      )
    },
    [
      persistStartupTemplates,
      startupTemplatePreview?.id,
      startupTemplates,
      t
    ]
  )

  // Enable focus shortcuts (Shift+Esc to focus textarea)
  useFocusShortcuts(textareaRef, true)

  const [pasteLargeTextAsFile] = useStorage("pasteLargeTextAsFile", false)
  const textAreaFocus = React.useCallback(() => {
    const el = textareaRef.current
    if (!el) {
      return
    }
    if (el.selectionStart === el.selectionEnd) {
      const ua =
        typeof navigator !== "undefined" ? navigator.userAgent : ""
      const isMobile =
        /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
          ua
        )
      if (!isMobile) {
        el.focus()
      } else {
        el.blur()
      }
    }
  }, [])

  const form = useSimpleForm({
    initialValues: {
      message: "",
      image: ""
    }
  })
  const { deferredInput: deferredComposerInput } = useDeferredComposerInput(
    form.values.message || ""
  )
  const composerPerfTrackerRef = React.useRef(
    createComposerPerfTracker({
      enabled: Boolean((globalThis as any).__TLDW_CHAT_PERF__)
    })
  )
  const renderPerfTrackerRef = React.useRef(
    createRenderPerfTracker({
      enabled: Boolean((globalThis as any).__TLDW_CHAT_PERF__)
    })
  )
  const markComposerPerf = React.useCallback((label: string) => {
    return composerPerfTrackerRef.current.start(label)
  }, [])
  const onComposerRenderProfile = React.useCallback<React.ProfilerOnRenderCallback>(
    (id, phase, actualDuration, baseDuration, startTime, commitTime) => {
      renderPerfTrackerRef.current.onRender(
        String(id),
        phase,
        actualDuration,
        baseDuration,
        startTime,
        commitTime
      )
    },
    []
  )
  const measureComposerPerf = React.useCallback(
    <T,>(label: string, fn: () => T): T => {
      const end = markComposerPerf(label)
      try {
        return fn()
      } finally {
        end()
      }
    },
    [markComposerPerf]
  )
  const wrapComposerProfile = React.useCallback(
    (id: string, node: React.ReactNode): React.ReactNode => {
      if (!renderPerfTrackerRef.current.isEnabled()) {
        return node
      }
      return (
        <React.Profiler id={id} onRender={onComposerRenderProfile}>
          {node}
        </React.Profiler>
      )
    },
    [onComposerRenderProfile]
  )

  React.useEffect(() => {
    const inputTracker = composerPerfTrackerRef.current
    const renderTracker = renderPerfTrackerRef.current
    if (!inputTracker.isEnabled() || typeof window === "undefined") {
      return
    }
    ;(window as any).__TLDW_CHAT_PERF_SNAPSHOT__ = () => inputTracker.snapshot()
    ;(window as any).__TLDW_CHAT_PERF_CLEAR__ = () => {
      inputTracker.clear()
      renderTracker.clear()
    }
    ;(window as any).__TLDW_CHAT_RENDER_PERF_SNAPSHOT__ = () =>
      renderTracker.snapshot()
    ;(window as any).__TLDW_CHAT_RENDER_PERF_SUMMARY__ = () =>
      renderTracker.summarize()
    ;(window as any).__TLDW_CHAT_RENDER_PERF_CLEAR__ = () =>
      renderTracker.clear()
    return () => {
      delete (window as any).__TLDW_CHAT_PERF_SNAPSHOT__
      delete (window as any).__TLDW_CHAT_PERF_CLEAR__
      delete (window as any).__TLDW_CHAT_RENDER_PERF_SNAPSHOT__
      delete (window as any).__TLDW_CHAT_RENDER_PERF_SUMMARY__
      delete (window as any).__TLDW_CHAT_RENDER_PERF_CLEAR__
    }
  }, [])

  const setFieldValueRef = React.useRef(form.setFieldValue)
  React.useEffect(() => {
    setFieldValueRef.current = form.setFieldValue
  }, [form.setFieldValue])

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

  const restoreMessageValue = React.useCallback(
    (
      value: string,
      metadata?: { wasExpanded?: boolean; collapsedRange?: CollapsedRange | null }
    ) => {
      setFieldValueRef.current("message", value)
      restoreCollapseState(value, metadata)
    },
    [restoreCollapseState]
  )

  const setMessageValue = React.useCallback(
    (
      nextValue: string,
      options?: {
        collapseLarge?: boolean
        forceCollapse?: boolean
        collapsedRange?: CollapsedRange
      }
    ) => {
      form.setFieldValue("message", nextValue)
      if (options?.collapseLarge) {
        collapseLargeMessage(nextValue, {
          force: options?.forceCollapse,
          range: options?.collapsedRange
        })
      }
    },
    [collapseLargeMessage, form.setFieldValue]
  )

  const collapsedDisplayMeta = React.useMemo(() => {
    const message = form.values.message || ""
    if (!message || !collapsedRange) return null
    return getCollapsedDisplayMeta(message, collapsedRange)
  }, [collapsedRange, form.values.message, getCollapsedDisplayMeta])

  const messageDisplayValue = React.useMemo(
    () => {
      const message = form.values.message || ""
      if (!message) return ""
      if (!isMessageCollapsed || !collapsedDisplayMeta) return message
      return collapsedDisplayMeta.display
    },
    [collapsedDisplayMeta, form.values.message, isMessageCollapsed]
  )

  React.useEffect(() => {
    const message = form.values.message || ""
    if (!message || message.length <= PASTED_TEXT_CHAR_LIMIT) {
      setIsMessageCollapsed(false)
      setHasExpandedLargeText(false)
      setCollapsedRange(null)
    }
  }, [form.values.message])

  // Draft persistence - saves/restores message draft to local-only storage
  const { draftSaved } = useDraftPersistence({
    storageKey: "tldw:playgroundChatDraft",
    getValue: () => form.values.message,
    getMetadata: () => ({
      wasExpanded: hasExpandedLargeText,
      collapsedRange: collapsedRange
        ? { start: collapsedRange.start, end: collapsedRange.end }
        : null
    }),
    setValue: (value) => restoreMessageValue(value),
    setValueWithMetadata: restoreMessageValue
  })

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
  const sessionUsageSummary = React.useMemo(
    () => aggregateSessionUsage(messages as any[], selectedModel, resolvedProviderKey),
    [messages, resolvedProviderKey, selectedModel]
  )
  const sessionUsageLabel = React.useMemo(() => {
    const tokenPart = t("playground:tokens.total", "tokens")
    const base = `${sessionUsageSummary.totalTokens.toLocaleString()} ${tokenPart}`
    if (sessionUsageSummary.estimatedCostUsd == null) {
      return base
    }
    return `${base} (${formatCost(sessionUsageSummary.estimatedCostUsd)})`
  }, [sessionUsageSummary.estimatedCostUsd, sessionUsageSummary.totalTokens, t])
  const sessionInsights = React.useMemo(
    () => buildSessionInsights(messages as any[]),
    [messages]
  )
  const projectedBudget = React.useMemo(
    () =>
      projectTokenBudget({
        conversationTokens: conversationTokenCount,
        draftTokens: draftTokenCount,
        maxTokens: resolvedMaxContext
      }),
    [conversationTokenCount, draftTokenCount, resolvedMaxContext]
  )
  const tokenBudgetRisk = React.useMemo(
    () => resolveTokenBudgetRisk(projectedBudget),
    [projectedBudget]
  )
  const tokenBudgetRiskLabel = React.useMemo(() => {
    if (tokenBudgetRisk.level === "critical") {
      return t("playground:tokens.riskCritical", "Critical risk")
    }
    if (tokenBudgetRisk.level === "high") {
      return t("playground:tokens.riskHigh", "High risk")
    }
    if (tokenBudgetRisk.level === "medium") {
      return t("playground:tokens.riskMedium", "Medium risk")
    }
    if (tokenBudgetRisk.level === "low") {
      return t("playground:tokens.riskLow", "Low risk")
    }
    return t("playground:tokens.riskUnknown", "Unknown")
  }, [t, tokenBudgetRisk.level])
  const showTokenBudgetWarning =
    projectedBudget.isOverLimit || projectedBudget.isNearLimit
  const tokenBudgetWarningText = React.useMemo(() => {
    if (!showTokenBudgetWarning) return null
    if (projectedBudget.isOverLimit) {
      return t(
        "playground:tokens.preSendOverLimit",
        "Projected send exceeds the model context window. Consider trimming prompt/context before sending."
      )
    }
    return t(
      "playground:tokens.preSendNearLimit",
      "Projected send is near the context window limit."
    )
  }, [projectedBudget.isOverLimit, showTokenBudgetWarning, t])
  const characterContextTokenEstimate = React.useMemo(() => {
    if (!selectedCharacter) return 0
    const segments: string[] = []
    collectStringSegments(selectedCharacter.name, segments)
    collectStringSegments(selectedCharacter.title, segments)
    collectStringSegments(selectedCharacter.system_prompt, segments)
    collectStringSegments(selectedCharacter.greeting, segments)
    collectStringSegments(selectedCharacter.extensions, segments)
    const unique = Array.from(new Set(segments))
    if (unique.length === 0) return 0
    return unique.reduce(
      (total, segment) => total + estimateTokensFromText(segment),
      0
    )
  }, [selectedCharacter])
  const systemPromptTokenEstimate = React.useMemo(() => {
    const promptSegments = [
      String(systemPrompt || ""),
      String(selectedQuickPrompt || ""),
      String(selectedSystemPrompt || "")
    ]
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0)
    if (promptSegments.length === 0) return 0
    return promptSegments.reduce(
      (total, segment) => total + estimateTokensFromText(segment),
      0
    )
  }, [selectedQuickPrompt, selectedSystemPrompt, systemPrompt])
  const pinnedSourceTokenEstimate = React.useMemo(() => {
    if (!Array.isArray(ragPinnedResults) || ragPinnedResults.length === 0) {
      return 0
    }
    return ragPinnedResults.reduce((total, result) => {
      const snippet =
        typeof result?.snippet === "string" ? result.snippet : ""
      const title = typeof result?.title === "string" ? result.title : ""
      const sourceLine = typeof result?.source === "string" ? result.source : ""
      const payload = [title, snippet, sourceLine].filter(Boolean).join("\n")
      return total + estimateTokensFromText(payload)
    }, 0)
  }, [ragPinnedResults])
  const historyTokenEstimate = React.useMemo(() => {
    if (!Array.isArray(messages) || messages.length === 0) return 0
    return messages.reduce((total, entry) => {
      const text =
        typeof entry?.message === "string" ? entry.message : ""
      return total + estimateTokensFromText(text)
    }, 0)
  }, [messages])
  const summaryCheckpointSuggestion = React.useMemo(
    () =>
      evaluateSummaryCheckpointSuggestion({
        messageCount: messages.length,
        projectedBudget
      }),
    [messages.length, projectedBudget]
  )
  const modelRecommendations = React.useMemo(
    () =>
      measureComposerPerf("derive:model-recommendations", () =>
        buildModelRecommendations({
          draftText: deferredComposerInput,
          selectedModel,
          modelCapabilities,
          webSearch,
          jsonMode: Boolean(currentChatModelSettings.jsonMode),
          hasImageAttachment: Boolean(form.values.image),
          tokenBudgetRiskLevel: tokenBudgetRisk.level,
          sessionInsights
        })
      ),
    [
      currentChatModelSettings.jsonMode,
      deferredComposerInput,
      form.values.image,
      measureComposerPerf,
      modelCapabilities,
      selectedModel,
      sessionInsights,
      tokenBudgetRisk.level,
      webSearch
    ]
  )
  const visibleModelRecommendations = React.useMemo(
    () =>
      modelRecommendations.filter(
        (recommendation) =>
          !dismissedRecommendationIds.includes(recommendation.id)
      ),
    [dismissedRecommendationIds, modelRecommendations]
  )
  React.useEffect(() => {
    setDismissedRecommendationIds((previous) => {
      if (previous.length === 0) return previous
      const availableIds = new Set(
        modelRecommendations.map((recommendation) => recommendation.id)
      )
      const next = previous.filter((id) => availableIds.has(id))
      if (next.length === previous.length) return previous
      return next
    })
  }, [modelRecommendations])
  const contextFootprintRows = React.useMemo(
    () => [
      {
        id: "character",
        label: t("playground:tokens.breakdown.character", "Character + world book"),
        tokens: characterContextTokenEstimate
      },
      {
        id: "prompt",
        label: t("playground:tokens.breakdown.prompt", "System/prompt steering"),
        tokens: systemPromptTokenEstimate
      },
      {
        id: "pinned",
        label: t("playground:tokens.breakdown.pinned", "Pinned sources"),
        tokens: pinnedSourceTokenEstimate
      },
      {
        id: "history",
        label: t("playground:tokens.breakdown.history", "Chat history"),
        tokens: historyTokenEstimate
      },
      {
        id: "draft",
        label: t("playground:tokens.breakdown.draft", "Current draft"),
        tokens: draftTokenCount
      }
    ],
    [
      characterContextTokenEstimate,
      draftTokenCount,
      historyTokenEstimate,
      pinnedSourceTokenEstimate,
      systemPromptTokenEstimate,
      t
    ]
  )
  const nonMessageContextTokenEstimate = React.useMemo(
    () =>
      characterContextTokenEstimate +
      systemPromptTokenEstimate +
      pinnedSourceTokenEstimate,
    [
      characterContextTokenEstimate,
      pinnedSourceTokenEstimate,
      systemPromptTokenEstimate
    ]
  )
  const nonMessageContextPercent = React.useMemo(() => {
    if (
      typeof resolvedMaxContext !== "number" ||
      !Number.isFinite(resolvedMaxContext) ||
      resolvedMaxContext <= 0
    ) {
      return null
    }
    return (nonMessageContextTokenEstimate / resolvedMaxContext) * 100
  }, [nonMessageContextTokenEstimate, resolvedMaxContext])
  const showNonMessageContextWarning =
    typeof nonMessageContextPercent === "number" &&
    nonMessageContextPercent > CONTEXT_FOOTPRINT_THRESHOLD_PERCENT
  const largestContextContributor = React.useMemo(() => {
    return contextFootprintRows
      .filter((entry) => entry.tokens > 0)
      .sort((left, right) => right.tokens - left.tokens)[0]
  }, [contextFootprintRows])
  const contextWindowFormatter = React.useMemo(() => new Intl.NumberFormat(), [])
  const formatContextWindowValue = React.useCallback(
    (value: number | null | undefined) => {
      if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
        return t("common:unknown", "Unknown")
      }
      return contextWindowFormatter.format(Math.round(value))
    },
    [contextWindowFormatter, t]
  )
  const isContextWindowOverrideActive =
    typeof numCtx === "number" && Number.isFinite(numCtx) && numCtx > 0
  const requestedContextWindowOverride = isContextWindowOverrideActive
    ? Math.round(numCtx)
    : null
  const isContextWindowOverrideClamped =
    typeof requestedContextWindowOverride === "number" &&
    typeof modelContextLength === "number" &&
    modelContextLength > 0 &&
    requestedContextWindowOverride > modelContextLength
  const openContextWindowModal = React.useCallback(() => {
    const startingValue =
      typeof numCtx === "number" && Number.isFinite(numCtx) && numCtx > 0
        ? Math.round(numCtx)
        : typeof resolvedMaxContext === "number" &&
            Number.isFinite(resolvedMaxContext) &&
            resolvedMaxContext > 0
          ? Math.round(resolvedMaxContext)
          : undefined
    setContextWindowDraftValue(startingValue)
    setContextWindowModalOpen(true)
  }, [numCtx, resolvedMaxContext])
  const saveContextWindowSetting = React.useCallback(() => {
    if (
      typeof contextWindowDraftValue === "number" &&
      Number.isFinite(contextWindowDraftValue) &&
      contextWindowDraftValue > 0
    ) {
      updateChatModelSetting("numCtx", Math.round(contextWindowDraftValue))
    } else {
      updateChatModelSetting("numCtx", undefined)
    }
    setContextWindowModalOpen(false)
  }, [contextWindowDraftValue, updateChatModelSetting])
  const resetContextWindowSetting = React.useCallback(() => {
    updateChatModelSetting("numCtx", undefined)
    if (
      typeof modelContextLength === "number" &&
      Number.isFinite(modelContextLength) &&
      modelContextLength > 0
    ) {
      setContextWindowDraftValue(Math.round(modelContextLength))
      return
    }
    setContextWindowDraftValue(undefined)
  }, [modelContextLength, updateChatModelSetting])
  const openSessionInsightsModal = React.useCallback(() => {
    setSessionInsightsOpen(true)
  }, [])
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
  const dismissModelRecommendation = React.useCallback((id: string) => {
    setDismissedRecommendationIds((previous) =>
      previous.includes(id) ? previous : [...previous, id]
    )
  }, [])
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

  React.useEffect(() => {
    const next = queuedMessages.length > 0
    setShowQueuedBanner((prev) => (prev === next ? prev : next))
  }, [queuedMessages.length])

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

  const onFileInputChange = React.useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0]

        const isUnsupported = otherUnsupportedTypes.includes(file.type)

        if (isUnsupported) {
          console.error("File type not supported:", file.type)
          return
        }

        const isImage = file.type.startsWith("image/")
        if (isImage) {
          if (chatMode === "rag") {
            notifyImageAttachmentDisabled()
            return
          }
          const base64 = await toBase64(file)
          form.setFieldValue("image", base64)
        } else {
          await handleFileUpload(file)
        }
      }
    },
    [
      chatMode,
      form,
      handleFileUpload,
      notifyImageAttachmentDisabled,
      otherUnsupportedTypes,
      toBase64
    ]
  )

  const onInputChange = React.useCallback(
    async (e: React.ChangeEvent<HTMLInputElement> | File) => {
      if (e instanceof File) {
        const isUnsupported = otherUnsupportedTypes.includes(e.type)

        if (isUnsupported) {
          console.error("File type not supported:", e.type)
          return
        }

        const isImage = e.type.startsWith("image/")
        if (isImage) {
          if (chatMode === "rag") {
            notifyImageAttachmentDisabled()
            return
          }
          const base64 = await toBase64(e)
          form.setFieldValue("image", base64)
        } else {
          await handleFileUpload(e)
        }
      } else {
        if (e.target.files) {
          onFileInputChange(e)
        }
      }
    },
    [
      chatMode,
      form,
      handleFileUpload,
      notifyImageAttachmentDisabled,
      onFileInputChange,
      otherUnsupportedTypes,
      toBase64
    ]
  )

  const syncCollapsedCaret = React.useCallback(
    (options?: {
      message?: string
      range?: CollapsedRange | null
      caret?: number
    }) => {
      if (!isMessageCollapsed) return
      const pendingState = pendingCollapsedStateRef.current
      const message =
        options?.message ?? pendingState?.message ?? form.values.message ?? ""
      const range = options?.range ?? pendingState?.range ?? collapsedRange
      if (!range) return
      if (!message) return
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        const meta = getCollapsedDisplayMeta(message, range)
        const selection =
          lastDisplaySelectionRef.current ??
          (el.selectionStart !== null
            ? {
                start: el.selectionStart ?? 0,
                end: el.selectionEnd ?? el.selectionStart ?? 0
              }
            : null)
        const hasSelection =
          selection ? selection.start !== selection.end : false
        let caret =
          options?.caret ?? pendingState?.caret ?? pendingCaretRef.current
        if (caret === undefined || caret === null) {
          if (selection && hasSelection) {
            const start = Math.max(
              0,
              Math.min(selection.start, meta.display.length)
            )
            const end = Math.max(0, Math.min(selection.end, meta.display.length))
            el.focus()
            el.setSelectionRange(start, end)
            pendingCollapsedStateRef.current = null
            return
          }
          if (selection) {
            const displayCaret = Math.max(
              0,
              Math.min(selection.start, meta.display.length)
            )
            const prefer =
              displayCaret > meta.labelStart && displayCaret < meta.labelEnd
                ? "after"
                : undefined
            caret = getMessageCaretFromDisplay(displayCaret, meta, { prefer })
          } else {
            caret = meta.messageLength
          }
        }
        if (caret > meta.rangeStart && caret < meta.rangeEnd) {
          caret = meta.rangeEnd
        }
        caret = Math.max(0, Math.min(caret, meta.messageLength))
        pendingCaretRef.current = caret
        pendingCollapsedStateRef.current = null
        const displayCaret = getDisplayCaretFromMessage(caret, meta)
        el.focus()
        el.setSelectionRange(displayCaret, displayCaret)
      })
    },
    [
      collapsedRange,
      form.values.message,
      getDisplayCaretFromMessage,
      getCollapsedDisplayMeta,
      isMessageCollapsed,
      textareaRef
    ]
  )

  React.useEffect(() => {
    if (!isMessageCollapsed || !collapsedRange) return
    if (!pendingCollapsedStateRef.current && pendingCaretRef.current === null) {
      const el = textareaRef.current
      if (el) {
        lastDisplaySelectionRef.current = {
          start: el.selectionStart ?? 0,
          end: el.selectionEnd ?? el.selectionStart ?? 0
        }
      }
    }
    syncCollapsedCaret()
  }, [
    collapsedRange,
    form.values.message,
    isMessageCollapsed,
    syncCollapsedCaret
  ])

  const commitCollapsedEdit = React.useCallback(
    (
      nextValue: string,
      nextCaret: number,
      nextRange: CollapsedRange | null
    ) => {
      const shouldCollapse = nextValue.length > PASTED_TEXT_CHAR_LIMIT
      const range = shouldCollapse
        ? normalizeCollapsedRange(
            nextRange ?? { start: 0, end: nextValue.length },
            nextValue.length
          )
        : null
      pendingCaretRef.current = nextCaret
      pendingCollapsedStateRef.current = range
        ? { message: nextValue, range, caret: nextCaret }
        : null
      setMessageValue(nextValue, {
        collapseLarge: shouldCollapse,
        forceCollapse: shouldCollapse,
        collapsedRange: range ?? undefined
      })
      if (range) {
        syncCollapsedCaret({ message: nextValue, range, caret: nextCaret })
        return
      }
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        el.focus()
        el.setSelectionRange(nextCaret, nextCaret)
      })
    },
    [normalizeCollapsedRange, setMessageValue, syncCollapsedCaret, textareaRef]
  )

  const replaceCollapsedRange = React.useCallback(
    (
      currentValue: string,
      meta: ReturnType<typeof getCollapsedDisplayMeta>,
      editStart: number,
      editEnd: number,
      replacement: string
    ) => {
      const safeStart = Math.max(0, Math.min(editStart, currentValue.length))
      const safeEnd = Math.max(safeStart, Math.min(editEnd, currentValue.length))
      const nextValue =
        currentValue.slice(0, safeStart) +
        replacement +
        currentValue.slice(safeEnd)
      const nextCaret = safeStart + replacement.length
      const overlapsBlock =
        safeStart < meta.rangeEnd && safeEnd > meta.rangeStart
      if (overlapsBlock) {
        commitCollapsedEdit(nextValue, nextCaret, null)
        return
      }
      const delta = replacement.length - (safeEnd - safeStart)
      const nextRange =
        safeEnd <= meta.rangeStart
          ? {
              start: meta.rangeStart + delta,
              end: meta.rangeEnd + delta
            }
          : { start: meta.rangeStart, end: meta.rangeEnd }
      commitCollapsedEdit(nextValue, nextCaret, nextRange)
    },
    [commitCollapsedEdit]
  )

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
  React.useEffect(() => {
    if (droppedFiles.length === 0) return
    let cancelled = false
    const run = async () => {
      for (const file of droppedFiles) {
        if (cancelled) return
        if (processedFilesRef.current.has(file)) continue
        try {
          processedFilesRef.current.add(file)
          await onInputChange(file)
        } catch (error) {
          processedFilesRef.current.delete(file)
          console.error("Failed to process dropped file:", file.name, error)
        }
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [droppedFiles, onInputChange])

  const handleDisconnectedFocus = () => {
    if (!isConnectionReady && !hasShownConnectBanner) {
      setShowConnectBanner(true)
      setHasShownConnectBanner(true)
    }
  }

  // --- ComposerTextarea callback handlers (extracted from inline JSX) ---
  const handleCompositionStart = React.useCallback(() => {
    if (!isFirefoxTarget) {
      setTyping(true)
    }
  }, [])

  const handleCompositionEnd = React.useCallback(() => {
    if (!isFirefoxTarget) {
      setTyping(false)
    }
  }, [])

  const handleTextareaMouseDown = React.useCallback(() => {
    if (isMessageCollapsed) {
      pointerDownRef.current = true
      selectionFromPointerRef.current = true
    }
  }, [isMessageCollapsed])

  const handleTextareaMouseUp = React.useCallback(() => {
    pointerDownRef.current = false
    if (selectionFromPointerRef.current) {
      requestAnimationFrame(() => {
        selectionFromPointerRef.current = false
      })
    }
  }, [])

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

  const handleTextareaChange = React.useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const endPerf = markComposerPerf("input:textarea-change")
      try {
        if (isMessageCollapsed) return
        form.getInputProps("message").onChange(e)
        if (tabMentionsEnabled && textareaRef.current) {
          handleTextChange(
            e.target.value,
            textareaRef.current.selectionStart || 0
          )
        }
      } finally {
        endPerf()
      }
    },
    [
      isMessageCollapsed,
      form,
      tabMentionsEnabled,
      textareaRef,
      handleTextChange,
      markComposerPerf
    ]
  )

  const handleTextareaSelect = React.useCallback(() => {
    const textarea = textareaRef.current
    if (textarea) {
      lastDisplaySelectionRef.current = {
        start: textarea.selectionStart ?? 0,
        end: textarea.selectionEnd ?? textarea.selectionStart ?? 0
      }
    }
    if (isMessageCollapsed && collapsedRange) {
      const message = form.values.message || ""
      if (!message || !textarea) return
      const meta =
        collapsedDisplayMeta ??
        getCollapsedDisplayMeta(message, collapsedRange)
      const selectionStart = textarea.selectionStart ?? meta.labelStart
      const selectionEnd = textarea.selectionEnd ?? selectionStart
      const displayStart = Math.min(selectionStart, selectionEnd)
      const displayEnd = Math.max(selectionStart, selectionEnd)
      const hasSelection = displayStart !== displayEnd
      const selectionTouchesLabel =
        displayStart < meta.labelEnd && displayEnd > meta.labelStart
      const fromPointer = selectionFromPointerRef.current
      selectionFromPointerRef.current = false
      if (hasSelection) {
        pendingCaretRef.current = null
        return
      }
      const caretInsideLabel =
        displayStart > meta.labelStart && displayStart < meta.labelEnd
      if (selectionTouchesLabel && fromPointer && caretInsideLabel) {
        pendingCaretRef.current = meta.rangeEnd
        expandLargeMessage({ force: true })
        return
      }
      const prefer =
        caretInsideLabel &&
        (pendingCaretRef.current ?? meta.rangeEnd) <= meta.rangeStart
          ? "before"
          : "after"
      const caret = getMessageCaretFromDisplay(displayStart, meta, {
        prefer: caretInsideLabel ? prefer : undefined
      })
      pendingCaretRef.current = caret
      if (caretInsideLabel) {
        syncCollapsedCaret({ caret })
      }
      return
    }
    if (tabMentionsEnabled && textareaRef.current) {
      handleTextChange(
        textareaRef.current.value,
        textareaRef.current.selectionStart || 0
      )
    }
  }, [
    textareaRef,
    isMessageCollapsed,
    collapsedRange,
    form.values.message,
    collapsedDisplayMeta,
    getCollapsedDisplayMeta,
    expandLargeMessage,
    getMessageCaretFromDisplay,
    syncCollapsedCaret,
    tabMentionsEnabled,
    handleTextChange
  ])

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
  const submitFormRef = React.useRef<
    (options?: { ignorePinnedResults?: boolean }) => void
  >(() => undefined)

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
    [setMessageValue]
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

  // Match sidepanel textarea sizing: Pro mode gets more space
  const textareaMaxHeight = isProMode ? 160 : 120
  useDynamicTextareaSize(textareaRef, messageDisplayValue, textareaMaxHeight)

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
  const dictationDiagnosticsSnapshotRef = React.useRef<{
    requestedMode: DictationModePreference
    resolvedMode: DictationResolvedMode
    speechAvailable: boolean
    speechUsesServer: boolean
    fallbackReason: DictationErrorClass | null
  }>({
    requestedMode: "auto",
    resolvedMode: "unavailable",
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
    emitDictationDiagnostics({
      surface: "playground",
      kind: "server_error",
      requestedMode: transition.requestedMode,
      resolvedMode: transition.resolvedModeBeforeError,
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
  const { sendWhenEnter, setSendWhenEnter } = useWebUI()
  const dictationStrategy = useDictationStrategy({
    canUseServerStt,
    browserSupportsSpeechRecognition,
    isServerDictating,
    isBrowserDictating: isListening,
    modeOverride: dictationModeOverride,
    autoFallbackEnabled: Boolean(dictationAutoFallbackEnabled)
  })
  const speechAvailable = dictationStrategy.speechAvailable
  const speechUsesServer = dictationStrategy.speechUsesServer
  const dictationToggleIntent = dictationStrategy.toggleIntent
  dictationDiagnosticsSnapshotRef.current = {
    requestedMode: dictationStrategy.requestedMode,
    resolvedMode: dictationStrategy.resolvedMode,
    speechAvailable: dictationStrategy.speechAvailable,
    speechUsesServer: dictationStrategy.speechUsesServer,
    fallbackReason: dictationStrategy.autoFallbackErrorClass
  }
  serverDictationErrorBridgeRef.current = dictationStrategy.recordServerError
  serverDictationSuccessBridgeRef.current = dictationStrategy.recordServerSuccess

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
        t("playground:tooltip.speechToTextDetails", "Uses {{model}} · {{task}} · {{format}}. Configure in Settings → General → Speech-to-Text.", {
          model: sttModelLabel,
          task: sttTaskLabel,
          format: sttFormatLabel
        } as any),
        `Uses ${sttModelLabel} · ${sttTaskLabel} · ${sttFormatLabel}. Configure in Settings -> General -> Speech-to-Text.`
      )
      return (
        (t("playground:tooltip.speechToTextServer", "Dictation via your tldw server") as string) +
        " " +
        speechDetails
      )
    }
    return t("playground:tooltip.speechToTextBrowser", "Dictation via browser speech recognition") as string
  }, [
    dictationStrategy.autoFallbackActive,
    speechAvailable,
    speechUsesServer,
    sttModel,
    sttTask,
    sttResponseFormat,
    t
  ])

  const handleTemplateSelect = React.useCallback(
    (template: { content: string }) => {
      setSystemPrompt(template.content)
      setSelectedSystemPrompt(undefined)
    },
    [setSystemPrompt, setSelectedSystemPrompt]
  )

  React.useEffect(() => {
    if (isListening) {
      setMessageValue(transcript, { collapseLarge: true, forceCollapse: true })
    }
  }, [transcript, isListening, setMessageValue])

  React.useEffect(() => {
    if (!selectedQuickPrompt) {
      return
    }

    const currentMessage = form.values.message || ""
    const promptText = selectedQuickPrompt
    const isFollowUpResearchPrompt =
      promptText === "Follow up on this research" ||
      promptText.startsWith(FOLLOW_UP_RESEARCH_PROMPT_PREFIX)

    const applyOverwrite = () => {
      const word = getVariable(promptText)
      setMessageValue(promptText, { collapseLarge: true })
      if (isFollowUpResearchPrompt) {
        textAreaFocus()
      }
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
      if (isFollowUpResearchPrompt) {
        textAreaFocus()
      }
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
    textAreaFocus,
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

  const buildPinnedMessage = React.useCallback(
    (message: string, options?: { ignorePinnedResults?: boolean }) => {
      if (options?.ignorePinnedResults) return message
      if (fileRetrievalEnabled) return message
      if (!ragPinnedResults || ragPinnedResults.length === 0) return message
      const pinnedText = formatPinnedResults(ragPinnedResults, "markdown")
      return message ? `${message}\n\n${pinnedText}` : pinnedText
    },
    [fileRetrievalEnabled, ragPinnedResults]
  )
  const validateSelectedChatModelsAvailability = React.useCallback(
    (modelsToCheck: string[]) => {
      const unavailableModel = findUnavailableChatModel(
        modelsToCheck,
        availableChatModelIds
      )
      if (!unavailableModel) return true
      form.setFieldError(
        "message",
        t(
          "playground:composer.validationModelUnavailableInline",
          "Selected model is not available on this server. Refresh models or choose a different model."
        )
      )
      return false
    },
    [availableChatModelIds, form, t]
  )

  const resolveAttachedResearchRequestContext = React.useCallback(
    (options?: {
      isImageCommand?: boolean
      compareModeActive?: boolean
      imageGenerationSource?: "slash-command" | "generate-modal" | "message-regen"
    }) => {
      if (!attachedResearchContext) return undefined
      if (options?.isImageCommand) return undefined
      if (options?.compareModeActive) return undefined
      if (options?.imageGenerationSource) return undefined
      return toChatResearchContext(attachedResearchContext)
    },
    [attachedResearchContext]
  )

  const followUpResearchDraftQuery = React.useMemo(
    () => form.values.message.trim(),
    [form.values.message]
  )
  const canLaunchFollowUpResearch =
    !temporaryChat &&
    Boolean(serverChatId) &&
    followUpResearchDraftQuery.length > 0

  const openFollowUpResearchModal = React.useCallback(() => {
    if (!canLaunchFollowUpResearch) return
    setIncludeAttachedResearchAsBackground(Boolean(attachedResearchContext))
    setFollowUpResearchModalOpen(true)
  }, [attachedResearchContext, canLaunchFollowUpResearch])

  const closeFollowUpResearchModal = React.useCallback(() => {
    if (followUpResearchPendingRef.current) return
    setFollowUpResearchModalOpen(false)
  }, [])

  const handleStartFollowUpResearch = React.useCallback(async () => {
    if (followUpResearchPendingRef.current) return
    if (!serverChatId || temporaryChat) return
    const query = form.values.message.trim()
    if (!query) return

    const payload: ResearchRunCreateRequest = {
      query,
      source_policy: "balanced",
      autonomy_mode: "checkpointed",
      chat_handoff: {
        chat_id: serverChatId
      },
      follow_up: {
        question: query,
        background:
          includeAttachedResearchAsBackground && attachedResearchContext
            ? buildFollowUpResearchBackground(attachedResearchContext)
            : undefined
      }
    }

    followUpResearchPendingRef.current = true
    setFollowUpResearchPending(true)
    try {
      await tldwClient.createResearchRun(payload)
      void queryClient.invalidateQueries({
        queryKey: ["playground:chat-linked-research-runs", serverChatId]
      })
      setFollowUpResearchModalOpen(false)
      notificationApi.success({
        message: t(
          "playground:actions.followUpResearchStarted",
          "Follow-up research started."
        )
      })
    } catch (error) {
      notificationApi.error({
        message: t(
          "playground:actions.followUpResearchFailed",
          "Unable to start follow-up research."
        ),
        description: error instanceof Error ? error.message : undefined
      })
    } finally {
      followUpResearchPendingRef.current = false
      setFollowUpResearchPending(false)
    }
  }, [
    attachedResearchContext,
    form.values.message,
    includeAttachedResearchAsBackground,
    notificationApi,
    queryClient,
    serverChatId,
    t,
    temporaryChat
  ])

  const submitForm = (options?: { ignorePinnedResults?: boolean }) => {
    form.onSubmit(async (value) => {
      const intent = resolveSubmissionIntent(value.message)
      if (intent.handled && !intent.invalidImageCommand) {
        form.setFieldValue("message", intent.message)
      }
      if (intent.invalidImageCommand) {
        notificationApi.error({
          message: t("error", { defaultValue: "Error" }),
          description: intent.imageCommandMissingProvider
            ? t(
                "imageCommand.missingProvider",
                "Pick an Image provider in More tools or use /generate-image:<provider> <prompt>."
              )
            : t(
                "imageCommand.invalidUsage",
                "Use /generate-image:<provider> <prompt>."
              )
        })
        return
      }
      const nextMessage = intent.message
      const combinedMessage = intent.isImageCommand
        ? nextMessage
        : buildPinnedMessage(nextMessage, options)
      const trimmed = combinedMessage.trim()
      if (
        !intent.isImageCommand &&
        trimmed.length === 0 &&
        value.image.length === 0 &&
        selectedDocuments.length === 0 &&
        uploadedFiles.length === 0
      ) {
        return
      }
      if (!isConnectionReady) {
        addQueuedMessage({
          message: trimmed,
          image: value.image
        })
        form.reset()
        clearSelectedDocuments()
        clearUploadedFiles()
        return
      }
      const defaultEM = await defaultEmbeddingModelForRag()
      if (!intent.isImageCommand) {
        if (!compareModeActive) {
          const normalizedSelectedModel = normalizeChatModelId(selectedModel)
          if (!normalizedSelectedModel) {
            form.setFieldError("message", t("formError.noModel"))
            return
          }
          if (!validateSelectedChatModelsAvailability([normalizedSelectedModel])) {
            return
          }
        } else if (
          !compareSelectedModels ||
          compareSelectedModels.length < 2
        ) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareMinModelsInline",
              "Select at least two models for Compare mode."
            )
          )
          return
        } else if (
          !validateSelectedChatModelsAvailability(compareSelectedModels)
        ) {
          return
        }
        if (
          compareModeActive &&
          value.image.length > 0 &&
          !compareModelsSupportCapability(compareSelectedModels, "vision")
        ) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareVisionInline",
              "One or more selected compare models do not support image input."
            )
          )
          return
        }
      }

      if (!intent.isImageCommand && webSearch) {
        const simpleSearch = await getIsSimpleInternetSearch()
        if (!defaultEM && !simpleSearch) {
          form.setFieldError("message", t("formError.noEmbeddingModel"))
          return
        }
      }
      if (intent.isImageCommand && trimmed.length === 0) {
        notificationApi.error({
          message: t("error", { defaultValue: "Error" }),
          description: t(
            "imageCommand.missingPrompt",
            "Image prompt is required."
          )
        })
        return
      }
      form.reset()
      clearSelectedDocuments()
      clearUploadedFiles()
      textAreaFocus()
      const projectedForSubmission = projectTokenBudget({
        conversationTokens: conversationTokenCount,
        draftTokens: estimateTokensForText(trimmed),
        maxTokens: resolvedMaxContext
      })
      if (projectedForSubmission.isOverLimit || projectedForSubmission.isNearLimit) {
        notificationApi.warning({
          message: t("playground:tokens.preSendWarningTitle", "Context budget warning"),
          description: projectedForSubmission.isOverLimit
            ? t(
                "playground:tokens.preSendOverLimit",
                "Projected send exceeds the model context window. Consider trimming prompt/context before sending."
              )
            : t(
                "playground:tokens.preSendNearLimit",
                "Projected send is near the context window limit."
              )
        })
      }
      setLastSubmittedContext(currentContextSnapshot)
      await sendMessage({
        image: intent.isImageCommand ? "" : value.image,
        message: trimmed,
        docs: intent.isImageCommand
          ? []
          : selectedDocuments.map((doc) => ({
              type: "tab",
              tabId: doc.id,
              title: doc.title,
              url: doc.url,
              favIconUrl: doc.favIconUrl
            })),
        imageBackendOverride: intent.isImageCommand
          ? intent.imageBackendOverride
          : undefined,
        userMessageType: intent.isImageCommand
          ? IMAGE_GENERATION_USER_MESSAGE_TYPE
          : undefined,
        assistantMessageType: intent.isImageCommand
          ? IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
          : undefined,
        imageGenerationSource: intent.isImageCommand
          ? "slash-command"
          : undefined,
        researchContext: resolveAttachedResearchRequestContext({
          isImageCommand: intent.isImageCommand,
          compareModeActive
        })
      })
    })()
  }
  React.useEffect(() => {
    submitFormRef.current = submitForm
  }, [submitForm])

  const submitFormFromQueued = (message: string, image: string) => {
    if (!isConnectionReady) {
      return
    }
    form.onSubmit(async () => {
      const intent = resolveSubmissionIntent(message)
      if (intent.invalidImageCommand) {
        notificationApi.error({
          message: t("error", { defaultValue: "Error" }),
          description: intent.imageCommandMissingProvider
            ? t(
                "imageCommand.missingProvider",
                "Pick an Image provider in More tools or use /generate-image:<provider> <prompt>."
              )
            : t(
                "imageCommand.invalidUsage",
                "Use /generate-image:<provider> <prompt>."
              )
        })
        return
      }
      const nextMessage = intent.message
      const combinedMessage = intent.isImageCommand
        ? nextMessage
        : buildPinnedMessage(nextMessage)
      const trimmed = combinedMessage.trim()
      if (
        !intent.isImageCommand &&
        trimmed.length === 0 &&
        image.length === 0 &&
        selectedDocuments.length === 0 &&
        uploadedFiles.length === 0
      ) {
        return
      }
      const defaultEM = await defaultEmbeddingModelForRag()
      if (!intent.isImageCommand) {
        if (!compareModeActive) {
          const normalizedSelectedModel = normalizeChatModelId(selectedModel)
          if (!normalizedSelectedModel) {
            form.setFieldError("message", t("formError.noModel"))
            return
          }
          if (!validateSelectedChatModelsAvailability([normalizedSelectedModel])) {
            return
          }
        } else if (
          !compareSelectedModels ||
          compareSelectedModels.length < 2
        ) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareMinModelsInline",
              "Select at least two models for Compare mode."
            )
          )
          return
        } else if (
          !validateSelectedChatModelsAvailability(compareSelectedModels)
        ) {
          return
        }
        if (
          compareModeActive &&
          image.length > 0 &&
          !compareModelsSupportCapability(compareSelectedModels, "vision")
        ) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareVisionInline",
              "One or more selected compare models do not support image input."
            )
          )
          return
        }
      }
      if (!intent.isImageCommand && webSearch) {
        const simpleSearch = await getIsSimpleInternetSearch()
        if (!defaultEM && !simpleSearch) {
          form.setFieldError("message", t("formError.noEmbeddingModel"))
          return
        }
      }
      if (intent.isImageCommand && trimmed.length === 0) {
        notificationApi.error({
          message: t("error", { defaultValue: "Error" }),
          description: t(
            "imageCommand.missingPrompt",
            "Image prompt is required."
          )
        })
        return
      }
      form.reset()
      clearSelectedDocuments()
      clearUploadedFiles()
      textAreaFocus()
      const projectedForSubmission = projectTokenBudget({
        conversationTokens: conversationTokenCount,
        draftTokens: estimateTokensForText(trimmed),
        maxTokens: resolvedMaxContext
      })
      if (projectedForSubmission.isOverLimit || projectedForSubmission.isNearLimit) {
        notificationApi.warning({
          message: t("playground:tokens.preSendWarningTitle", "Context budget warning"),
          description: projectedForSubmission.isOverLimit
            ? t(
                "playground:tokens.preSendOverLimit",
                "Projected send exceeds the model context window. Consider trimming prompt/context before sending."
              )
            : t(
                "playground:tokens.preSendNearLimit",
                "Projected send is near the context window limit."
              )
        })
      }
      setLastSubmittedContext(currentContextSnapshot)
      await sendMessage({
        image: intent.isImageCommand ? "" : image,
        message: trimmed,
        docs: intent.isImageCommand
          ? []
          : selectedDocuments.map((doc) => ({
              type: "tab",
              tabId: doc.id,
              title: doc.title,
              url: doc.url,
              favIconUrl: doc.favIconUrl
            })),
        imageBackendOverride: intent.isImageCommand
          ? intent.imageBackendOverride
          : undefined,
        userMessageType: intent.isImageCommand
          ? IMAGE_GENERATION_USER_MESSAGE_TYPE
          : undefined,
        assistantMessageType: intent.isImageCommand
          ? IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
          : undefined,
        imageGenerationSource: intent.isImageCommand
          ? "slash-command"
          : undefined,
        researchContext: resolveAttachedResearchRequestContext({
          isImageCommand: intent.isImageCommand,
          compareModeActive
        })
      })
    })()
  }

  const privateChatLocked = temporaryChat && history.length > 0

  const handleToggleTemporaryChat = React.useCallback(
    (next: boolean) => {
      if (isFireFoxPrivateMode) {
        notificationApi.error({
          message: t(
            "common:privateModeSaveErrorTitle",
            "tldw Assistant can't save data"
          ),
          description: t(
            "playground:errors.privateModeDescription",
            "Firefox Private Mode does not support saving chat. Temporary chat is enabled by default. More fixes coming soon."
          )
        })
        return
      }

      const hasExistingHistory = history.length > 0

      if (!next && temporaryChat && hasExistingHistory) {
        notificationApi.warning({
          message: t(
            "playground:composer.privateChatLockedTitle",
            "Private chat is locked"
          ),
          description: t(
            "playground:composer.privateChatLockedBody",
            "Start a new chat to switch back to saved conversations."
          )
        })
        return
      }

      // Show confirmation when enabling temporary mode with existing messages
      if (next && hasExistingHistory) {
        Modal.confirm({
          title: t(
            "playground:composer.tempChatConfirmTitle",
            "Enable temporary mode?"
          ),
          content: t(
            "playground:composer.tempChatConfirmContent",
            "This will clear your current conversation. Messages won't be saved."
          ),
          okText: t("common:confirm", "Confirm"),
          cancelText: t("common:cancel", "Cancel"),
          onOk: () => {
            setTemporaryChat(next)
            clearChat()
            const modeLabel = getPersistenceModeLabel(
              t,
              next,
              isConnectionReady,
              serverChatId
            )
            notificationApi.info({
              message: modeLabel,
              placement: "bottomRight",
              duration: 2.5
            })
          }
        })
        return
      }

      // No confirmation needed when disabling temporary mode or no existing messages
      setTemporaryChat(next)
      if (hasExistingHistory) {
        clearChat()
      }

      const modeLabel = getPersistenceModeLabel(
        t,
        next,
        isConnectionReady,
        serverChatId
      )

      notificationApi.info({
        message: modeLabel,
        placement: "bottomRight",
        duration: 2.5
      })
    },
    [
      clearChat,
      history.length,
      isConnectionReady,
      notificationApi,
      serverChatId,
      setTemporaryChat,
      t,
      temporaryChat
    ]
  )

  const handleSaveChatToServer = React.useCallback(async () => {
    if (
      !isConnectionReady ||
      temporaryChat ||
      serverChatId ||
      history.length === 0
    ) {
      return
    }
    try {
      await tldwClient.initialize()

      const snapshot = [...history]
      const firstUser = snapshot.find((m) => m.role === "user")
      const fallbackTitle = t(
        "playground:composer.persistence.serverDefaultTitle",
        "Extension chat"
      )
      const titleSource =
        typeof firstUser?.content === "string" &&
        firstUser.content.trim().length > 0
          ? firstUser.content.trim()
          : fallbackTitle
      const title =
        titleSource.length > 80 ? `${titleSource.slice(0, 77)}…` : titleSource

      let characterId: string | number | null =
        (selectedCharacter as any)?.id ?? null

      if (!characterId) {
        const DEFAULT_NAME = "Helpful AI Assistant"
        const normalizeName = (value: unknown) =>
          String(value || "").trim().toLowerCase()
        const findByName = (list: any[]) =>
          (list || []).find(
            (c: any) => normalizeName(c?.name) === normalizeName(DEFAULT_NAME)
          )
        const findDefaultCharacter = async () => {
          try {
            const results = await tldwClient.searchCharacters(DEFAULT_NAME, {
              limit: 50
            })
            const match = findByName(results)
            if (match) return match
          } catch {}
          try {
            const results = await tldwClient.listCharacters({ limit: 200 })
            const match = findByName(results)
            if (match) return match
          } catch {}
          return null
        }
        try {
          let target = await findDefaultCharacter()
          if (!target) {
            try {
              target = await tldwClient.createCharacter({
                name: DEFAULT_NAME
              })
            } catch (error: any) {
              if (error?.status === 409) {
                target = await findDefaultCharacter()
              } else {
                throw error
              }
            }
          }
          characterId =
            target && typeof target.id !== "undefined" ? target.id : null
        } catch {
          characterId = null
        }
      }

      if (characterId == null) {
        notificationApi.error({
          message: t("error"),
          description: t(
            "playground:composer.persistence.serverCharacterRequired",
            "Unable to find or create a default assistant character on the server. Try again from the Characters page."
          ),
          btn: (
            <Button
              type="primary"
              size="small"
              title={t(
                "playground:composer.persistence.serverCharacterCta",
                "Open Characters workspace"
              ) as string}
              onClick={() => {
                navigate("/characters?from=server-chat-persistence-error")
              }}>
              {t(
                "playground:composer.persistence.serverCharacterCta",
                "Open Characters workspace"
              )}
            </Button>
          ),
          duration: 6
        })
        return
      }

      const created = await tldwClient.createChat({
        title,
        character_id: characterId,
        state: serverChatState || "in-progress",
        source:
          serverChatSource && serverChatSource.trim().length > 0
            ? serverChatSource.trim()
            : undefined
      })
      const rawId = (created as any)?.id ?? (created as any)?.chat_id ?? created
      const cid = rawId != null ? String(rawId) : ""
      if (!cid) {
        throw new Error("Failed to create server chat")
      }
      setServerChatId(cid)
      setServerChatState(
        (created as any)?.state ??
          (created as any)?.conversation_state ??
          serverChatState ??
          "in-progress"
      )
      setServerChatSource((created as any)?.source ?? serverChatSource ?? null)
      setServerChatVersion((created as any)?.version ?? null)
      invalidateServerChatHistory()

      for (const msg of snapshot) {
        const content = (msg.content || "").trim()
        if (!content) continue
        const role =
          msg.role === "system" ||
          msg.role === "assistant" ||
          msg.role === "user"
            ? msg.role
            : "user"
        await tldwClient.addChatMessage(cid, {
          role,
          content
        })
      }

      if (!serverPersistenceHintSeen) {
        notificationApi.success({
          message: t(
            "playground:composer.persistence.serverSavedTitle",
            "Chat now saved on server"
          ),
          description:
            t(
              "playground:composer.persistence.serverSaved",
              "Future messages in this chat will sync to your tldw server."
            ) +
            " " +
            t(
              "playground:composer.persistence.serverBenefits",
              "This keeps a durable record in server history so you can reopen the conversation later, access it from other browsers, and run server-side analytics over your chats."
            )
        })
        setServerPersistenceHintSeen(true)
        setShowServerPersistenceHint(true)
      }
    } catch (e: any) {
      notificationApi.error({
        message: t("error"),
        description: e?.message || t("somethingWentWrong")
      })
    }
  }, [
    history,
    invalidateServerChatHistory,
    isConnectionReady,
    notificationApi,
    selectedCharacter,
    temporaryChat,
    serverChatId,
    setServerChatId,
    navigate,
    serverPersistenceHintSeen,
    setServerPersistenceHintSeen,
    t,
    serverChatState,
    serverChatSource,
    setServerChatState,
    setServerChatSource,
    setServerChatVersion
  ])

  React.useEffect(() => {
    if (
      !isConnectionReady ||
      temporaryChat ||
      serverChatId ||
      history.length === 0
    ) {
      return
    }
    if (serverSaveInFlightRef.current) {
      return
    }
    serverSaveInFlightRef.current = true
    Promise.resolve(handleSaveChatToServer()).finally(() => {
      serverSaveInFlightRef.current = false
    })
  }, [
    handleSaveChatToServer,
    history.length,
    isConnectionReady,
    serverChatId,
    temporaryChat
  ])

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

  const handleToggleWebSearch = React.useCallback(() => {
    setWebSearch(!webSearch)
  }, [setWebSearch, webSearch])
  const handleOpenModelSettings = React.useCallback(() => {
    setOpenModelSettings(true)
  }, [setOpenModelSettings])
  const handleDismissServerPersistenceHint = React.useCallback(() => {
    setShowServerPersistenceHint(false)
  }, [setShowServerPersistenceHint])

  const handleImageUpload = React.useCallback(() => {
    inputRef.current?.click()
  }, [])

  const handleDocumentUpload = React.useCallback(() => {
    fileInputRef.current?.click()
  }, [])

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

  const startBrowserDictation = React.useCallback(() => {
    resetTranscript()
    startListening({
      continuous: true,
      lang: speechToTextLanguage
    })
  }, [resetTranscript, speechToTextLanguage, startListening])

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
      connecting: "🔌",
      listening: "🎤",
      thinking: "💭",
      speaking: "🔊",
      error: "⚠️"
    }[voiceChat.state] || ""

    if (emoji) {
      document.title = `${emoji} ${voiceChatStatusLabel} - Chat`
    }

    return () => {
      document.title = originalTitle
    }
  }, [voiceChatEnabled, voiceChat.state, voiceChatStatusLabel])

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

  const persistChatMetadata = React.useCallback(
    async (patch: Record<string, any>) => {
      if (!serverChatId) return
      try {
        const updated = await tldwClient.updateChat(serverChatId, patch)
        setServerChatState(
          (updated as any)?.state ??
            (updated as any)?.conversation_state ??
            "in-progress"
        )
        setServerChatSource((updated as any)?.source ?? null)
        setServerChatVersion((updated as any)?.version ?? null)
        invalidateServerChatHistory()
      } catch (e: any) {
        notificationApi.error({
          message: t("error", { defaultValue: "Error" }),
          description:
            e?.message ||
            t("somethingWentWrong", { defaultValue: "Something went wrong" })
        })
      }
    },
    [
      invalidateServerChatHistory,
      notificationApi,
      serverChatId,
      setServerChatSource,
      setServerChatState,
      setServerChatVersion,
      t
    ]
  )

  const handleDictationToggle = React.useCallback(() => {
    switch (dictationToggleIntent) {
      case "start_server":
        void startServerDictation()
        break
      case "stop_server":
        stopServerDictation()
        break
      case "start_browser":
        startBrowserDictation()
        break
      case "stop_browser":
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
      speechAvailable: snapshot.speechAvailable,
      speechUsesServer: snapshot.speechUsesServer,
      toggleIntent: dictationToggleIntent,
      fallbackReason: snapshot.fallbackReason
    })
  }, [
    dictationToggleIntent,
    startBrowserDictation,
    startServerDictation,
    stopServerDictation,
    stopSpeechRecognition
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
  const [rawRequestModalOpen, setRawRequestModalOpen] = React.useState(false)
  const [rawRequestSnapshot, setRawRequestSnapshot] =
    React.useState<ChatRequestDebugSnapshot | null>(null)
  const [imageGenerateModalOpen, setImageGenerateModalOpen] =
    React.useState(false)
  const [imageGenerateBackend, setImageGenerateBackend] = React.useState("")
  const [imageGeneratePrompt, setImageGeneratePrompt] = React.useState("")
  const [imageGeneratePromptMode, setImageGeneratePromptMode] =
    React.useState<ImageGenerationPromptMode>("scene")
  const [imageGenerateFormat, setImageGenerateFormat] = React.useState<
    "png" | "jpg" | "webp"
  >("png")
  const [imageGenerateNegativePrompt, setImageGenerateNegativePrompt] =
    React.useState("")
  const [imageGenerateWidth, setImageGenerateWidth] = React.useState<
    number | undefined
  >(undefined)
  const [imageGenerateHeight, setImageGenerateHeight] = React.useState<
    number | undefined
  >(undefined)
  const [imageGenerateSteps, setImageGenerateSteps] = React.useState<
    number | undefined
  >(undefined)
  const [imageGenerateCfgScale, setImageGenerateCfgScale] = React.useState<
    number | undefined
  >(undefined)
  const [imageGenerateSeed, setImageGenerateSeed] = React.useState<
    number | undefined
  >(undefined)
  const [imageGenerateSampler, setImageGenerateSampler] = React.useState("")
  const [imageGenerateModel, setImageGenerateModel] = React.useState("")
  const [imageGenerateExtraParams, setImageGenerateExtraParams] =
    React.useState("")
  const [imageGenerateSyncPolicy, setImageGenerateSyncPolicy] =
    React.useState<ImageGenerationEventSyncPolicy>("inherit")
  const [imagePromptContextBreakdown, setImagePromptContextBreakdown] =
    React.useState<WeightedImagePromptContextEntry[]>([])
  const [imagePromptRefineSubmitting, setImagePromptRefineSubmitting] =
    React.useState(false)
  const [imagePromptRefineBaseline, setImagePromptRefineBaseline] =
    React.useState("")
  const [imagePromptRefineCandidate, setImagePromptRefineCandidate] =
    React.useState("")
  const [imagePromptRefineModel, setImagePromptRefineModel] = React.useState<
    string | null
  >(null)
  const [imagePromptRefineLatencyMs, setImagePromptRefineLatencyMs] =
    React.useState<number | null>(null)
  const [imagePromptRefineDiff, setImagePromptRefineDiff] =
    React.useState<CompareResponseDiff | null>(null)
  const [imageGenerateRefineMetadata, setImageGenerateRefineMetadata] =
    React.useState<ImageGenerationRefineMetadata | undefined>(undefined)
  const [imageGenerateSubmitting, setImageGenerateSubmitting] =
    React.useState(false)
  const { mcpSettingsOpen, setMcpSettingsOpen } = mcpCtrl

  const parseJsonObject = React.useCallback((value?: string) => {
    if (!value || typeof value !== "string") return undefined
    const trimmed = value.trim()
    if (!trimmed) return undefined
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      return undefined
    }
    return undefined
  }, [])

  const imagePromptStrategies = React.useMemo(() => getImagePromptStrategies(), [])
  const imageGenerationCharacterMood = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const candidate = messages[i]
      if (candidate?.isBot && typeof candidate?.moodLabel === "string") {
        return candidate.moodLabel
      }
    }
    return null
  }, [messages])

  const imageGenerateBackendOptions = React.useMemo(() => {
    return imageBackendOptions.filter((option) => option.value.trim().length > 0)
  }, [imageBackendOptions])

  const clearImagePromptRefineCandidate = React.useCallback(() => {
    setImagePromptRefineBaseline("")
    setImagePromptRefineCandidate("")
    setImagePromptRefineModel(null)
    setImagePromptRefineLatencyMs(null)
    setImagePromptRefineDiff(null)
  }, [])

  const clearImagePromptRefineState = React.useCallback(() => {
    clearImagePromptRefineCandidate()
    setImageGenerateRefineMetadata(undefined)
  }, [clearImagePromptRefineCandidate])

  const imageGenerateBusy = imageGenerateSubmitting || imagePromptRefineSubmitting
  const imageEventSyncBaselineMode = React.useMemo(
    () =>
      resolveImageGenerationEventSyncMode({
        requestPolicy: "inherit",
        chatMode: imageEventSyncChatMode,
        globalMode: normalizeImageGenerationEventSyncMode(
          imageEventSyncGlobalDefault,
          "off"
        )
      }),
    [imageEventSyncChatMode, imageEventSyncGlobalDefault]
  )
  const imageGenerateResolvedSyncMode = React.useMemo(
    () =>
      resolveImageGenerationEventSyncMode({
        requestPolicy: imageGenerateSyncPolicy,
        chatMode: imageEventSyncChatMode,
        globalMode: normalizeImageGenerationEventSyncMode(
          imageEventSyncGlobalDefault,
          "off"
        )
      }),
    [
      imageEventSyncChatMode,
      imageEventSyncGlobalDefault,
      imageGenerateSyncPolicy
    ]
  )

  const hydrateImageGenerateSettings = React.useCallback(
    async (backend: string) => {
      if (!backend) return
      const configs = await getImageBackendConfigs().catch(() => ({}))
      const config = normalizeImageBackendConfig(
        resolveImageBackendConfig(backend, configs)
      )
      setImageGenerateFormat(config.format || "png")
      setImageGenerateNegativePrompt(config.negativePrompt || "")
      setImageGenerateWidth(config.width)
      setImageGenerateHeight(config.height)
      setImageGenerateSteps(config.steps)
      setImageGenerateCfgScale(config.cfgScale)
      setImageGenerateSeed(config.seed)
      setImageGenerateSampler(config.sampler || "")
      setImageGenerateModel(config.model || "")
      setImageGenerateExtraParams(
        config.extraParams == null
          ? ""
          : typeof config.extraParams === "string"
            ? config.extraParams
            : JSON.stringify(config.extraParams, null, 2)
      )
    },
    []
  )

  const openImageGenerateModal = React.useCallback(() => {
    setToolsPopoverOpen(false)
    setImagePromptContextBreakdown([])
    clearImagePromptRefineState()
    setImageGenerateSyncPolicy("inherit")
    const defaultBackend =
      imageBackendDefaultTrimmed ||
      imageGenerateBackendOptions[0]?.value ||
      ""
    setImageGenerateBackend(defaultBackend)
    if (!imageGeneratePrompt.trim()) {
      const draftFromComposer = String(form.values.message || "").trim()
      if (draftFromComposer) {
        setImageGeneratePrompt(draftFromComposer)
      }
    }
    if (defaultBackend) {
      void hydrateImageGenerateSettings(defaultBackend)
    }
    setImageGenerateModalOpen(true)
  }, [
    clearImagePromptRefineState,
    form.values.message,
    hydrateImageGenerateSettings,
    imageBackendDefaultTrimmed,
    imageGenerateBackendOptions,
    imageGeneratePrompt
  ])

  const handleCreateImagePromptDraft = React.useCallback(() => {
    const rawContext = deriveImagePromptRawContext({
      messages: messages as Array<{ isBot?: boolean; message?: string }>,
      characterName: selectedCharacter?.name ?? null,
      moodLabel: imageGenerationCharacterMood,
      userIntent: form.values.message || imageGeneratePrompt
    })
    const draftResult = createImagePromptDraftFromStrategy({
      strategyId: imageGeneratePromptMode,
      rawContext
    })
    setImageGeneratePrompt(draftResult.prompt)
    setImagePromptContextBreakdown(draftResult.weightedContext.entries.slice(0, 4))
    clearImagePromptRefineState()
  }, [
    clearImagePromptRefineState,
    form.values.message,
    imageGeneratePromptMode,
    imageGenerationCharacterMood,
    imageGeneratePrompt,
    messages,
    selectedCharacter?.name
  ])

  const handleRefineImagePromptDraft = React.useCallback(async () => {
    const prompt = imageGeneratePrompt.trim()
    if (!prompt) {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:imageGeneration.refinePromptRequired",
          "Add or create a prompt before refining."
        )
      })
      return
    }

    const normalizedModel = String(selectedModel || "")
      .replace(/^tldw:/, "")
      .trim()
    if (!normalizedModel) {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:imageGeneration.refineModelRequired",
          "Select a chat model before using Refine with LLM."
        )
      })
      return
    }

    const strategyLabel =
      imagePromptStrategies.find((entry) => entry.id === imageGeneratePromptMode)
        ?.label || imageGeneratePromptMode
    const contextEntries =
      imagePromptContextBreakdown.length > 0
        ? imagePromptContextBreakdown
        : createImagePromptDraftFromStrategy({
            strategyId: imageGeneratePromptMode,
            rawContext: deriveImagePromptRawContext({
              messages: messages as Array<{ isBot?: boolean; message?: string }>,
              characterName: selectedCharacter?.name ?? null,
              moodLabel: imageGenerationCharacterMood,
              userIntent: form.values.message || imageGeneratePrompt
            })
          }).weightedContext.entries.slice(0, 4)

    setImagePromptRefineSubmitting(true)
    setImageGenerateRefineMetadata(undefined)
    try {
      const startedAt =
        typeof performance !== "undefined" ? performance.now() : Date.now()
      await tldwClient.initialize().catch(() => null)
      const provider = await resolveApiProviderForModel({
        modelId: normalizedModel,
        explicitProvider: currentChatModelSettings.apiProvider
      })
      const completionResponse = await tldwClient.createChatCompletion({
        model: normalizedModel,
        api_provider: provider || undefined,
        temperature: 0.1,
        max_tokens: 320,
        messages: buildImagePromptRefineMessages({
          originalPrompt: prompt,
          strategyLabel,
          backend: imageGenerateBackend,
          contextEntries
        })
      })
      const completionPayload = await completionResponse.json().catch(() => null)
      const candidate = extractImagePromptRefineCandidate(completionPayload)
      if (!candidate) {
        throw new Error(
          t(
            "playground:imageGeneration.refineEmpty",
            "Refiner returned an empty prompt. Try again."
          )
        )
      }
      const elapsedRaw =
        typeof performance !== "undefined" ? performance.now() : Date.now()
      const latencyMs = Math.max(1, Math.round(elapsedRaw - startedAt))
      const diff = computeResponseDiffPreview({
        baseline: prompt,
        candidate,
        maxHighlights: 4
      })
      setImagePromptRefineBaseline(prompt)
      setImagePromptRefineCandidate(candidate)
      setImagePromptRefineModel(normalizedModel)
      setImagePromptRefineLatencyMs(latencyMs)
      setImagePromptRefineDiff(diff)
    } catch (error: any) {
      notificationApi.error({
        message: t(
          "playground:imageGeneration.refineFailedTitle",
          "Prompt refinement failed"
        ),
        description:
          error?.message ||
          t(
            "playground:imageGeneration.refineFailedBody",
            "Could not refine the image prompt."
          )
      })
    } finally {
      setImagePromptRefineSubmitting(false)
    }
  }, [
    currentChatModelSettings.apiProvider,
    form.values.message,
    imageGenerateBackend,
    imageGeneratePrompt,
    imageGeneratePromptMode,
    imageGenerationCharacterMood,
    imagePromptContextBreakdown,
    imagePromptStrategies,
    messages,
    notificationApi,
    selectedCharacter?.name,
    selectedModel,
    t
  ])

  const applyRefinedImagePromptCandidate = React.useCallback(() => {
    const candidate = imagePromptRefineCandidate.trim()
    if (!candidate) return

    if (imagePromptRefineModel && imagePromptRefineLatencyMs != null) {
      const diffStats = imagePromptRefineDiff
        ? {
            baselineSegments: imagePromptRefineDiff.baselineSegments,
            candidateSegments: imagePromptRefineDiff.candidateSegments,
            sharedSegments: imagePromptRefineDiff.sharedSegments,
            overlapRatio: imagePromptRefineDiff.overlapRatio,
            addedCount: imagePromptRefineDiff.addedHighlights.length,
            removedCount: imagePromptRefineDiff.removedHighlights.length
          }
        : {
            baselineSegments: 0,
            candidateSegments: 0,
            sharedSegments: 0,
            overlapRatio: 0,
            addedCount: 0,
            removedCount: 0
          }
      setImageGenerateRefineMetadata({
        model: imagePromptRefineModel,
        latencyMs: imagePromptRefineLatencyMs,
        diffStats
      })
    }

    setImageGeneratePrompt(candidate)
    clearImagePromptRefineCandidate()
  }, [
    clearImagePromptRefineCandidate,
    imagePromptRefineCandidate,
    imagePromptRefineDiff,
    imagePromptRefineLatencyMs,
    imagePromptRefineModel
  ])

  const rejectRefinedImagePromptCandidate = React.useCallback(() => {
    clearImagePromptRefineState()
  }, [clearImagePromptRefineState])

  const submitImageGenerateModal = React.useCallback(async () => {
    const prompt = imageGeneratePrompt.trim()
    const backend = imageGenerateBackend.trim()
    if (!backend) {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:imageGeneration.modalBackendRequired",
          "Select an image backend before generating."
        )
      })
      return
    }
    if (!prompt) {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:imageGeneration.modalPromptRequired",
          "Image prompt is required."
        )
      })
      return
    }
    const parsedExtraParams = parseJsonObject(imageGenerateExtraParams)
    if (imageGenerateExtraParams.trim().length > 0 && !parsedExtraParams) {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:imageGeneration.modalExtraParamsInvalid",
          "Extra params must be valid JSON object."
        )
      })
      return
    }

    const request: Partial<ImageGenerationRequestSnapshot> = {
      prompt,
      backend,
      format: imageGenerateFormat,
      negativePrompt: imageGenerateNegativePrompt.trim() || undefined,
      width:
        typeof imageGenerateWidth === "number" && Number.isFinite(imageGenerateWidth)
          ? imageGenerateWidth
          : undefined,
      height:
        typeof imageGenerateHeight === "number" && Number.isFinite(imageGenerateHeight)
          ? imageGenerateHeight
          : undefined,
      steps:
        typeof imageGenerateSteps === "number" && Number.isFinite(imageGenerateSteps)
          ? imageGenerateSteps
          : undefined,
      cfgScale:
        typeof imageGenerateCfgScale === "number" &&
        Number.isFinite(imageGenerateCfgScale)
          ? imageGenerateCfgScale
          : undefined,
      seed:
        typeof imageGenerateSeed === "number" && Number.isFinite(imageGenerateSeed)
          ? imageGenerateSeed
          : undefined,
      sampler: imageGenerateSampler.trim() || undefined,
      model: imageGenerateModel.trim() || undefined,
      extraParams: parsedExtraParams
    }

    setImageGenerateSubmitting(true)
    try {
      await sendMessage({
        message: prompt,
        image: "",
        docs: [],
        imageBackendOverride: backend,
        userMessageType: IMAGE_GENERATION_USER_MESSAGE_TYPE,
        assistantMessageType: IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
        imageGenerationRequest: request,
        imageGenerationRefine: imageGenerateRefineMetadata,
        imageGenerationPromptMode: imageGeneratePromptMode,
        imageGenerationSource: "generate-modal",
        imageEventSyncPolicy: imageGenerateSyncPolicy,
        researchContext: resolveAttachedResearchRequestContext({
          imageGenerationSource: "generate-modal"
        })
      })
      setImageGenerateModalOpen(false)
      textAreaFocus()
    } finally {
      setImageGenerateSubmitting(false)
    }
  }, [
    imageGenerateBackend,
    imageGenerateCfgScale,
    imageGenerateExtraParams,
    imageGenerateFormat,
    imageGenerateHeight,
    imageGenerateModel,
    imageGenerateNegativePrompt,
    imageGeneratePromptMode,
    imageGenerateSyncPolicy,
    imageGeneratePrompt,
    imageGenerateSampler,
    imageGenerateSeed,
    imageGenerateSteps,
    imageGenerateWidth,
    imageGenerateRefineMetadata,
    notificationApi,
    parseJsonObject,
    sendMessage,
    t,
    textAreaFocus
  ])

  const getComposerModelMeta = React.useCallback(
    (modelId: string) => {
      const normalized = String(modelId || "").replace(/^tldw:/, "")
      const models = Array.isArray(composerModels) ? (composerModels as any[]) : []
      return models.find((entry) => {
        const candidate =
          String(entry?.id || entry?.model || entry?.name || "").replace(
            /^tldw:/,
            ""
          )
        return candidate === normalized
      })
    },
    [composerModels]
  )

  const supportsCapability = React.useCallback(
    (modelId: string, capability: string) => {
      const meta = getComposerModelMeta(modelId)
      const caps = Array.isArray(meta?.capabilities) ? meta.capabilities : []
      return caps.includes(capability)
    },
    [getComposerModelMeta]
  )

  const toPreviewUserContent = React.useCallback(
    (text: string, image: string, modelId: string): ChatMessage["content"] => {
      const cleanedText = text ?? ""
      const trimmedImage = typeof image === "string" ? image.trim() : ""
      const canUseImages = supportsCapability(modelId, "vision")
      if (trimmedImage.length > 0 && canUseImages) {
        return [
          { type: "image_url", image_url: { url: trimmedImage } },
          { type: "text", text: cleanedText }
        ]
      }
      return cleanedText
    },
    [supportsCapability]
  )

  const toPreviewHistoryMessages = React.useCallback(
    (modelId: string, draftMessage: string, draftImage: string): ChatMessage[] => {
      const requestMessages: ChatMessage[] = []
      for (const entry of history || []) {
        if (!entry || typeof entry.content !== "string") continue
        if (entry.role === "system") {
          requestMessages.push({ role: "system", content: entry.content })
          continue
        }
        if (entry.role === "assistant") {
          requestMessages.push({ role: "assistant", content: entry.content })
          continue
        }
        if (entry.role === "user") {
          requestMessages.push({
            role: "user",
            content: toPreviewUserContent(
              entry.content,
              typeof entry.image === "string" ? entry.image : "",
              modelId
            )
          })
        }
      }

      if (draftMessage.trim().length > 0 || draftImage.trim().length > 0) {
        requestMessages.push({
          role: "user",
          content: toPreviewUserContent(draftMessage, draftImage, modelId)
        })
      }

      const trimmedSystemPrompt = String(systemPrompt || "").trim()
      if (
        trimmedSystemPrompt.length > 0 &&
        requestMessages[0]?.role !== "system"
      ) {
        requestMessages.unshift({ role: "system", content: trimmedSystemPrompt })
      }

      return requestMessages
    },
    [history, systemPrompt, toPreviewUserContent]
  )

  const buildNormalPreviewRequest = React.useCallback(
    async (modelId: string, draftMessage: string, draftImage: string) => {
      const normalizedModel = String(modelId || "").replace(/^tldw:/, "").trim()
      const resolvedProvider = await resolveApiProviderForModel({
        modelId: normalizedModel,
        explicitProvider: currentChatModelSettings.apiProvider
      })
      const modelSupportsTools = supportsCapability(normalizedModel, "tools")
      const toolsAllowed =
        modelSupportsTools &&
        hasMcp &&
        mcpHealthState !== "unavailable" &&
        mcpHealthState !== "unhealthy"
      const executableTools = Array.isArray(mcpTools)
        ? mcpTools.filter((tool) => {
            if (!tool || typeof tool !== "object") return false
            if (!("canExecute" in tool)) return true
            return Boolean((tool as Record<string, unknown>).canExecute)
          })
        : []
      const effectiveTools =
        toolsAllowed &&
        toolChoice !== "none" &&
        executableTools.length > 0
          ? executableTools
          : undefined
      const request: ChatCompletionRequest = {
        messages: toPreviewHistoryMessages(normalizedModel, draftMessage, draftImage),
        model: normalizedModel,
        stream: true,
        temperature: currentChatModelSettings.temperature,
        max_tokens: currentChatModelSettings.numPredict,
        top_p: currentChatModelSettings.topP,
        frequency_penalty: currentChatModelSettings.frequencyPenalty,
        presence_penalty: currentChatModelSettings.presencePenalty,
        reasoning_effort:
          currentChatModelSettings.reasoningEffort === "low" ||
          currentChatModelSettings.reasoningEffort === "medium" ||
          currentChatModelSettings.reasoningEffort === "high"
            ? currentChatModelSettings.reasoningEffort
            : undefined,
        tool_choice: effectiveTools ? toolChoice : undefined,
        tools: effectiveTools,
        save_to_db: !temporaryChat && Boolean(serverChatId),
        conversation_id: !temporaryChat && serverChatId ? serverChatId : undefined,
        history_message_limit: currentChatModelSettings.historyMessageLimit,
        history_message_order: currentChatModelSettings.historyMessageOrder,
        slash_command_injection_mode:
          currentChatModelSettings.slashCommandInjectionMode,
        api_provider: resolvedProvider || undefined,
        extra_headers: parseJsonObject(currentChatModelSettings.extraHeaders),
        extra_body: parseJsonObject(currentChatModelSettings.extraBody),
        response_format: currentChatModelSettings.jsonMode
          ? { type: "json_object" }
          : undefined,
        research_context: resolveAttachedResearchRequestContext({
          compareModeActive
        })
      }
      return request
    },
    [
      compareModeActive,
      currentChatModelSettings.apiProvider,
      currentChatModelSettings.extraBody,
      currentChatModelSettings.extraHeaders,
      currentChatModelSettings.frequencyPenalty,
      currentChatModelSettings.historyMessageLimit,
      currentChatModelSettings.historyMessageOrder,
      currentChatModelSettings.jsonMode,
      currentChatModelSettings.numPredict,
      currentChatModelSettings.presencePenalty,
      currentChatModelSettings.reasoningEffort,
      currentChatModelSettings.slashCommandInjectionMode,
      currentChatModelSettings.temperature,
      currentChatModelSettings.topP,
      hasMcp,
      mcpHealthState,
      mcpTools,
      parseJsonObject,
      resolveAttachedResearchRequestContext,
      serverChatId,
      temporaryChat,
      toPreviewHistoryMessages,
      toolChoice,
      supportsCapability
    ]
  )

  const buildCurrentRawRequestSnapshot = React.useCallback(async () => {
    const intent = resolveSubmissionIntent(form.values.message || "")
    const draftMessage = intent.message.trim()
    const draftImage = intent.isImageCommand ? "" : String(form.values.image || "")
    const hasScopedRagMediaIds =
      Array.isArray(ragMediaIds) && ragMediaIds.length > 0
    const shouldUseRag =
      Boolean(selectedKnowledge) || (fileRetrievalEnabled && hasScopedRagMediaIds)
    const hasContextFiles = Array.isArray(contextFiles) && contextFiles.length > 0
    const hasDocs =
      (Array.isArray(selectedDocuments) && selectedDocuments.length > 0) ||
      (Array.isArray(documentContext) && documentContext.length > 0)
    const isCharacterFlow =
      !compareModeActive &&
      !intent.isImageCommand &&
      !hasContextFiles &&
      !hasDocs &&
      !shouldUseRag &&
      Boolean(selectedCharacter?.id)

    if (intent.isImageCommand) {
      const backend =
        intent.imageBackendOverride || imageBackendDefaultTrimmed || "image-generation"
      return {
        endpoint: "/api/v1/files/create",
        method: "POST",
        mode: "non-stream" as const,
        sentAt: new Date().toISOString(),
        body: {
          file_type: "image",
          payload: {
            backend,
            prompt: draftMessage
          },
          export: {
            format: "png",
            mode: "inline",
            async_mode: "sync"
          },
          options: {
            persist: true
          }
        }
      } satisfies ChatRequestDebugSnapshot
    }

    if (isCharacterFlow) {
      const resolvedModel = String(selectedModel || "").replace(/^tldw:/, "").trim()
      const provider = await resolveApiProviderForModel({
        modelId: resolvedModel,
        explicitProvider: currentChatModelSettings.apiProvider
      })
      const chatIdHint = serverChatId || "<new-chat-id>"
      const messagePayload: Record<string, unknown> = {
        role: "user",
        content: draftMessage
      }
      const normalizedImage = String(form.values.image || "")
      if (normalizedImage.startsWith("data:")) {
        const b64 = normalizedImage.includes(",")
          ? normalizedImage.split(",")[1]
          : normalizedImage
        if (b64 && b64.length > 0) {
          messagePayload.image_base64 = b64
        }
      }
      return {
        endpoint: `/api/v1/chats/${chatIdHint}/complete-v2`,
        method: "POST",
        mode: "stream",
        sentAt: new Date().toISOString(),
        body: {
          sequence: [
            !serverChatId
              ? {
                  endpoint: "/api/v1/chats/",
                  method: "POST",
                  body: {
                    character_id: selectedCharacter?.id,
                    state: serverChatState || "in-progress",
                    source: serverChatSource || undefined
                  }
                }
              : null,
            {
              endpoint: `/api/v1/chats/${chatIdHint}/messages`,
              method: "POST",
              body: messagePayload
            },
            {
              endpoint: `/api/v1/chats/${chatIdHint}/complete-v2`,
              method: "POST",
              body: {
                include_character_context: true,
                model: resolvedModel,
                provider: provider || undefined,
                save_to_db: !temporaryChat,
                continue_as_user: messageSteeringMode === "continue_as_user",
                impersonate_user: messageSteeringMode === "impersonate_user",
                force_narrate: Boolean(messageSteeringForceNarrate),
                stream: true
              }
            }
          ].filter(Boolean)
        }
      } satisfies ChatRequestDebugSnapshot
    }

    const modelsForPreview = compareModeActive
      ? Array.from(
          new Set(
            compareSelectedModels.length > 0
              ? compareSelectedModels
              : selectedModel
                ? [selectedModel]
                : []
          )
        )
      : selectedModel
        ? [selectedModel]
        : []
    const limitedModels =
      compareModeActive && compareMaxModels > 0
        ? modelsForPreview.slice(0, compareMaxModels)
        : modelsForPreview

    if (limitedModels.length === 0) {
      return {
        endpoint: "/api/v1/chat/completions",
        method: "POST",
        mode: "stream",
        sentAt: new Date().toISOString(),
        body: {
          error: "No model selected"
        }
      } satisfies ChatRequestDebugSnapshot
    }

    if (limitedModels.length === 1) {
      const request = await buildNormalPreviewRequest(
        limitedModels[0],
        draftMessage,
        draftImage
      )
      return {
        endpoint: "/api/v1/chat/completions",
        method: "POST",
        mode: "stream",
        sentAt: new Date().toISOString(),
        body: request
      } satisfies ChatRequestDebugSnapshot
    }

    const requests = await Promise.all(
      limitedModels.map((modelId) =>
        buildNormalPreviewRequest(modelId, draftMessage, draftImage)
      )
    )
    return {
      endpoint: "/api/v1/chat/completions",
      method: "POST",
      mode: "stream",
      sentAt: new Date().toISOString(),
      body: {
        compare_mode: true,
        requests
      }
    } satisfies ChatRequestDebugSnapshot
  }, [
    buildNormalPreviewRequest,
    compareMaxModels,
    compareModeActive,
    compareSelectedModels,
    contextFiles,
    currentChatModelSettings.apiProvider,
    documentContext,
    fileRetrievalEnabled,
    form.values.image,
    form.values.message,
    imageBackendDefaultTrimmed,
    messageSteeringForceNarrate,
    messageSteeringMode,
    ragMediaIds,
    resolveSubmissionIntent,
    selectedCharacter?.id,
    selectedKnowledge,
    selectedModel,
    selectedDocuments,
    serverChatId,
    serverChatSource,
    serverChatState,
    temporaryChat
  ])

  const rawRequestJson = React.useMemo(
    () =>
      rawRequestSnapshot
        ? JSON.stringify(rawRequestSnapshot.body, null, 2)
        : "",
    [rawRequestSnapshot]
  )

  React.useEffect(() => {
    if (!attachedResearchContext) {
      setAttachedResearchContextDraft(null)
      if (rawRequestModalOpen) {
        setRawRequestModalOpen(false)
      }
      return
    }
    setAttachedResearchContextDraft(cloneAttachedResearchContext(attachedResearchContext))
  }, [attachedResearchContext, rawRequestModalOpen])

  const attachedResearchPreviewSuppressed =
    Boolean(attachedResearchContext) &&
    Boolean(rawRequestSnapshot) &&
    !(rawRequestSnapshot?.body as any)?.research_context

  const applyAttachedResearchDraft = React.useCallback(() => {
    if (!attachedResearchContext || !attachedResearchContextDraft) return
    const nextContext = applyAttachedResearchContextEdits(
      attachedResearchContext,
      attachedResearchContextDraft
    )
    onApplyAttachedResearchContext?.(nextContext)
    setAttachedResearchContextDraft(cloneAttachedResearchContext(nextContext))
  }, [
    attachedResearchContext,
    attachedResearchContextDraft,
    onApplyAttachedResearchContext
  ])

  const handleResetAttachedResearchDraft = React.useCallback(() => {
    const resetContext = resetAttachedResearchContext(
      attachedResearchContextBaseline
    )
    if (!resetContext) return
    onResetAttachedResearchContext?.()
    setAttachedResearchContextDraft(cloneAttachedResearchContext(resetContext))
  }, [attachedResearchContextBaseline, onResetAttachedResearchContext])

  const handleAttachedResearchDraftQuestionChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const nextQuestion = event.target.value
      setAttachedResearchContextDraft((current) =>
        current ? { ...current, question: nextQuestion } : current
      )
    },
    []
  )

  const handleAttachedResearchDraftOutlineChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const nextOutline = event.target.value
        .split("\n")
        .map((title) => ({ title }))
      setAttachedResearchContextDraft((current) =>
        current ? { ...current, outline: nextOutline } : current
      )
    },
    []
  )

  const handleAttachedResearchDraftClaimsChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const nextClaims = event.target.value
        .split("\n")
        .map((text) => ({ text }))
      setAttachedResearchContextDraft((current) =>
        current ? { ...current, key_claims: nextClaims } : current
      )
    },
    []
  )

  const handleAttachedResearchDraftUnresolvedChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const nextQuestions = event.target.value.split("\n")
      setAttachedResearchContextDraft((current) =>
        current
          ? { ...current, unresolved_questions: nextQuestions }
          : current
      )
    },
    []
  )

  const handleAttachedResearchDraftUnsupportedClaimCountChange =
    React.useCallback((value: number | null | undefined) => {
      setAttachedResearchContextDraft((current) =>
        current
          ? {
              ...current,
              verification_summary:
                value == null
                  ? undefined
                  : { unsupported_claim_count: value }
            }
          : current
      )
    }, [])

  const handleAttachedResearchDraftHighTrustCountChange = React.useCallback(
    (value: number | null | undefined) => {
      setAttachedResearchContextDraft((current) =>
        current
          ? {
              ...current,
              source_trust_summary:
                value == null ? undefined : { high_trust_count: value }
            }
          : current
      )
    },
    []
  )

  const refreshRawRequestSnapshot = React.useCallback(async () => {
    try {
      const snapshot = await buildCurrentRawRequestSnapshot()
      setRawRequestSnapshot(snapshot)
      captureChatRequestDebugSnapshot({
        endpoint: snapshot.endpoint,
        method: snapshot.method,
        mode: snapshot.mode,
        body: snapshot.body
      })
    } catch (error) {
      console.error("Failed to build current request preview", error)
      setRawRequestSnapshot(null)
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:tools.rawChatRequestBuildFailed",
          "Failed to generate request preview from current input."
        )
      })
    }
  }, [buildCurrentRawRequestSnapshot, notificationApi, t])

  const openRawRequestModal = React.useCallback(() => {
    setToolsPopoverOpen(false)
    setRawRequestModalOpen(true)
    void refreshRawRequestSnapshot()
  }, [refreshRawRequestSnapshot])

  const copyRawRequestJson = React.useCallback(async () => {
    if (!rawRequestJson) return
    try {
      await navigator.clipboard.writeText(rawRequestJson)
      notificationApi.success({
        message: t("common:copied", "Copied"),
        description: t(
          "playground:tools.rawChatRequestCopied",
          "Copied request JSON to clipboard."
        )
      })
    } catch {
      notificationApi.error({
        message: t("error", { defaultValue: "Error" }),
        description: t(
          "playground:tools.rawChatRequestCopyFailed",
          "Unable to copy request JSON."
        )
      })
    }
  }, [notificationApi, rawRequestJson, t])

  const moreToolsContent = React.useMemo(
    () => (
      <div className="flex w-72 flex-col gap-2 p-1">
        {/* ATTACHMENTS Section */}
        <div className="flex flex-col gap-2">
          <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider px-2">
            {t("playground:tools.attachments", "Attachments")}
          </span>
          <button
            type="button"
            onClick={() => {
              setToolsPopoverOpen(false)
              openImageGenerateModal()
            }}
            className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
          >
            <span>{t("playground:imageGeneration.modalTitle", "Generate image")}</span>
            <WandSparkles className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => openKnowledgePanel("context")}
            className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
          >
            <span>{t("playground:attachments.manageContext", "Manage in Knowledge Panel")}</span>
            <Settings2 className="h-4 w-4" />
          </button>
        </div>

        <div className="border-t border-border my-1" />

        <div className="flex items-center justify-between px-2">
          <span className="text-sm text-text">
            {t("useOCR")}
          </span>
          <Switch
            size="small"
            checked={useOCR}
            onChange={(value) => setUseOCR(value)}
          />
        </div>

        <div className="border-t border-border my-1" />

        {/* WEB SEARCH Section */}
        <div className="flex flex-col gap-2">
          <span className="px-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            {t("playground:tools.webSearch", "Web Search")}
          </span>
          {capabilities?.hasWebSearch ? (
            <>
              <div className="flex items-center justify-between gap-2 px-2">
                <span className="flex items-center gap-2 text-sm text-text">
                  <Globe className="h-4 w-4 text-text-subtle" />
                  {t(
                    "playground:tools.webSearchEnabled",
                    "Enable web search"
                  )}
                </span>
                <Switch
                  size="small"
                  checked={webSearch}
                  onChange={(checked) => setWebSearch(checked)}
                />
              </div>
              <div className="flex items-center justify-between gap-2 px-2">
                <span className="text-sm text-text">
                  {t(
                    "playground:tools.webSearchSimpleMode",
                    "Simple search mode"
                  )}
                </span>
                <Switch
                  size="small"
                  checked={simpleInternetSearch}
                  onChange={(checked) => setSimpleInternetSearch(checked)}
                />
              </div>
              <div className="flex items-center justify-between gap-2 px-2">
                <span className="text-sm text-text">
                  {t(
                    "playground:tools.webSearchDefaultOn",
                    "Default on for new chats"
                  )}
                </span>
                <Switch
                  size="small"
                  checked={defaultInternetSearchOn}
                  onChange={(checked) =>
                    setDefaultInternetSearchOnSetting(checked)
                  }
                />
              </div>
              <button
                type="button"
                onClick={() => {
                  setToolsPopoverOpen(false)
                  navigate("/settings")
                }}
                className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
              >
                <span>
                  {t(
                    "playground:tools.webSearchOpenSettings",
                    "Open web search settings"
                  )}
                </span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </>
          ) : (
            <p className="px-2 text-xs text-text-muted">
              {t(
                "playground:tools.webSearchUnavailable",
                "Web search is unavailable on this server."
              )}
            </p>
          )}
        </div>

        <div className="border-t border-border my-1" />

        {/* ADVANCED Section (collapsible) */}
        <button
          type="button"
          onClick={() => setAdvancedToolsExpanded(!advancedToolsExpanded)}
          className="flex items-center justify-between px-2 py-1 text-[10px] font-semibold uppercase text-text-muted tracking-wider hover:text-text transition"
        >
          <span>{t("playground:tools.advanced", "Advanced")}</span>
          <ChevronRight className={`h-3 w-3 transition-transform ${advancedToolsExpanded ? "rotate-90" : ""}`} />
        </button>

        {advancedToolsExpanded && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1.5 px-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-text">
                  {t(
                    "playground:tools.allowExternalImages",
                    "Load external images in chat"
                  )}
                </span>
                <Switch
                  size="small"
                  checked={allowExternalImages}
                  onChange={(checked) => setAllowExternalImages(checked)}
                />
              </div>
              <p className="text-[11px] text-text-muted">
                {t(
                  "playground:tools.allowExternalImagesHelp",
                  "When off, external image URLs are blocked and shown as links."
                )}
              </p>
            </div>

            <div className="border-t border-border my-1" />

            <div className="flex flex-col gap-1.5 px-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-text">
                  {t("playground:tools.showMoodBadge", "Show mood badge in chat")}
                </span>
                <Switch
                  size="small"
                  checked={showMoodBadge}
                  onChange={(checked) => setShowMoodBadge(checked)}
                />
              </div>
              <p className="text-[11px] text-text-muted">
                {t(
                  "playground:tools.showMoodBadgeHelp",
                  "Shows labels like \"Mood: neutral\" on assistant messages."
                )}
              </p>

              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-text">
                  {t(
                    "playground:tools.showMoodConfidence",
                    "Show mood confidence (%)"
                  )}
                </span>
                <Switch
                  size="small"
                  checked={showMoodConfidence}
                  disabled={!showMoodBadge}
                  onChange={(checked) => setShowMoodConfidence(checked)}
                />
              </div>
              <p className="text-[11px] text-text-muted">
                {t(
                  "playground:tools.showMoodConfidenceHelp",
                  "Adds confidence percentage when available."
                )}
              </p>
            </div>

            <div className="border-t border-border my-1" />

            <div className="flex flex-col gap-1.5 px-2">
              <button
                type="button"
                onClick={openRawRequestModal}
                className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
              >
                <span>
                  {t(
                    "playground:tools.rawChatRequest",
                    "View raw chat JSON"
                  )}
                </span>
                <FileText className="h-4 w-4" />
              </button>
              <p className="text-[11px] text-text-muted">
                {t(
                  "playground:tools.rawChatRequestHelp",
                  "Shows the chat request payload preview generated from your current composer input."
                )}
              </p>
            </div>

            <div className="border-t border-border my-1" />

            {/* Voice Settings */}
            <div className="flex flex-col gap-2 px-2">
              <Tooltip
                title={
                  voiceChatAvailable
                    ? voiceChatStatusLabel
                    : t("playground:voiceChat.unavailableTitle", "Voice chat unavailable")
                }
              >
                <button
                  type="button"
                  onClick={handleVoiceChatToggle}
                  disabled={!voiceChatAvailable || isSending}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    voiceChat.state === "error"
                      ? "text-danger"
                      : voiceChatEnabled && voiceChat.state !== "idle"
                        ? "bg-surface2 text-primaryStrong"
                        : "text-text hover:bg-surface2"
                  }`}
                >
                  <span>{t("playground:tools.voiceSettings", "Voice settings")}</span>
                  <Headphones className="h-4 w-4" />
                </button>
              </Tooltip>
              <div
                className={`flex flex-col gap-2 text-xs ${
                  !voiceChatAvailable ? "pointer-events-none opacity-50" : ""
                }`}
              >
                {voiceChatSettingsFields}
              </div>
            </div>

            {imageProviderControl}

          </div>
        )}

        <div className="border-t border-border my-1" />

        {/* Footer Actions */}
        <Link
          to="/model-playground"
          title={t("playground:actions.workspacePlayground", "Compare models") as string}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
        >
          <span>{t("playground:actions.compareModels", "Compare models")}</span>
          <GitBranch className="h-4 w-4" />
        </Link>
        <button
          type="button"
          onClick={handleClearContext}
          disabled={history.length === 0}
          title={t("tooltip.clearContext") as string}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-danger transition hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40 disabled:text-text-muted disabled:hover:bg-transparent"
        >
          <span>{t("playground:actions.clearConversation", "Clear conversation")}</span>
          <EraserIcon className="h-4 w-4" />
        </button>
      </div>
    ),
    [
      allowExternalImages,
      advancedToolsExpanded,
      capabilities?.hasWebSearch,
      defaultInternetSearchOn,
      handleClearContext,
      openKnowledgePanel,
      openImageGenerateModal,
      handleVoiceChatToggle,
      history.length,
      imageProviderControl,
      isSending,
      navigate,
      openRawRequestModal,
      setAllowExternalImages,
      setDefaultInternetSearchOnSetting,
      setShowMoodBadge,
      setShowMoodConfidence,
      setSimpleInternetSearch,
      setToolsPopoverOpen,
      setWebSearch,
      showMoodBadge,
      showMoodConfidence,
      simpleInternetSearch,
      useOCR,
      setUseOCR,
      t,
      voiceChatAvailable,
      voiceChatEnabled,
      voiceChat.state,
      voiceChatSettingsFields,
      voiceChatStatusLabel,
      webSearch
    ]
  )

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
        isSending
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
        isSending
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

  const stopListening = async () => {
    if (isListening) {
      stopSpeechRecognition()
    }
  }

  const {
    persistenceTooltip,
    focusConnectionCard,
    getPersistenceModeLabel
  } = usePersistenceMode({
    temporaryChat,
    serverChatId,
    isConnectionReady
  })

  const contextItems = React.useMemo<ComposerContextItem[]>(() => {
    const items: ComposerContextItem[] = []
    items.push({
      id: "model",
      label: t("playground:composer.context.model", "Model"),
      value: selectedModel ? modelSummaryLabel : t("common:none", "None"),
      tone: selectedModel ? "active" : "warning",
      onClick: openModelApiSelector
    })
    if (isSessionDegraded) {
      items.push({
        id: "sessionStatus",
        label: t("playground:composer.context.sessionStatus", "Session status"),
        value: connectionStatusLabel,
        tone: "warning",
        onClick: focusConnectionCard
      })
    }

    if (compareModeActive) {
      items.push({
        id: "compare",
        label: t("playground:composer.context.compare", "Compare"),
        value:
          compareSelectedModels.length > 0
            ? String(
                t("playground:composer.context.compareCount", {
                  defaultValue: "{{count}} models",
                  count: compareSelectedModels.length
                } as any)
              )
            : String(t("playground:composer.context.compareOn", "On")),
        tone: "active",
        onClick: () => setOpenModelSettings(true)
      })
    }

    if (currentPreset && currentPreset.key !== "custom") {
      items.push({
        id: "preset",
        label: t("playground:composer.context.preset", "Preset"),
        value: t(
          `playground:presets.${currentPreset.key}.label`,
          currentPreset.label
        ),
        tone: "active",
        onClick: () => setOpenModelSettings(true)
      })
    }

    if (selectedCharacter?.name) {
      items.push({
        id: "character",
        label: t("playground:composer.context.character", "Character"),
        value: characterPendingApply
          ? t(
              "playground:composer.context.characterNextTurn",
              "{{name}} (next turn)",
              { name: selectedCharacter.name } as any
            )
          : selectedCharacter.name,
        tone: "active",
        onClick: () => setOpenActorSettings(true)
      })
    }

    if (contextToolsOpen) {
      items.push({
        id: "knowledge",
        label: t("playground:composer.context.knowledge", "Knowledge"),
        value: t("common:open", "Open"),
        tone: "active",
        onClick: () => setContextToolsOpen(false)
      })
    }

    if (ragPinnedResults.length > 0) {
      items.push({
        id: "ragPinned",
        label: t("playground:composer.context.pinnedSources", "Pinned"),
        value: String(
          t("playground:composer.context.pinnedCount", {
            defaultValue: "{{count}} sources",
            count: ragPinnedResults.length
          } as any)
        ),
        tone: "active",
        onClick: () => openKnowledgePanel("search")
      })
    }

    if (webSearch) {
      items.push({
        id: "webSearch",
        label: t("playground:composer.context.webSearch", "Web search"),
        value: t("common:on", "On"),
        tone: "active",
        onClick: handleToggleWebSearch
      })
    }
    if (sessionUsageSummary.totalTokens > 0) {
      items.push({
        id: "sessionUsage",
        label: t("playground:composer.context.session", "Session"),
        value: sessionUsageLabel,
        tone: "neutral",
        onClick: openSessionInsightsModal
      })
    }
    if (
      selectedSystemPrompt ||
      selectedQuickPrompt ||
      String(systemPrompt || "").trim().length > 0
    ) {
      items.push({
        id: "prompt",
        label: t("playground:composer.context.prompt", "Prompt"),
        value: promptSummaryLabel,
        tone: "active"
      })
    }

    if (currentChatModelSettings.jsonMode) {
      items.push({
        id: "json",
        label: t("playground:composer.context.json", "JSON mode"),
        value: t(
          "playground:composer.context.jsonShort",
          "Object responses"
        ),
        tone: "active",
        onClick: () => updateChatModelSetting("jsonMode", undefined)
      })
    }

    if (showTokenBudgetWarning) {
      items.push({
        id: "budget",
        label: t("playground:composer.context.budget", "Budget"),
        value: `${tokenBudgetRiskLabel}${
          projectedBudget.utilizationPercent != null
            ? ` • ${Math.round(projectedBudget.utilizationPercent)}%`
            : ""
        }`,
        tone: "warning",
        onClick: openContextWindowModal
      })
    }
    if (tokenBudgetRisk.level !== "unknown" && !showTokenBudgetWarning) {
      items.push({
        id: "truncationRisk",
        label: t("playground:composer.context.truncationRisk", "Truncation"),
        value: tokenBudgetRiskLabel,
        tone:
          tokenBudgetRisk.level === "high" || tokenBudgetRisk.level === "critical"
            ? "warning"
            : "neutral",
        onClick: openContextWindowModal
      })
    }
    if (nonMessageContextPercent != null) {
      items.push({
        id: "contextMix",
        label: t("playground:composer.context.contextMix", "Context mix"),
        value: t(
          "playground:composer.context.nonMessageShare",
          "{{percent}}% non-message",
          {
            percent: Math.max(0, Math.round(nonMessageContextPercent))
          } as any
        ),
        tone: showNonMessageContextWarning ? "warning" : "neutral",
        onClick: openContextWindowModal
      })
    }

    if (temporaryChat) {
      items.push({
        id: "temporary",
        label: t("playground:composer.context.temporary", "Temporary"),
        value: t("playground:composer.context.notSaved", "Not saved"),
        tone: "warning"
      })
    }

    return items
  }, [
    compareModeActive,
    compareSelectedModels.length,
    connectionStatusLabel,
    contextToolsOpen,
    currentPreset,
    currentChatModelSettings.jsonMode,
    focusConnectionCard,
    handleToggleWebSearch,
    isSessionDegraded,
    modelSummaryLabel,
    openModelApiSelector,
    openKnowledgePanel,
    openContextWindowModal,
    nonMessageContextPercent,
    characterPendingApply,
    promptSummaryLabel,
    tokenBudgetRisk.level,
    tokenBudgetRiskLabel,
    ragPinnedResults.length,
    selectedCharacter?.name,
    selectedModel,
    selectedQuickPrompt,
    selectedSystemPrompt,
    sessionUsageLabel,
    sessionUsageSummary.totalTokens,
    openSessionInsightsModal,
    setContextToolsOpen,
    setOpenModelSettings,
    showTokenBudgetWarning,
    projectedBudget.utilizationPercent,
    showNonMessageContextWarning,
    systemPrompt,
    t,
    temporaryChat,
    updateChatModelSetting
  ])

  const compareHasPromptContext = React.useMemo(
    () =>
      Boolean(selectedSystemPrompt) ||
      Boolean(selectedQuickPrompt) ||
      String(systemPrompt || "").trim().length > 0,
    [selectedQuickPrompt, selectedSystemPrompt, systemPrompt]
  )

  const compareSharedContextLabels = React.useMemo(() => {
    const labels: string[] = []
    if (selectedCharacter?.name) {
      labels.push(
        String(
          t(
            "playground:composer.compareSharedCharacter",
            "Character: {{name}}",
            { name: selectedCharacter.name } as any
          )
        )
      )
    }
    if (compareHasPromptContext) {
      labels.push(
        String(
          t(
            "playground:composer.compareSharedPrompt",
            "Prompt steering enabled"
          )
        )
      )
    }
    if (ragPinnedResults.length > 0) {
      labels.push(
        String(
          t(
            "playground:composer.compareSharedPinned",
            "{{count}} pinned sources",
            { count: ragPinnedResults.length } as any
          )
        )
      )
    }
    if (webSearch) {
      labels.push(
        String(t("playground:composer.compareSharedWebSearch", "Web search on"))
      )
    }
    if (currentChatModelSettings.jsonMode) {
      labels.push(
        String(t("playground:composer.compareSharedJson", "JSON mode on"))
      )
    }
    return labels
  }, [
    compareHasPromptContext,
    currentChatModelSettings.jsonMode,
    ragPinnedResults.length,
    selectedCharacter?.name,
    t,
    webSearch
  ])

  const compareInteroperabilityNotices = React.useMemo(
    () =>
      buildCompareInteroperabilityNotices({
        t,
        characterName: selectedCharacter?.name || null,
        pinnedSourceCount: ragPinnedResults.length,
        webSearch,
        hasPromptContext: compareHasPromptContext,
        jsonMode: Boolean(currentChatModelSettings.jsonMode),
        voiceChatEnabled
      }),
    [
      compareHasPromptContext,
      currentChatModelSettings.jsonMode,
      ragPinnedResults.length,
      selectedCharacter?.name,
      t,
      voiceChatEnabled,
      webSearch
    ]
  )

  const contextConflictWarnings = React.useMemo(
    () => {
      const warnings: Array<{
        id: string
        text: string
        actionLabel?: string
        onAction?: () => void
      }> = []

      const hasCustomPrompt =
        Boolean(selectedSystemPrompt) ||
        Boolean(selectedQuickPrompt) ||
        String(systemPrompt || "").trim().length > 0

      if (selectedCharacter?.name && ragPinnedResults.length > 0) {
        warnings.push({
          id: "character-rag",
          text: t(
            "playground:composer.conflict.characterRag",
            "Character mode and pinned RAG sources are both active. Responses may blend persona and retrieval context."
          ),
          actionLabel: t(
            "playground:composer.conflict.reviewContext",
            "Review context"
          ),
          onAction: () => openKnowledgePanel("search")
        })
      }

      if (selectedCharacter?.name && hasCustomPrompt) {
        warnings.push({
          id: "character-prompt",
          text: t(
            "playground:composer.conflict.characterPrompt",
            "Character mode and custom prompt steering are both active. Verify intended behavior before sending."
          ),
          actionLabel: t(
            "playground:composer.conflict.reviewModes",
            "Review modes"
          ),
          onAction: () => setModeLauncherOpen(true)
        })
      }

      if (compareModeActive && voiceChatEnabled) {
        warnings.push({
          id: "compare-voice",
          text: t(
            "playground:composer.conflict.compareVoice",
            "Compare mode with voice can reduce output parity across models."
          ),
          actionLabel: t(
            "playground:composer.conflict.adjustModes",
            "Adjust modes"
          ),
          onAction: () => setModeLauncherOpen(true)
        })
      }

      if (compareNeedsMoreModels) {
        warnings.push({
          id: "compare-min-models",
          text: t(
            "playground:composer.validationCompareMinModelsInline",
            "Select at least two models for Compare mode."
          ),
          actionLabel: t(
            "playground:composer.conflict.reviewModels",
            "Review models"
          ),
          onAction: () => setOpenModelSettings(true)
        })
      }

      if (compareModeActive && compareCapabilityIncompatibilities.length > 0) {
        warnings.push({
          id: "compare-capability",
          text: t(
            "playground:composer.conflict.compareCapabilities",
            "Compare models have incompatible capabilities: {{details}}. Outputs may not be directly comparable.",
            {
              details: compareCapabilityIncompatibilities.join(", ")
            } as any
          ),
          actionLabel: t(
            "playground:composer.conflict.reviewModels",
            "Review models"
          ),
          onAction: openModelApiSelector
        })
      }

      if (showTokenBudgetWarning && tokenBudgetWarningText) {
        warnings.push({
          id: "token-budget",
          text: tokenBudgetWarningText,
          actionLabel: t(
            "playground:composer.conflict.adjustBudget",
            "Adjust budget"
          ),
          onAction: () => openContextWindowModal()
        })
      }
      if (summaryCheckpointSuggestion.shouldSuggest && messages.length >= 2) {
        warnings.push({
          id: "summary-checkpoint",
          text:
            summaryCheckpointSuggestion.reason === "token-budget"
              ? t(
                  "playground:composer.conflict.summaryCheckpointBudget",
                  "Consider creating a checkpoint summary before your next turn to reduce truncation risk."
                )
              : t(
                  "playground:composer.conflict.summaryCheckpointVolume",
                  "This thread is getting long. A checkpoint summary can preserve key decisions before context is trimmed."
                ),
          actionLabel: t(
            "playground:composer.conflict.createCheckpointSummary",
            "Create checkpoint summary"
          ),
          onAction: insertSummaryCheckpointPrompt
        })
      }
      if (showNonMessageContextWarning) {
        warnings.push({
          id: "context-footprint",
          text: t(
            "playground:composer.conflict.contextFootprint",
            "Non-message context is using {{percent}}% of the context window. Trim character/prompt/source context before sending.",
            {
              percent: Math.round(nonMessageContextPercent || 0)
            } as any
          ),
          actionLabel: largestContextContributor
            ? t(
                "playground:composer.conflict.trimLargest",
                "Trim largest"
              )
            : t("playground:composer.conflict.reviewContext", "Review context"),
          onAction: largestContextContributor
            ? trimLargestContextContributor
            : () => openContextWindowModal()
        })
      }

      return warnings
    },
    [
      compareCapabilityIncompatibilities,
      compareModeActive,
      compareNeedsMoreModels,
      largestContextContributor,
      insertSummaryCheckpointPrompt,
      messages.length,
      nonMessageContextPercent,
      openKnowledgePanel,
      trimLargestContextContributor,
      ragPinnedResults.length,
      selectedCharacter?.name,
      selectedQuickPrompt,
      selectedSystemPrompt,
      openModelApiSelector,
      setOpenModelSettings,
      setModeLauncherOpen,
      showNonMessageContextWarning,
      summaryCheckpointSuggestion.reason,
      summaryCheckpointSuggestion.shouldSuggest,
      showTokenBudgetWarning,
      systemPrompt,
      t,
      tokenBudgetWarningText,
      openContextWindowModal,
      voiceChatEnabled
    ]
  )

  const modeLauncherContent = (
    <div className="flex w-72 flex-col gap-1 p-1">
      <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {t("playground:composer.modes", "Modes")}
      </div>
      <button
        type="button"
        onClick={() => {
          const next = !compareModeActive
          toggleCompareMode()
          setModeAnnouncement(
            next
              ? t(
                  "playground:composer.modeCompareEnabled",
                  "Compare mode enabled."
                )
              : t(
                  "playground:composer.modeCompareDisabled",
                  "Compare mode disabled."
                )
          )
          setModeLauncherOpen(false)
        }}
        disabled={!compareFeatureEnabled}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span>{t("playground:composer.modeCompare", "Compare responses")}</span>
        <span className="text-xs text-text-muted">
          {compareModeActive
            ? t("common:on", "On")
            : t("common:off", "Off")}
        </span>
      </button>
      <button
        type="button"
        onClick={() => {
          setOpenActorSettings(true)
          setModeAnnouncement(
            t(
              "playground:composer.modeCharacterNotice",
              "Character settings opened."
            )
          )
          setModeLauncherOpen(false)
        }}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
      >
        <span>{t("playground:composer.modeCharacter", "Character mode")}</span>
        <span className="truncate text-xs text-text-muted">
          {selectedCharacter?.name
            ? t("playground:composer.modeCharacterActive", "Active: {{name}}", {
                name: selectedCharacter.name
              })
            : t("common:off", "Off")}
        </span>
      </button>
      <button
        type="button"
        onClick={() => {
          const nextOpen = !contextToolsOpen
          toggleKnowledgePanel()
          setModeAnnouncement(
            nextOpen
              ? t(
                  "playground:composer.modeKnowledgeOpened",
                  "Search & Context panel opened."
                )
              : t(
                  "playground:composer.modeKnowledgeClosed",
                  "Search & Context panel closed."
                )
          )
          setModeLauncherOpen(false)
        }}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
      >
        <span>{t("playground:composer.modeKnowledge", "Knowledge panel")}</span>
        <span className="text-xs text-text-muted">
          {contextToolsOpen
            ? t("common:open", "Open")
            : t("common:closed", "Closed")}
        </span>
      </button>
      <button
        type="button"
        onClick={() => {
          handleVoiceChatToggle()
          setModeAnnouncement(
            voiceChatEnabled
              ? t(
                  "playground:composer.modeVoiceDisabled",
                  "Voice mode disabled."
                )
              : t(
                  "playground:composer.modeVoiceEnabled",
                  "Voice mode enabled."
                )
          )
          setModeLauncherOpen(false)
        }}
        disabled={!voiceChatAvailable || isSending}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span>{t("playground:composer.modeVoice", "Voice mode")}</span>
        <span className="text-xs text-text-muted">
          {voiceChatEnabled
            ? t("common:on", "On")
            : t("common:off", "Off")}
        </span>
      </button>
      <button
        type="button"
        onClick={() => {
          if (!capabilities?.hasWebSearch) return
          handleToggleWebSearch()
          setModeAnnouncement(
            webSearch
              ? t(
                  "playground:composer.modeWebSearchDisabled",
                  "Web search disabled."
                )
              : t(
                  "playground:composer.modeWebSearchEnabled",
                  "Web search enabled."
                )
          )
          setModeLauncherOpen(false)
        }}
        disabled={!capabilities?.hasWebSearch}
        className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span>{t("playground:composer.modeWebSearch", "Web search")}</span>
        <span className="text-xs text-text-muted">
          {webSearch
            ? t("common:on", "On")
            : t("common:off", "Off")}
        </span>
      </button>
    </div>
  )

  const modeLauncherButton = (
    <Popover
      trigger="click"
      placement="topLeft"
      content={modeLauncherContent}
      open={modeLauncherOpen}
      onOpenChange={setModeLauncherOpen}
    >
      <TldwButton
        variant="outline"
        size="sm"
        shape="pill"
        ariaLabel={t("playground:composer.modes", "Modes") as string}
        title={t("playground:composer.modes", "Modes") as string}
        className="min-h-[44px]"
      >
        <span className="inline-flex items-center gap-1.5">
          <Settings2 className="h-4 w-4" aria-hidden="true" />
          <span>{t("playground:composer.modes", "Modes")}</span>
        </span>
      </TldwButton>
    </Popover>
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

  const mcpControlContent = (
    <div className="flex w-64 flex-col gap-2 p-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {t("playground:composer.mcpToolsLabel", "MCP tools")}
      </div>
      <div className="text-xs text-text-muted">{mcpCtrl.mcpSummaryLabel}</div>
      <div className="flex flex-col gap-1">
        <div className="text-xs font-semibold text-text-muted">
          {t("playground:composer.toolChoiceLabel", "Tool choice")}
        </div>
        <Radio.Group
          size="small"
          value={toolChoice}
          onChange={(e) => setToolChoice(e.target.value as typeof toolChoice)}
          className="flex flex-wrap gap-1"
          aria-label={t("playground:composer.toolChoiceLabel", "Tool choice")}
          disabled={
            !hasMcp ||
            mcpHealthState === "unhealthy" ||
            mcpToolsLoading ||
            mcpTools.length === 0
          }
        >
          <Radio.Button value="auto">
            {t("playground:composer.toolChoiceAuto", "Auto")}
          </Radio.Button>
          <Radio.Button value="required">
            {t("playground:composer.toolChoiceRequired", "Required")}
          </Radio.Button>
          <Radio.Button value="none">
            {t("playground:composer.toolChoiceNone", "None")}
          </Radio.Button>
        </Radio.Group>
        <div className="text-[11px] text-text-muted">
          {t("playground:composer.toolRunStatus", "Tool run")}: {toolRunStatusLabel}
        </div>
        <button
          type="button"
          onClick={() => {
            mcpCtrl.setMcpPopoverOpen(false)
            setMcpSettingsOpen(true)
          }}
          className="mt-1 inline-flex w-fit items-center gap-1 text-xs font-medium text-primary hover:text-primaryStrong"
        >
          {t("playground:composer.mcpConfigure", "Configure tools")}
        </button>
      </div>
    </div>
  )

  const mcpControlButton = (
    <TldwButton
      variant="outline"
      size="md"
      shape="pill"
      ariaLabel={mcpCtrl.mcpAriaLabel}
      title={mcpCtrl.mcpAriaLabel}
      disabled={!hasMcp || mcpHealthState === "unhealthy"}
      data-testid="mcp-tools-toggle"
      className="gap-1.5 min-h-[44px]"
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="text-[11px] font-semibold">MCP</span>
        <span className="text-[11px] text-text-muted">{mcpCtrl.mcpChoiceLabel}</span>
        {!mcpToolsLoading && hasMcp && mcpTools.length > 0 && (
          <span className="rounded-full bg-surface2 px-1.5 py-0.5 text-[10px] text-text-muted">
            {mcpTools.length}
          </span>
        )}
        <ChevronDown className="h-3.5 w-3.5 text-text-subtle" aria-hidden="true" />
      </span>
    </TldwButton>
  )

  const mcpControl =
    !hasMcp || mcpHealthState === "unhealthy" ? (
      <Tooltip title={mcpCtrl.mcpDisabledReason}>
        <span>{mcpControlButton}</span>
      </Tooltip>
    ) : (
      <Popover
        trigger="click"
        placement="topRight"
        content={mcpControlContent}
        open={mcpCtrl.mcpPopoverOpen}
        onOpenChange={mcpCtrl.setMcpPopoverOpen}
      >
        {mcpControlButton}
      </Popover>
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
    <Popover
      trigger="click"
      placement="topRight"
      content={moreToolsContent}
      overlayClassName="playground-more-tools"
      open={toolsPopoverOpen}
      onOpenChange={setToolsPopoverOpen}>
      <TldwButton
        variant="outline"
        size="sm"
        shape={isProMode ? "rounded" : "pill"}
        iconOnly={!isProMode}
        ariaLabel={t("playground:composer.moreTools", "More tools") as string}
        title={t("playground:composer.moreTools", "More tools") as string}
        data-testid="tools-button">
        {isProMode ? (
          <span>{t("playground:composer.toolsButton", "+Tools")}</span>
        ) : (
          <>
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">
              {t("playground:composer.moreTools", "More tools")}
            </span>
          </>
        )}
      </TldwButton>
    </Popover>
  )

  const imageAttachmentDisabled =
    chatMode === "rag"
      ? t(
          "playground:attachments.imageDisabledBody",
          "Disable Knowledge Search to attach images."
        )
      : null

  const attachmentMenu = React.useMemo(
    () => (
      <div className="flex w-56 flex-col gap-1 p-1">
        <button
          type="button"
          onClick={handleDocumentUpload}
          title={t("tooltip.uploadDocuments") as string}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
        >
          <span className="flex flex-col items-start">
            <span>{t("playground:actions.attachDocument", "Attach document")}</span>
            <span className="text-[10px] text-text-muted">
              {t(
                "playground:actions.attachDocumentHint",
                "PDF/DOCX/TXT/CSV/MD"
              )}
            </span>
          </span>
          <PaperclipIcon className="h-4 w-4" />
        </button>
        <div className="border-t border-border my-1" />
        <button
          type="button"
          onClick={() => openKnowledgePanel("context")}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2"
        >
          <span>{t("playground:attachments.manageContext", "Manage in Knowledge Panel")}</span>
          <Settings2 className="h-4 w-4" />
        </button>
      </div>
    ),
    [
      handleDocumentUpload,
      openKnowledgePanel,
      t
    ]
  )

  const attachmentButton = (
    <div className="inline-flex items-center">
      <Tooltip title={imageAttachmentDisabled || undefined}>
        <span>
          <TldwButton
            variant="outline"
            size={isMobileViewport ? "lg" : "sm"}
            shape={isProMode ? "rounded" : "pill"}
            iconOnly={!isProMode}
            ariaLabel={t("playground:actions.attachImage", "Attach image") as string}
            title={t("playground:actions.attachImage", "Attach image") as string}
            disabled={chatMode === "rag"}
            data-testid="attachment-button"
            onClick={handleImageUpload}
            className="rounded-r-none"
          >
            {isProMode ? (
              <span className="inline-flex items-center gap-1.5">
                <PaperclipIcon className="h-4 w-4" aria-hidden="true" />
                <span>{t("playground:actions.attach", "Attach")}</span>
              </span>
            ) : (
              <>
                <PaperclipIcon className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">
                  {t("playground:actions.attachImage", "Attach image")}
                </span>
              </>
            )}
          </TldwButton>
        </span>
      </Tooltip>
      <Popover
        trigger="click"
        placement="topRight"
        content={attachmentMenu}
        overlayClassName="playground-attachment-menu"
        open={attachmentMenuOpen}
        onOpenChange={setAttachmentMenuOpen}
      >
        <TldwButton
          variant="outline"
          size={isMobileViewport ? "lg" : "sm"}
          shape={isProMode ? "rounded" : "pill"}
          iconOnly
          ariaLabel={t("playground:actions.attachMore", "More attachments") as string}
          title={t("playground:actions.attachMore", "More attachments") as string}
          className="-ml-px rounded-l-none"
        >
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </TldwButton>
      </Popover>
    </div>
  )

  const sendControl = !isSending ? (
    <Space.Compact
      className={`!justify-end !w-auto ${
        isProMode ? "" : "!h-9 !rounded-full !px-3 !text-xs"
      }`}
    >
      <Button
        size={isMobileViewport ? "large" : isProMode ? "middle" : "small"}
        htmlType="submit"
        disabled={isSending || !isConnectionReady || compareNeedsMoreModels}
        className={isMobileViewport ? "min-h-[44px] min-w-[44px]" : undefined}
        title={
          !isConnectionReady
            ? (t(
                "playground:composer.connectToSend",
                "Connect to your tldw server to start chatting."
              ) as string)
            : compareNeedsMoreModels
              ? (t(
                  "playground:composer.validationCompareMinModelsInline",
                  "Select at least two models for Compare mode."
                ) as string)
            : sendWhenEnter
              ? (t("playground:composer.submitAriaEnter", "Send message (Enter)") as string)
              : (t(
                  "playground:composer.submitAriaModEnter",
                  isMac ? "Send message (⌘+Enter)" : "Send message (Ctrl+Enter)"
                ) as string)
        }
        aria-label={
          t("playground:composer.submitAria", "Send message") as string
        }
      >
        <div
          className={`inline-flex items-center ${
            isProMode ? "gap-2" : "gap-1"
          }`}
        >
          {sendWhenEnter ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              className="h-5 w-5"
              viewBox="0 0 24 24">
              <path d="M9 10L4 15 9 20"></path>
              <path d="M20 4v7a4 4 0 01-4 4H4"></path>
            </svg>
          ) : null}
          <span
            className={
              isProMode
                ? ""
                : "text-[11px] font-semibold uppercase tracking-[0.12em]"
            }>
            {sendLabel}
          </span>
        </div>
      </Button>
      <Dropdown
        open={sendMenuOpen}
        onOpenChange={(open) => setSendMenuOpen(open)}
        disabled={isSending || !isConnectionReady || compareNeedsMoreModels}
        trigger={["click"]}
        menu={{
          items: [
            {
              key: 1,
              label: (
                <Checkbox
                  checked={sendWhenEnter}
                  onChange={(e) =>
                    setSendWhenEnter(e.target.checked)
                  }>
                  {t("sendWhenEnter")}
                </Checkbox>
              )
            }
          ]
        }}
      >
        <Button
          size={isMobileViewport ? "large" : isProMode ? "middle" : "small"}
          disabled={isSending || !isConnectionReady || compareNeedsMoreModels}
          className={isMobileViewport ? "min-h-[44px] min-w-[44px]" : undefined}
          aria-label={
            t(
              "playground:composer.sendOptions",
              "Open send options"
            ) as string
          }
          title={
            t(
              "playground:composer.sendOptions",
              "Open send options"
            ) as string
          }
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className={isProMode ? "w-5 h-5" : "w-4 h-4"}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          }
        />
      </Dropdown>
    </Space.Compact>
  ) : (
    <Tooltip
      title={
        t("tooltip.stopStreaming") as string
      }>
      <TldwButton
        variant="outline"
        size={isMobileViewport ? "lg" : "md"}
        iconOnly
        onClick={stopStreamingRequest}
        ariaLabel={t("tooltip.stopStreaming") as string}>
        <StopCircleIcon className="size-5 sm:size-4" />
      </TldwButton>
    </Tooltip>
  )

  const handleLaunchDeepResearch = React.useCallback(() => {
    const trimmedMessage = form.values.message.trim()
    navigate(
      buildResearchLaunchPath(
        trimmedMessage
          ? {
              query: trimmedMessage,
              sourcePolicy: "balanced",
              autonomyMode: "checkpointed",
              autorun: true,
              from: "chat",
              chatId: serverChatId ?? null
            }
          : { from: "chat", chatId: serverChatId ?? null }
      )
    )
  }, [form.values.message, navigate, serverChatId])

  const researchLaunchButton = (
    <>
      <TldwButton
        variant="outline"
        size={isMobileViewport ? "lg" : "sm"}
        shape={isProMode ? "rounded" : "pill"}
        onClick={handleLaunchDeepResearch}
        title={t("playground:actions.deepResearch", "Deep Research") as string}
        ariaLabel={t("playground:actions.deepResearch", "Deep Research") as string}
        className={isProMode ? "" : "whitespace-nowrap"}
      >
        <span className="inline-flex items-center gap-1.5">
          <Search className="h-4 w-4" aria-hidden="true" />
          <span>{t("playground:actions.deepResearch", "Deep Research")}</span>
        </span>
      </TldwButton>
      <TldwButton
        variant="outline"
        size={isMobileViewport ? "lg" : "sm"}
        shape={isProMode ? "rounded" : "pill"}
        onClick={openFollowUpResearchModal}
        disabled={!canLaunchFollowUpResearch || followUpResearchPending}
        title={
          t("playground:actions.followUpResearch", "Follow-up Research") as string
        }
        ariaLabel={
          t("playground:actions.followUpResearch", "Follow-up Research") as string
        }
        className={isProMode ? "" : "whitespace-nowrap"}
      >
        <span className="inline-flex items-center gap-1.5">
          <GitBranch className="h-4 w-4" aria-hidden="true" />
          <span>
            {t("playground:actions.followUpResearch", "Follow-up Research")}
          </span>
        </span>
      </TldwButton>
    </>
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
                  onSubmit={form.onSubmit(async (value) => {
                    stopListening()
                    const intent = resolveSubmissionIntent(value.message)
                    if (intent.handled && !intent.invalidImageCommand) {
                      form.setFieldValue("message", intent.message)
                    }
                    if (intent.invalidImageCommand) {
                      notificationApi.error({
                        message: t("error", { defaultValue: "Error" }),
                        description: intent.imageCommandMissingProvider
                          ? t(
                              "imageCommand.missingProvider",
                              "Pick an Image provider in More tools or use /generate-image:<provider> <prompt>."
                            )
                          : t(
                              "imageCommand.invalidUsage",
                              "Use /generate-image:<provider> <prompt>."
                            )
                      })
                      return
                    }
                    if (!intent.isImageCommand) {
                      if (!compareModeActive) {
                        const normalizedSelectedModel = normalizeChatModelId(selectedModel)
                        if (!normalizedSelectedModel) {
                          form.setFieldError("message", t("formError.noModel"))
                          return
                        }
                        if (!validateSelectedChatModelsAvailability([normalizedSelectedModel])) {
                          return
                        }
                      } else if (
                        !compareSelectedModels ||
                        compareSelectedModels.length < 2
                      ) {
                        form.setFieldError(
                          "message",
                          t(
                            "playground:composer.validationCompareMinModelsInline",
                            "Select at least two models for Compare mode."
                          )
                        )
                        return
                      } else if (
                        !validateSelectedChatModelsAvailability(compareSelectedModels)
                      ) {
                        return
                      }
                      if (
                        value.image.length > 0 &&
                        !compareModelsSupportCapability(compareSelectedModels, "vision")
                      ) {
                        form.setFieldError(
                          "message",
                          t(
                            "playground:composer.validationCompareVisionInline",
                            "One or more selected compare models do not support image input."
                          )
                        )
                        return
                      }
                    }
                    const defaultEM = await defaultEmbeddingModelForRag()

                    if (!intent.isImageCommand && webSearch) {
                      const simpleSearch = await getIsSimpleInternetSearch()
                      if (!defaultEM && !simpleSearch) {
                        form.setFieldError(
                          "message",
                          t("formError.noEmbeddingModel")
                        )
                        return
                      }
                    }
                    if (
                      !intent.isImageCommand &&
                      intent.message.trim().length === 0 &&
                      value.image.length === 0 &&
                      selectedDocuments.length === 0 &&
                      uploadedFiles.length === 0
                    ) {
                      return
                    }
                    if (intent.isImageCommand && intent.message.trim().length === 0) {
                      notificationApi.error({
                        message: t("error", { defaultValue: "Error" }),
                        description: t(
                          "imageCommand.missingPrompt",
                          "Image prompt is required."
                        )
                      })
                      return
                    }
                    form.reset()
                    clearSelectedDocuments()
                    clearUploadedFiles()
                    textAreaFocus()
                    const projectedForSubmission = projectTokenBudget({
                      conversationTokens: conversationTokenCount,
                      draftTokens: estimateTokensForText(intent.message.trim()),
                      maxTokens: resolvedMaxContext
                    })
                    if (projectedForSubmission.isOverLimit || projectedForSubmission.isNearLimit) {
                      notificationApi.warning({
                        message: t("playground:tokens.preSendWarningTitle", "Context budget warning"),
                        description: projectedForSubmission.isOverLimit
                          ? t(
                              "playground:tokens.preSendOverLimit",
                              "Projected send exceeds the model context window. Consider trimming prompt/context before sending."
                            )
                          : t(
                              "playground:tokens.preSendNearLimit",
                              "Projected send is near the context window limit."
                            )
                      })
                    }
                    setLastSubmittedContext(currentContextSnapshot)
                    await sendMessage({
                      image: intent.isImageCommand ? "" : value.image,
                      message: intent.message.trim(),
                      docs: intent.isImageCommand
                        ? []
                        : selectedDocuments.map((doc) => ({
                            type: "tab",
                            tabId: doc.id,
                            title: doc.title,
                            url: doc.url
                          })),
                      imageBackendOverride: intent.isImageCommand
                        ? intent.imageBackendOverride
                        : undefined,
                      userMessageType: intent.isImageCommand
                        ? IMAGE_GENERATION_USER_MESSAGE_TYPE
                        : undefined,
                      assistantMessageType: intent.isImageCommand
                        ? IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
                        : undefined,
                      imageGenerationSource: intent.isImageCommand
                        ? "slash-command"
                        : undefined,
                      researchContext: resolveAttachedResearchRequestContext({
                        isImageCommand: intent.isImageCommand,
                        compareModeActive
                      })
                    })
                  })}
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
                  {attachedResearchContext && (
                      <AttachedResearchContextChip
                        context={attachedResearchContext}
                        pinned={attachedResearchContextPinned}
                        history={attachedResearchContextHistory}
                        onPreview={openRawRequestModal}
                        onRemove={() => onRemoveAttachedResearchContext?.()}
                        onPin={() => onPinAttachedResearchContext?.()}
                        onUnpin={() => onUnpinAttachedResearchContext?.()}
                        onRestorePinned={() => onRestorePinnedResearchContext?.()}
                        onPrepareResearchFollowUp={onPrepareResearchFollowUp}
                        onPinHistory={onPinAttachedResearchContextHistory}
                        onSelectHistory={onSelectAttachedResearchContextHistory}
                      />
                    )}
                    {!attachedResearchContext &&
                    (attachedResearchContextPinned ||
                      attachedResearchContextHistory.length > 0) ? (
                      <div className="mb-2 flex flex-col gap-2">
                        {attachedResearchContextPinned ? (
                          <div
                            data-testid="pinned-research-fallback-card"
                            className="rounded-md border border-border bg-surface2 px-3 py-3 text-xs text-text"
                          >
                            <div className="flex flex-col gap-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium text-text-muted">
                                  {t(
                                    "playground:composer.pinnedResearch",
                                    "Pinned research"
                                  )}
                                </span>
                                <span className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text">
                                  {attachedResearchContextPinned.query}
                                </span>
                              </div>
                              <p className="text-[11px] text-text-muted">
                                {t(
                                  "playground:composer.pinnedResearchFallbackDescription",
                                  "This thread keeps this research as its default context."
                                )}
                              </p>
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => onRestorePinnedResearchContext?.()}
                                  className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                >
                                  {t(
                                    "playground:actions.usePinnedResearchNow",
                                    "Use now"
                                  )}
                                </button>
                                <Link
                                  to={attachedResearchContextPinned.research_url}
                                  className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                >
                                  {t(
                                    "playground:actions.openInResearch",
                                    "Open in Research"
                                  )}
                                </Link>
                                <button
                                  type="button"
                                  onClick={() => onUnpinAttachedResearchContext?.()}
                                  className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                >
                                  {t(
                                    "playground:actions.unpinResearchContext",
                                    "Unpin"
                                  )}
                                </button>
                                {onPrepareResearchFollowUp ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setPendingAttachmentFollowUp({
                                        run_id: attachedResearchContextPinned.run_id,
                                        query: attachedResearchContextPinned.query
                                      })
                                    }
                                    className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                  >
                                    {t("playground:actions.followUp", "Follow up")}
                                  </button>
                                ) : null}
                              </div>
                              {pendingAttachmentFollowUp?.run_id ===
                              attachedResearchContextPinned.run_id ? (
                                <div
                                  data-testid="pinned-research-follow-up-confirmation"
                                  className="rounded-md border border-border bg-surface px-3 py-2 text-[11px] text-text"
                                >
                                  <div className="font-medium">
                                    {t(
                                      "playground:actions.prepareFollowUpTitle",
                                      "Prepare follow-up?"
                                    )}
                                  </div>
                                  <div className="mt-1">
                                    {t(
                                      "playground:actions.prepareFollowUpBody",
                                      'This will use "{{query}}" and prefill a follow-up research prompt in the composer.',
                                      {
                                        query: pendingAttachmentFollowUp.query
                                      }
                                    )}
                                  </div>
                                  <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        onPrepareResearchFollowUp?.(
                                          pendingAttachmentFollowUp
                                        )
                                        setPendingAttachmentFollowUp(null)
                                      }}
                                      className="rounded border border-border bg-surface2 px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                    >
                                      {t(
                                        "playground:actions.prepareFollowUp",
                                        "Prepare follow-up"
                                      )}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setPendingAttachmentFollowUp(null)
                                      }
                                      className="rounded border border-border bg-surface2 px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                    >
                                      {t("common:cancel", "Cancel")}
                                    </button>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                        {attachedResearchContextHistory.length > 0 ? (
                          <div
                            data-testid="pinned-research-history-block"
                            className="rounded-md border border-border bg-surface2 px-3 py-2 text-xs text-text"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium text-text-muted">
                                {t(
                                  "playground:composer.recentResearch",
                                  "Recent research"
                                )}
                              </span>
                              {attachedResearchContextHistory.map((entry) => (
                                <React.Fragment key={entry.run_id}>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      onSelectAttachedResearchContextHistory?.(entry)
                                    }
                                    className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                  >
                                    {entry.query}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      onPinAttachedResearchContextHistory?.(entry)
                                    }
                                    className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                  >
                                    {`${t("playground:actions.pinResearchContext", "Pin")} ${entry.query}`}
                                  </button>
                                  {onPrepareResearchFollowUp ? (
                                    <button
                                      type="button"
                                      onClick={(event) => {
                                        event.stopPropagation()
                                        setPendingAttachmentFollowUp({
                                          run_id: entry.run_id,
                                          query: entry.query
                                        })
                                      }}
                                      className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                    >
                                      {t("playground:actions.followUp", "Follow up")}
                                    </button>
                                  ) : null}
                                  {pendingAttachmentFollowUp?.run_id ===
                                  entry.run_id ? (
                                    <div
                                      data-testid={`history-follow-up-confirmation-${entry.run_id}`}
                                      className="w-full rounded-md border border-border bg-surface px-3 py-2 text-[11px] text-text"
                                    >
                                      <div className="font-medium">
                                        {t(
                                          "playground:actions.prepareFollowUpTitle",
                                          "Prepare follow-up?"
                                        )}
                                      </div>
                                      <div className="mt-1">
                                        {t(
                                          "playground:actions.prepareFollowUpBody",
                                          'This will use "{{query}}" and prefill a follow-up research prompt in the composer.',
                                          {
                                            query: pendingAttachmentFollowUp.query
                                          }
                                        )}
                                      </div>
                                      <div className="mt-2 flex flex-wrap items-center gap-2">
                                        <button
                                          type="button"
                                          onClick={() => {
                                            onPrepareResearchFollowUp?.(
                                              pendingAttachmentFollowUp
                                            )
                                            setPendingAttachmentFollowUp(null)
                                          }}
                                          className="rounded border border-border bg-surface2 px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                        >
                                          {t(
                                            "playground:actions.prepareFollowUp",
                                            "Prepare follow-up"
                                          )}
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setPendingAttachmentFollowUp(null)
                                          }
                                          className="rounded border border-border bg-surface2 px-2 py-0.5 text-[11px] text-text hover:bg-surface3"
                                        >
                                          {t("common:cancel", "Cancel")}
                                        </button>
                                      </div>
                                    </div>
                                  ) : null}
                                </React.Fragment>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    <div
                      className={contextToolsOpen ? "mb-2" : "hidden"}
                      aria-hidden={!contextToolsOpen}
                    >
                      <div className="rounded-md bg-surface2/50 p-3">
                        <div className="flex flex-col gap-4">
                          <div>
                            <div className="mb-2 text-xs font-semibold text-text">
                              {t(
                                "playground:composer.knowledgeSearch",
                                "Search & Context"
                              )}
                            </div>
                            {wrapComposerProfile(
                              "knowledge-panel",
                              <KnowledgePanel
                                onInsert={handleKnowledgeInsert}
                                onAsk={handleKnowledgeAsk}
                                isConnected={isConnectionReady}
                                open={contextToolsOpen}
                                onOpenChange={handleKnowledgePanelOpenChange}
                                openTab={knowledgePanelTab}
                                openTabRequestId={knowledgePanelTabRequestId}
                                autoFocus
                                showToggle={false}
                                variant="embedded"
                                currentMessage={contextToolsOpen ? deferredComposerInput : ""}
                                showAttachedContext
                                attachedImage={form.values.image}
                                attachedTabs={selectedDocuments}
                                availableTabs={availableTabs}
                                attachedFiles={uploadedFiles}
                                onRemoveImage={handleKnowledgeRemoveImage}
                                onRemoveTab={removeDocument}
                                onAddTab={addDocument}
                                onClearTabs={clearSelectedDocuments}
                                onRefreshTabs={reloadTabs}
                                onAddFile={handleKnowledgeAddFile}
                                onRemoveFile={removeUploadedFile}
                                onClearFiles={clearUploadedFiles}
                                fileRetrievalEnabled={fileRetrievalEnabled}
                                onFileRetrievalChange={setFileRetrievalEnabled}
                              />
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
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
                    {modeAnnouncement && (
                      <div
                        role="status"
                        aria-live="polite"
                        className="mt-1 rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs text-primaryStrong"
                      >
                        {modeAnnouncement}
                      </div>
                    )}
                    {characterPendingApply && (
                      <div
                        role="status"
                        aria-live="polite"
                        className="mt-1 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/10 px-2 py-2 text-xs text-primaryStrong"
                      >
                        <span>
                          {t(
                            "playground:composer.characterPendingNotice",
                            "Character updates will apply on your next turn."
                          )}
                        </span>
                        <div className="flex items-center gap-2">
                          {selectedCharacterGreeting && (
                            <button
                              type="button"
                              onClick={() => {
                                setMessageValue(selectedCharacterGreeting, {
                                  collapseLarge: true
                                })
                                textAreaFocus()
                              }}
                              className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
                            >
                              {t(
                                "playground:composer.characterUseGreeting",
                                "Use greeting"
                              )}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setOpenActorSettings(true)}
                            className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
                          >
                            {t(
                              "playground:composer.characterReview",
                              "Review character"
                            )}
                          </button>
                        </div>
                      </div>
                    )}
                    {compareModeActive && (
                      <div
                        role="status"
                        aria-live="polite"
                        data-testid="compare-activation-contract"
                        className="mt-1 space-y-2 rounded-md border border-primary/30 bg-primary/10 px-2 py-2 text-xs text-primaryStrong"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-[11px] font-semibold uppercase tracking-wide">
                            {t(
                              "playground:composer.compareActivationTitle",
                              "Compare contract"
                            )}
                          </span>
                          <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[10px] font-medium text-primaryStrong">
                            {t(
                              "playground:composer.compareActivationCount",
                              "{{count}} models",
                              {
                                count: compareSelectedModels.length
                              } as any
                            )}
                          </span>
                        </div>
                        <p>
                          {t(
                            "playground:composer.compareActivationBody",
                            "Next send fans out the same prompt and shared context to each selected model. Compare mode stays active until you turn it off."
                          )}
                        </p>
                        <div className="space-y-1">
                          <p className="text-[11px] font-medium text-primaryStrong">
                            {t(
                              "playground:composer.compareActivationModels",
                              "Selected models"
                            )}
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {compareSelectedModelLabels.length > 0 ? (
                              compareSelectedModelLabels.map((label, index) => (
                                <span
                                  key={`${label}-${index}`}
                                  className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[10px] text-primaryStrong"
                                >
                                  {label}
                                </span>
                              ))
                            ) : (
                              <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[10px] text-primaryStrong">
                                {t(
                                  "playground:compare.noModelsSelected",
                                  "No models selected"
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="space-y-1">
                          <p className="text-[11px] font-medium text-primaryStrong">
                            {t(
                              "playground:composer.compareActivationSharedContext",
                              "Shared context"
                            )}
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {compareSharedContextLabels.length > 0 ? (
                              compareSharedContextLabels.map((label, index) => (
                                <span
                                  key={`${label}-${index}`}
                                  className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[10px] text-primaryStrong"
                                >
                                  {label}
                                </span>
                              ))
                            ) : (
                              <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[10px] text-primaryStrong">
                                {t(
                                  "playground:composer.compareActivationNoSharedContext",
                                  "No additional shared context modifiers are active."
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                        {compareInteroperabilityNotices.length > 0 && (
                          <div className="space-y-1" data-testid="compare-interoperability-notices">
                            <p className="text-[11px] font-medium text-primaryStrong">
                              {t(
                                "playground:composer.compareActivationInteroperability",
                                "Interoperability notes"
                              )}
                            </p>
                            <div className="space-y-1">
                              {(noticesExpanded
                                ? compareInteroperabilityNotices
                                : compareInteroperabilityNotices.slice(0, 2)
                              ).map((notice) => (
                                <div
                                  key={notice.id}
                                  className={`rounded border px-2 py-1 text-[11px] ${
                                    notice.tone === "warning"
                                      ? "border-warn/40 bg-warn/10 text-warn"
                                      : "border-primary/30 bg-surface text-primaryStrong"
                                  }`}
                                >
                                  {notice.text}
                                </div>
                              ))}
                              {compareInteroperabilityNotices.length > 2 && (
                                <button
                                  type="button"
                                  onClick={() => setNoticesExpanded(!noticesExpanded)}
                                  className="text-[10px] text-primary underline"
                                >
                                  {noticesExpanded
                                    ? t(
                                        "playground:compareNoticesCollapse",
                                        "Show fewer"
                                      )
                                    : t(
                                        "playground:compareNoticesExpand",
                                        "{{count}} more notes",
                                        { count: compareInteroperabilityNotices.length - 2 }
                                      )}
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span
                            className={
                              compareNeedsMoreModels
                                ? "text-warn"
                                : "text-primaryStrong"
                            }
                          >
                            {compareNeedsMoreModels
                              ? t(
                                  "playground:composer.compareActivationNeedsMoreModels",
                                  "Add at least one more model before sending in Compare mode."
                                )
                              : t(
                                  "playground:composer.compareActivationPersistence",
                                  "These selections persist for next turns until Compare mode is disabled."
                                )}
                          </span>
                          <button
                            type="button"
                            onClick={() => setOpenModelSettings(true)}
                            className={`rounded border px-2 py-0.5 text-[11px] font-medium ${
                              compareNeedsMoreModels
                                ? "border-warn/40 bg-surface text-warn hover:bg-warn/10"
                                : "border-primary/30 bg-surface text-primaryStrong hover:bg-primary/10"
                            }`}
                          >
                            {compareNeedsMoreModels
                              ? t("playground:compare.addModels", "Add models")
                              : t(
                                  "playground:composer.compareActivationReviewModels",
                                  "Review models"
                                )}
                          </button>
                        </div>
                      </div>
                    )}
                    {contextDeltaLabels.length > 0 && (
                      <div
                        role="status"
                        aria-live="polite"
                        className="mt-1 flex flex-wrap items-center gap-1 rounded-md border border-border bg-surface2 px-2 py-1"
                      >
                        <span className="text-[11px] font-medium text-text-muted">
                          {t(
                            "playground:composer.delta.title",
                            "Changed since last send:"
                          )}
                        </span>
                        {contextDeltaLabels.map((delta) => (
                          <span
                            key={delta}
                            className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] text-text-muted"
                          >
                            {delta}
                          </span>
                        ))}
                      </div>
                    )}
                    {contextConflictWarnings.length > 0 && (
                      <div
                        role="status"
                        aria-live="polite"
                        className="mt-1 space-y-1 rounded-md border border-warn/40 bg-warn/10 px-2 py-2"
                      >
                        {contextConflictWarnings.map((warning) => (
                          <div
                            key={warning.id}
                            className="flex items-start justify-between gap-2 text-xs text-warn"
                          >
                            <span>{warning.text}</span>
                            {warning.onAction ? (
                              <button
                                type="button"
                                onClick={warning.onAction}
                                className="shrink-0 rounded px-1 py-0.5 text-[11px] font-medium text-warn underline hover:bg-warn/10"
                              >
                                {warning.actionLabel || t("common:review", "Review")}
                              </button>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    )}
                    {wrapComposerProfile(
                      "model-recommendations",
                      <ModelRecommendationsPanel
                        t={t}
                        recommendations={visibleModelRecommendations}
                        showOpenInsights={sessionInsights.totals.totalTokens > 0}
                        onOpenInsights={openSessionInsightsModal}
                        onRunAction={handleModelRecommendationAction}
                        onDismiss={dismissModelRecommendation}
                        getActionLabel={getModelRecommendationActionLabel}
                      />
                    )}
                    {currentChatModelSettings.jsonMode && (
                      <div
                        role="status"
                        aria-live="polite"
                        className="mt-1 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/10 px-2 py-2 text-xs text-primaryStrong"
                      >
                        <span>
                          {t(
                            "playground:composer.jsonModeHint",
                            "JSON mode is active. Responses should be valid JSON objects."
                          )}
                        </span>
                        <button
                          type="button"
                          onClick={() => setOpenModelSettings(true)}
                          className="rounded border border-primary/30 bg-surface px-2 py-0.5 text-[11px] font-medium text-primaryStrong hover:bg-primary/10"
                        >
                          {t(
                            "playground:composer.jsonModeConfigure",
                            "Configure"
                          )}
                        </button>
                      </div>
                    )}
                    {isConnectionReady &&
                      connectionUxState === "connected_degraded" && (
                        <div className="mt-1 flex flex-wrap items-center justify-between gap-2 rounded-md border border-warn/40 bg-warn/10 px-2 py-2 text-xs text-warn">
                          <span>
                            {t(
                              "playground:composer.providerDegraded",
                              "Provider connectivity is degraded. Responses may be slower or fail intermittently."
                            )}
                          </span>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={openModelApiSelector}
                              className="rounded border border-warn/40 bg-surface px-2 py-0.5 text-[11px] font-medium text-warn hover:bg-warn/10"
                            >
                              {t(
                                "playground:composer.providerDegradedSwitchModel",
                                "Switch model"
                              )}
                            </button>
                            <Link
                              to="/settings/health"
                              className="text-[11px] font-medium text-warn underline hover:text-warn"
                            >
                              {t(
                                "settings:healthSummary.diagnostics",
                                "Health & diagnostics"
                              )}
                            </Link>
                          </div>
                        </div>
                      )}
                    {isProMode && (
                      <div
                        data-testid="startup-template-controls"
                        className="mt-2 rounded-md border border-border/60 bg-surface2/70 px-2 py-2"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                            {t(
                              "playground:composer.startupTemplatesLabel",
                              "Startup templates"
                            )}
                          </span>
                          <Input
                            size="small"
                            value={startupTemplateDraftName}
                            onChange={(event) =>
                              setStartupTemplateDraftName(event.target.value)
                            }
                            placeholder={t(
                              "playground:composer.startupTemplatesNamePlaceholder",
                              "Template name"
                            )}
                            className="min-w-[180px] max-w-[260px]"
                          />
                          <Button
                            size="small"
                            onClick={handleSaveStartupTemplate}
                            disabled={
                              !selectedModel &&
                              String(systemPrompt || "").trim().length === 0 &&
                              !selectedCharacter &&
                              ragPinnedResults.length === 0
                            }
                          >
                            {t(
                              "playground:composer.startupTemplatesSave",
                              "Save current"
                            )}
                          </Button>
                          <Select
                            size="small"
                            placeholder={t(
                              "playground:composer.startupTemplatesLaunch",
                              "Launch saved template"
                            )}
                            options={startupTemplates.map((template) => ({
                              value: template.id,
                              label: template.name
                            }))}
                            onChange={handleOpenStartupTemplatePreview}
                            className="min-w-[220px]"
                            data-testid="startup-template-launch-select"
                          />
                        </div>
                        {startupTemplates.length === 0 && (
                          <p className="mt-1 text-xs text-text-muted">
                            {t(
                              "playground:composer.startupTemplatesHint",
                              "Save your current model, prompt, character, and pinned-source setup to reuse it before first send."
                            )}
                          </p>
                        )}
                      </div>
                    )}
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
                          researchLaunchButton={researchLaunchButton}
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
                    {queuedMessages.length > 0 && showQueuedBanner && (
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
                        <p className="max-w-xs text-left">
                          <span className="block font-medium">
                            {t(
                              "playground:composer.queuedBanner.title",
                              "Queued while offline"
                            )}
                          </span>
                          {t(
                            "playground:composer.queuedBanner.body",
                            "We’ll hold these messages and send them once your tldw server is connected."
                          )}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            className={`rounded-md border border-success/30 bg-surface px-2 py-1 text-xs font-medium text-success hover:bg-success/10 ${
                              !isConnectionReady ? "cursor-not-allowed opacity-60" : ""
                            }`}
                            title={t(
                              "playground:composer.queuedBanner.sendNow",
                              "Send queued messages"
                            ) as string}
                            disabled={!isConnectionReady}
                            onClick={async () => {
                              if (!isConnectionReady) return
                              for (const item of queuedMessages) {
                                await submitFormFromQueued(item.message, item.image)
                              }
                              clearQueuedMessages()
                            }}>
                            {t(
                              "playground:composer.queuedBanner.sendNow",
                              "Send queued messages"
                            )}
                          </button>
                          <button
                            type="button"
                            className="text-xs font-medium text-success underline hover:text-success"
                            title={t(
                              "playground:composer.queuedBanner.clear",
                              "Clear queue"
                            ) as string}
                            onClick={() => {
                              clearQueuedMessages()
                            }}>
                            {t(
                              "playground:composer.queuedBanner.clear",
                              "Clear queue"
                            )}
                          </button>
                          <Link
                            to="/settings/health"
                            className="text-xs font-medium text-success underline hover:text-success"
                          >
                            {t(
                              "settings:healthSummary.diagnostics",
                              "Health & diagnostics"
                            )}
                          </Link>
                          <button
                            type="button"
                            onClick={() => setShowQueuedBanner(false)}
                            className="inline-flex items-center rounded-full p-1 text-success hover:bg-success/10"
                            aria-label={t("common:close", "Dismiss")}
                            title={t("common:close", "Dismiss") as string}>
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
      <Modal
        open={imageGenerateModalOpen}
        onCancel={() => {
          if (imageGenerateBusy) return
          setImageGenerateModalOpen(false)
        }}
        title={t("playground:imageGeneration.modalTitle", "Generate image")}
        width={720}
        destroyOnHidden
        footer={
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={handleCreateImagePromptDraft}
                icon={<WandSparkles className="h-4 w-4" />}
                disabled={imageGenerateBusy}
              >
                {t("playground:imageGeneration.createPrompt", "Create prompt")}
              </Button>
              <Button
                onClick={() => {
                  void handleRefineImagePromptDraft()
                }}
                loading={imagePromptRefineSubmitting}
                disabled={imageGenerateSubmitting}
                data-testid="image-refine-with-llm"
              >
                {t(
                  "playground:imageGeneration.refineWithLlm",
                  "Refine with LLM"
                )}
              </Button>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                onClick={() => setImageGenerateModalOpen(false)}
                disabled={imageGenerateBusy}
              >
                {t("common:cancel", "Cancel")}
              </Button>
              <Button
                type="primary"
                onClick={() => {
                  void submitImageGenerateModal()
                }}
                loading={imageGenerateSubmitting}
                disabled={imagePromptRefineSubmitting}
              >
                {t(
                  "playground:imageGeneration.generateNow",
                  "Generate image"
                )}
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.backendLabel", "Backend")}
              </label>
              <Select
                value={imageGenerateBackend || undefined}
                data-testid="image-generate-backend-select"
                options={imageGenerateBackendOptions.map((option) => ({
                  value: option.value,
                  label: option.provider
                    ? `${getProviderDisplayName(option.provider)} · ${option.label}`
                    : option.label
                }))}
                onChange={(value) => {
                  const next = String(value || "")
                  setImageGenerateBackend(next)
                  void hydrateImageGenerateSettings(next)
                }}
                placeholder={t(
                  "playground:imageGeneration.backendPlaceholder",
                  "Select backend"
                )}
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.promptModeLabel", "Prompt mode")}
              </label>
              <Radio.Group
                optionType="button"
                value={imageGeneratePromptMode}
                onChange={(event) =>
                  setImageGeneratePromptMode(
                    event.target.value as ImageGenerationPromptMode
                  )
                }
                disabled={imageGenerateBusy}
              >
                {imagePromptStrategies.map((strategy) => (
                  <Radio.Button key={strategy.id} value={strategy.id}>
                    {strategy.label}
                  </Radio.Button>
                ))}
                </Radio.Group>
              </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.syncPolicyLabel", "Server sync")}
              </label>
              <Select
                value={imageGenerateSyncPolicy}
                data-testid="image-generate-sync-policy-select"
                options={[
                  {
                    value: "inherit",
                    label: t(
                      "playground:imageGeneration.syncPolicyInherit",
                      "Inherit defaults"
                    )
                  },
                  {
                    value: "on",
                    label: t(
                      "playground:imageGeneration.syncPolicyOn",
                      "Mirror event"
                    )
                  },
                  {
                    value: "off",
                    label: t(
                      "playground:imageGeneration.syncPolicyOff",
                      "Local only"
                    )
                  }
                ]}
                onChange={(value) =>
                  setImageGenerateSyncPolicy(
                    normalizeImageGenerationEventSyncPolicy(value, "inherit")
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.syncChatDefault", "Chat default")}
              </label>
              <Select
                value={imageEventSyncChatMode}
                data-testid="image-generate-chat-default-select"
                options={[
                  {
                    value: "off",
                    label: t(
                      "playground:imageGeneration.syncChatDefaultOff",
                      "Off (local only)"
                    )
                  },
                  {
                    value: "on",
                    label: t(
                      "playground:imageGeneration.syncChatDefaultOn",
                      "On (mirror events)"
                    )
                  }
                ]}
                onChange={(value) => {
                  const next = normalizeImageGenerationEventSyncMode(value, "off")
                  void updateChatSettings({
                    imageEventSyncMode: next
                  })
                }}
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.syncGlobalDefault", "Global default")}
              </label>
              <Select
                value={normalizeImageGenerationEventSyncMode(
                  imageEventSyncGlobalDefault,
                  "off"
                )}
                data-testid="image-generate-global-default-select"
                options={[
                  {
                    value: "off",
                    label: t(
                      "playground:imageGeneration.syncGlobalDefaultOff",
                      "Off (local only)"
                    )
                  },
                  {
                    value: "on",
                    label: t(
                      "playground:imageGeneration.syncGlobalDefaultOn",
                      "On (mirror events)"
                    )
                  }
                ]}
                onChange={(value) => {
                  const next = normalizeImageGenerationEventSyncMode(value, "off")
                  void setImageEventSyncGlobalDefault(next)
                }}
                disabled={imageGenerateBusy}
              />
            </div>
          </div>
          <p className="text-[11px] text-text-muted">
            {imageGenerateResolvedSyncMode === "on"
              ? t(
                  "playground:imageGeneration.syncEffectiveOn",
                  "Effective policy: this generation event will also be mirrored to server chat history."
                )
              : t(
                  "playground:imageGeneration.syncEffectiveOff",
                  "Effective policy: this generation event stays local-only and does not mirror to server chat history."
                )}
          </p>
          <div className="space-y-1">
            <label className="text-xs font-medium text-text-muted">
              {t("playground:imageGeneration.promptLabel", "Prompt")}
            </label>
            <Input.TextArea
              value={imageGeneratePrompt}
              onChange={(event) => {
                setImageGeneratePrompt(event.target.value)
                clearImagePromptRefineState()
              }}
              autoSize={{ minRows: 4, maxRows: 8 }}
              disabled={imageGenerateBusy}
              placeholder={t(
                "playground:imageGeneration.promptPlaceholder",
                "Describe the image you want to generate."
              )}
            />
            <p className="text-[11px] text-text-muted">
              {t(
                "playground:imageGeneration.promptHint",
                "Create prompt drafts from current chat context, then edit before generating."
              )}
            </p>
            {imagePromptContextBreakdown.length > 0 && (
              <div
                className="rounded-md border border-border/70 bg-surface2/60 px-2 py-2 text-[11px] text-text-muted"
                data-testid="image-prompt-context-breakdown"
              >
                <div className="mb-1 font-medium text-text">
                  {t(
                    "playground:imageGeneration.contextBlendLabel",
                    "Weighted context blend"
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {imagePromptContextBreakdown.map((entry) => (
                    <span
                      key={`${entry.id}-${entry.score}`}
                      className="inline-flex items-center rounded-full border border-border px-2 py-0.5"
                      title={entry.text}
                    >
                      {entry.label} {Math.round(entry.score * 100)}%
                    </span>
                  ))}
                </div>
              </div>
            )}
            {imagePromptRefineCandidate && (
              <div
                className="rounded-md border border-primary/30 bg-primary/10 px-3 py-3"
                data-testid="image-prompt-refine-diff"
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-primaryStrong">
                    {t(
                      "playground:imageGeneration.refineCandidateTitle",
                      "Refined prompt candidate"
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-1 text-[11px] text-primaryStrong">
                    {imagePromptRefineModel ? (
                      <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5">
                        {imagePromptRefineModel}
                      </span>
                    ) : null}
                    {imagePromptRefineLatencyMs != null ? (
                      <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5">
                        {t(
                          "playground:imageGeneration.refineLatency",
                          "{{ms}} ms",
                          { ms: imagePromptRefineLatencyMs } as any
                        )}
                      </span>
                    ) : null}
                    {imagePromptRefineDiff ? (
                      <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5">
                        {t(
                          "playground:imageGeneration.refineOverlap",
                          "{{percent}}% overlap",
                          {
                            percent: Math.round(
                              imagePromptRefineDiff.overlapRatio * 100
                            )
                          } as any
                        )}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <div className="text-[11px] font-medium text-text-muted">
                      {t(
                        "playground:imageGeneration.refineOriginalLabel",
                        "Original draft"
                      )}
                    </div>
                    <Input.TextArea
                      value={imagePromptRefineBaseline}
                      autoSize={{ minRows: 3, maxRows: 6 }}
                      readOnly
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="text-[11px] font-medium text-text-muted">
                      {t(
                        "playground:imageGeneration.refineCandidateLabel",
                        "Refined prompt"
                      )}
                    </div>
                    <Input.TextArea
                      value={imagePromptRefineCandidate}
                      autoSize={{ minRows: 3, maxRows: 6 }}
                      readOnly
                    />
                  </div>
                </div>
                {imagePromptRefineDiff && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <div className="space-y-1">
                      <div className="text-[11px] font-medium text-success">
                        {t("playground:imageGeneration.refineAdded", "Added")}
                      </div>
                      <div className="space-y-1 text-[11px] text-text-muted">
                        {imagePromptRefineDiff.addedHighlights.length > 0 ? (
                          imagePromptRefineDiff.addedHighlights.map((entry, index) => (
                            <div
                              key={`image-refine-added-${index}`}
                              className="rounded border border-success/40 bg-success/10 px-2 py-1"
                            >
                              {entry}
                            </div>
                          ))
                        ) : (
                          <div className="rounded border border-border/70 bg-surface2/50 px-2 py-1">
                            {t(
                              "playground:imageGeneration.refineNoAdded",
                              "No added segments"
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-[11px] font-medium text-danger">
                        {t("playground:imageGeneration.refineRemoved", "Removed")}
                      </div>
                      <div className="space-y-1 text-[11px] text-text-muted">
                        {imagePromptRefineDiff.removedHighlights.length > 0 ? (
                          imagePromptRefineDiff.removedHighlights.map(
                            (entry, index) => (
                              <div
                                key={`image-refine-removed-${index}`}
                                className="rounded border border-danger/40 bg-danger/10 px-2 py-1"
                              >
                                {entry}
                              </div>
                            )
                          )
                        ) : (
                          <div className="rounded border border-border/70 bg-surface2/50 px-2 py-1">
                            {t(
                              "playground:imageGeneration.refineNoRemoved",
                              "No removed segments"
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  <Button onClick={rejectRefinedImagePromptCandidate}>
                    {t(
                      "playground:imageGeneration.refineKeepOriginal",
                      "Keep original"
                    )}
                  </Button>
                  <Button
                    type="primary"
                    onClick={applyRefinedImagePromptCandidate}
                    data-testid="image-refine-accept"
                  >
                    {t(
                      "playground:imageGeneration.refineAccept",
                      "Apply refined prompt"
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.formatLabel", "Format")}
              </label>
              <Select
                value={imageGenerateFormat}
                options={[
                  { value: "png", label: "PNG" },
                  { value: "jpg", label: "JPG" },
                  { value: "webp", label: "WEBP" }
                ]}
                onChange={(value) =>
                  setImageGenerateFormat(value as "png" | "jpg" | "webp")
                }
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.widthLabel", "Width")}
              </label>
              <InputNumber
                value={imageGenerateWidth}
                min={64}
                step={64}
                style={{ width: "100%" }}
                onChange={(value) =>
                  setImageGenerateWidth(
                    typeof value === "number" && Number.isFinite(value)
                      ? value
                      : undefined
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.heightLabel", "Height")}
              </label>
              <InputNumber
                value={imageGenerateHeight}
                min={64}
                step={64}
                style={{ width: "100%" }}
                onChange={(value) =>
                  setImageGenerateHeight(
                    typeof value === "number" && Number.isFinite(value)
                      ? value
                      : undefined
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.stepsLabel", "Steps")}
              </label>
              <InputNumber
                value={imageGenerateSteps}
                min={1}
                style={{ width: "100%" }}
                onChange={(value) =>
                  setImageGenerateSteps(
                    typeof value === "number" && Number.isFinite(value)
                      ? value
                      : undefined
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.cfgScaleLabel", "CFG scale")}
              </label>
              <InputNumber
                value={imageGenerateCfgScale}
                min={0}
                step={0.5}
                style={{ width: "100%" }}
                onChange={(value) =>
                  setImageGenerateCfgScale(
                    typeof value === "number" && Number.isFinite(value)
                      ? value
                      : undefined
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.seedLabel", "Seed")}
              </label>
              <InputNumber
                value={imageGenerateSeed}
                style={{ width: "100%" }}
                onChange={(value) =>
                  setImageGenerateSeed(
                    typeof value === "number" && Number.isFinite(value)
                      ? value
                      : undefined
                  )
                }
                disabled={imageGenerateBusy}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.samplerLabel", "Sampler")}
              </label>
              <Input
                value={imageGenerateSampler}
                onChange={(event) => setImageGenerateSampler(event.target.value)}
                disabled={imageGenerateBusy}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-text-muted">
                {t("playground:imageGeneration.modelLabel", "Image model")}
              </label>
              <Input
                value={imageGenerateModel}
                onChange={(event) => setImageGenerateModel(event.target.value)}
                disabled={imageGenerateBusy}
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-text-muted">
              {t(
                "playground:imageGeneration.negativePromptLabel",
                "Negative prompt"
              )}
            </label>
            <Input.TextArea
              value={imageGenerateNegativePrompt}
              onChange={(event) =>
                setImageGenerateNegativePrompt(event.target.value)
              }
              autoSize={{ minRows: 2, maxRows: 4 }}
              disabled={imageGenerateBusy}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-text-muted">
              {t(
                "playground:imageGeneration.extraParamsLabel",
                "Extra params (JSON object)"
              )}
            </label>
            <Input.TextArea
              value={imageGenerateExtraParams}
              onChange={(event) => setImageGenerateExtraParams(event.target.value)}
              autoSize={{ minRows: 3, maxRows: 6 }}
              disabled={imageGenerateBusy}
              placeholder='{"tiling": false}'
            />
          </div>
        </div>
      </Modal>
      <Modal
        open={followUpResearchModalOpen}
        onCancel={closeFollowUpResearchModal}
        destroyOnHidden
        title={t(
          "playground:actions.followUpResearch",
          "Follow-up Research"
        )}
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              onClick={closeFollowUpResearchModal}
              disabled={followUpResearchPending}
            >
              {t("common:cancel", "Cancel")}
            </Button>
            <Button
              type="primary"
              onClick={() => {
                void handleStartFollowUpResearch()
              }}
              disabled={!canLaunchFollowUpResearch || followUpResearchPending}
              loading={followUpResearchPending}
            >
              {t("playground:actions.startResearch", "Start research")}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            {t(
              "playground:actions.followUpResearchBody",
              "Start a new linked research run from the current draft without sending a chat message."
            )}
          </p>
          <div className="rounded-md border border-border bg-surface px-3 py-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              {t("playground:actions.followUpResearchQuery", "Query")}
            </div>
            <div className="mt-1 text-sm text-text">
              {followUpResearchDraftQuery}
            </div>
          </div>
          {attachedResearchContext ? (
            <Checkbox
              checked={includeAttachedResearchAsBackground}
              onChange={(event) =>
                setIncludeAttachedResearchAsBackground(event.target.checked)
              }
              disabled={followUpResearchPending}
            >
              {t(
                "playground:actions.followUpResearchUseAttachedBackground",
                "Use attached research as background"
              )}
            </Checkbox>
          ) : null}
        </div>
      </Modal>
      <Modal
        open={rawRequestModalOpen}
        onCancel={() => setRawRequestModalOpen(false)}
        title={t("playground:tools.rawChatRequestTitle", "Current chat request JSON")}
        width={780}
        destroyOnHidden
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button onClick={refreshRawRequestSnapshot}>
              {t("common:refresh", "Refresh")}
            </Button>
            {attachedResearchContextDraft ? (
              <Button onClick={handleResetAttachedResearchDraft}>
                {t(
                  "playground:actions.resetAttachedResearchContext",
                  "Reset to Attached Run"
                )}
              </Button>
            ) : null}
            {attachedResearchContextDraft ? (
              <Button type="primary" onClick={applyAttachedResearchDraft}>
                {t(
                  "playground:actions.applyAttachedResearchContext",
                  "Apply"
                )}
              </Button>
            ) : null}
            <Button onClick={copyRawRequestJson} disabled={!rawRequestJson}>
              {t("common:copy", "Copy")}
            </Button>
            <Button type="primary" onClick={() => setRawRequestModalOpen(false)}>
              {t("common:close", "Close")}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          {rawRequestSnapshot ? (
            <>
              {attachedResearchContextDraft ? (
                <div
                  data-testid="attached-research-context-panel"
                  className="space-y-3 rounded-md border border-border bg-surface px-3 py-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-medium text-text">
                        {t(
                          "playground:tools.attachedResearchContextTitle",
                          "Attached Research Context"
                        )}
                      </h3>
                      <p className="text-xs text-text-muted">
                        {attachedResearchContextDraft.query}
                      </p>
                    </div>
                    <div className="space-y-1 text-right text-[11px] text-text-muted">
                      <div>
                        {t("playground:tools.attachedResearchRunId", "Run ID")}:{" "}
                        <span className="font-mono">
                          {attachedResearchContextDraft.run_id}
                        </span>
                      </div>
                      <div>
                        {t(
                          "playground:tools.attachedResearchAttachedAt",
                          "Attached"
                        )}
                        :{" "}
                        {new Date(
                          attachedResearchContextDraft.attached_at
                        ).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  {attachedResearchPreviewSuppressed ? (
                    <p className="text-xs text-text-muted">
                      {t(
                        "playground:tools.attachedResearchContextSuppressed",
                        "Attached research is active but omitted from this request preview."
                      )}
                    </p>
                  ) : null}
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-text-muted">
                        {t("playground:composer.context.question", "Question")}
                      </label>
                      <Input
                        data-testid="attached-research-context-question-input"
                        value={attachedResearchContextDraft.question}
                        onChange={handleAttachedResearchDraftQuestionChange}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-text-muted">
                        {t(
                          "playground:tools.attachedResearchContextLink",
                          "Research link"
                        )}
                      </label>
                      <Input
                        value={attachedResearchContextDraft.research_url}
                        readOnly
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-text-muted">
                        {t("playground:composer.context.outline", "Outline")}
                      </label>
                      <Input.TextArea
                        data-testid="attached-research-context-outline-input"
                        value={stringifyOutline(attachedResearchContextDraft)}
                        onChange={handleAttachedResearchDraftOutlineChange}
                        autoSize={{ minRows: 3, maxRows: 6 }}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-text-muted">
                        {t("playground:composer.context.claims", "Key claims")}
                      </label>
                      <Input.TextArea
                        data-testid="attached-research-context-claims-input"
                        value={stringifyKeyClaims(attachedResearchContextDraft)}
                        onChange={handleAttachedResearchDraftClaimsChange}
                        autoSize={{ minRows: 3, maxRows: 6 }}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-text-muted">
                        {t(
                          "playground:composer.context.unresolvedQuestions",
                          "Unresolved questions"
                        )}
                      </label>
                      <Input.TextArea
                        data-testid="attached-research-context-unresolved-input"
                        value={stringifyUnresolvedQuestions(
                          attachedResearchContextDraft
                        )}
                        onChange={handleAttachedResearchDraftUnresolvedChange}
                        autoSize={{ minRows: 3, maxRows: 6 }}
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-text-muted">
                          {t(
                            "playground:tools.attachedResearchUnsupportedClaims",
                            "Unsupported claim count"
                          )}
                        </label>
                        <InputNumber
                          data-testid="attached-research-context-unsupported-count-input"
                          value={
                            attachedResearchContextDraft.verification_summary
                              ?.unsupported_claim_count
                          }
                          min={0}
                          onChange={
                            handleAttachedResearchDraftUnsupportedClaimCountChange
                          }
                          style={{ width: "100%" }}
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-text-muted">
                          {t(
                            "playground:tools.attachedResearchHighTrustSources",
                            "High-trust sources"
                          )}
                        </label>
                        <InputNumber
                          data-testid="attached-research-context-high-trust-count-input"
                          value={
                            attachedResearchContextDraft.source_trust_summary
                              ?.high_trust_count
                          }
                          min={0}
                          onChange={handleAttachedResearchDraftHighTrustCountChange}
                          style={{ width: "100%" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
              <div className="space-y-1 text-xs text-text-muted">
                <p>
                  {t("playground:tools.rawChatRequestEndpoint", "Endpoint")}:{" "}
                  <span className="font-mono">{rawRequestSnapshot.endpoint}</span>
                </p>
                <p>
                  {t("playground:tools.rawChatRequestMethod", "Method")}:{" "}
                  {rawRequestSnapshot.method}
                </p>
                <p>
                  {t("playground:tools.rawChatRequestMode", "Mode")}:{" "}
                  {rawRequestSnapshot.mode}
                </p>
                <p>
                  {t("playground:tools.rawChatRequestSentAt", "Sent at")}:{" "}
                  {new Date(rawRequestSnapshot.sentAt).toLocaleString()}
                </p>
                <p>
                  {t("playground:tools.rawChatRequestMessageCount", "Messages")}:{" "}
                  {Array.isArray((rawRequestSnapshot.body as any)?.messages)
                    ? (rawRequestSnapshot.body as any).messages.length
                    : t("playground:tools.rawChatRequestMessageCountNa", "n/a")}
                </p>
              </div>
              <Input.TextArea
                data-testid="raw-chat-request-json"
                readOnly
                value={rawRequestJson}
                autoSize={{ minRows: 14, maxRows: 30 }}
                className="font-mono text-xs"
              />
            </>
          ) : (
            <p className="text-sm text-text-muted">
              {t(
                "playground:tools.rawChatRequestEmpty",
                "Unable to generate a request preview for the current composer state."
              )}
            </p>
          )}
        </div>
      </Modal>
      <Modal
        open={Boolean(startupTemplatePreview)}
        onCancel={() => setStartupTemplatePreview(null)}
        title={t(
          "playground:composer.startupTemplatePreviewTitle",
          "Launch startup template"
        )}
        destroyOnHidden
        data-testid="startup-template-preview-modal"
        footer={
          <div className="flex flex-wrap justify-between gap-2">
            <Button
              danger
              onClick={() => {
                if (!startupTemplatePreview) return
                handleDeleteStartupTemplate(startupTemplatePreview.id)
              }}
              disabled={!startupTemplatePreview}
            >
              {t(
                "playground:composer.startupTemplateDelete",
                "Delete template"
              )}
            </Button>
            <div className="flex flex-wrap justify-end gap-2">
              <Button onClick={() => setStartupTemplatePreview(null)}>
                {t("common:cancel", "Cancel")}
              </Button>
              <Button
                type="primary"
                onClick={handleApplyStartupTemplate}
                disabled={!startupTemplatePreview}
              >
                {t(
                  "playground:composer.startupTemplateApply",
                  "Apply template"
                )}
              </Button>
            </div>
          </div>
        }
      >
        {startupTemplatePreview ? (
          <div className="space-y-3">
            <p className="text-sm text-text-muted">
              {t(
                "playground:composer.startupTemplatePreviewBody",
                "Review active context that will be applied before your next send."
              )}
            </p>
            <div className="grid gap-2 text-xs text-text sm:grid-cols-2">
              <div className="rounded-md border border-border bg-surface px-2 py-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("playground:composer.context.model", "Model")}
                </div>
                <div className="mt-1">
                  {startupTemplatePreview.selectedModel ||
                    t("common:none", "None")}
                </div>
              </div>
              <div className="rounded-md border border-border bg-surface px-2 py-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("playground:composer.context.prompt", "Prompt")}
                </div>
                <div className="mt-1">{startupTemplatePromptDescription}</div>
              </div>
              <div className="rounded-md border border-border bg-surface px-2 py-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("playground:composer.context.preset", "Preset")}
                </div>
                <div className="mt-1">
                  {startupTemplatePreset
                    ? t(
                        `playground:presets.${startupTemplatePreset.key}.label`,
                        startupTemplatePreset.label
                      )
                    : t("common:none", "None")}
                </div>
              </div>
              <div className="rounded-md border border-border bg-surface px-2 py-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                  {t("playground:composer.context.character", "Character")}
                </div>
                <div className="mt-1">
                  {startupTemplatePreview.character?.name ||
                    t("common:none", "None")}
                </div>
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface px-2 py-2 text-xs text-text">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                {t("playground:composer.context.pinnedSources", "Pinned")}
              </div>
              <div className="mt-1">
                {t("playground:composer.context.pinnedCount", {
                  defaultValue: "{{count}} sources",
                  count: startupTemplatePreview.ragPinnedResults.length
                } as any)}
              </div>
              {startupTemplatePromptResolution?.source === "prompt-studio" && (
                <div className="mt-1 text-[11px] text-text-muted">
                  {t(
                    "playground:composer.startupTemplatePromptStudioApplied",
                    "Prompt Studio mapping will be reapplied if available."
                  )}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>
      <Modal
        title={t(
          "common:modelSettings.form.numCtx.label",
          "Context Window Size (num_ctx)"
        )}
        open={contextWindowModalOpen}
        onCancel={() => setContextWindowModalOpen(false)}
        onOk={saveContextWindowSetting}
        okText={t("common:save", "Save")}
        destroyOnHidden
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button onClick={() => setContextWindowModalOpen(false)}>
              {t("common:cancel", "Cancel")}
            </Button>
            <Button onClick={resetContextWindowSetting}>
              {t("playground:tokens.useModelDefault", "Use model default")}
            </Button>
            <Button type="primary" onClick={saveContextWindowSetting}>
              {t("common:save", "Save")}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-text-muted">
            {t(
              "playground:tokens.contextWindowOverrideDescription",
              "Set a chat-level context window override. Leave empty to use the model default."
            )}
          </p>
          <InputNumber
            style={{ width: "100%" }}
            min={1}
            step={256}
            value={contextWindowDraftValue}
            placeholder={t(
              "common:modelSettings.form.numCtx.placeholder",
              "e.g. 4096"
            )}
            onChange={(value) => {
              setContextWindowDraftValue(
                typeof value === "number" && Number.isFinite(value)
                  ? value
                  : undefined
              )
            }}
          />
          <div className="space-y-1 text-xs text-text-muted">
            <p>
              {t("playground:tokens.effectiveContextWindow", "Effective context window")}:
              {" "}
              {formatContextWindowValue(resolvedMaxContext)}{" "}
              {t("playground:tokens.tokenUnit", "tokens")}
            </p>
            <p>
              {t("playground:tokens.requestedContextWindow", "Requested context window")}:
              {" "}
              {formatContextWindowValue(requestedContextWindowOverride)}{" "}
              {t("playground:tokens.tokenUnit", "tokens")}
            </p>
            <p>
              {t("playground:tokens.modelDefaultContextWindow", "Model default context window")}:
              {" "}
              {formatContextWindowValue(modelContextLength)}{" "}
              {t("playground:tokens.tokenUnit", "tokens")}
            </p>
            <p>
              {t("playground:tokens.chatOverrideStatus", "Chat override")}:{" "}
              {isContextWindowOverrideActive
                ? t("common:enabled", "Enabled")
                : t("common:disabled", "Disabled")}
            </p>
            {nonMessageContextPercent != null && (
              <p>
                {t("playground:tokens.nonMessageShare", "Non-message context share")}:{" "}
                {Math.round(nonMessageContextPercent)}%
              </p>
            )}
            <p>
              {t("playground:tokens.truncationRisk", "Projected truncation risk")}:{" "}
              {tokenBudgetRiskLabel}
              {tokenBudgetRisk.overflowTokens > 0
                ? ` (${t("playground:tokens.overflowTokens", "{{count}} tokens over", {
                    count: tokenBudgetRisk.overflowTokens
                  } as any)})`
                : ""}
            </p>
            {isContextWindowOverrideClamped && (
              <p className="text-warn">
                {t(
                  "playground:tokens.contextWindowClamped",
                  "Requested override exceeds the model maximum. Effective value is clamped to the model limit."
                )}
              </p>
            )}
          </div>
          <ContextFootprintPanel
            t={t}
            rows={contextFootprintRows}
            nonMessageContextPercent={nonMessageContextPercent}
            showNonMessageContextWarning={showNonMessageContextWarning}
            thresholdPercent={CONTEXT_FOOTPRINT_THRESHOLD_PERCENT}
            onClearPromptContext={clearPromptContext}
            onClearPinnedSourceContext={clearPinnedSourceContext}
            onClearHistoryContext={clearHistoryContext}
            onCreateSummaryCheckpoint={insertSummaryCheckpointPrompt}
            onReviewCharacterContext={() => setOpenActorSettings(true)}
            onTrimLargestContextContributor={trimLargestContextContributor}
          />
        </div>
      </Modal>
      <Modal
        title={t("playground:insights.modalTitle", "Session insights")}
        open={sessionInsightsOpen}
        onCancel={() => setSessionInsightsOpen(false)}
        destroyOnHidden
        width={760}
        footer={
          <div className="flex justify-end">
            <Button onClick={() => setSessionInsightsOpen(false)}>
              {t("common:close", "Close")}
            </Button>
          </div>
        }
      >
        <SessionInsightsPanel t={t} insights={sessionInsights} />
      </Modal>
      <Modal
        open={mcpSettingsOpen}
        onCancel={() => setMcpSettingsOpen(false)}
        footer={null}
        width={560}
        title={t("playground:composer.mcpSettingsTitle", "MCP tool settings")}
      >
        <div className="flex flex-col gap-4">
          <div className="text-xs text-text-muted">{mcpCtrl.mcpStatusLabel}</div>
          {!hasMcp ? (
            <div className="text-sm text-text-muted">
              {t("playground:composer.mcpToolsUnavailable", "MCP tools unavailable")}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-text-muted">
                  {t("playground:composer.mcpCatalogLabel", "Catalog")}
                </label>
                <Select
                  size="small"
                  allowClear
                  showSearch
                  loading={mcpCatalogsLoading}
                  value={toolCatalogId ?? undefined}
                  placeholder={t("playground:composer.mcpCatalogSelectPlaceholder", "Select a catalog")}
                  onChange={(value) => mcpCtrl.handleCatalogSelect(value as number | undefined)}
                  optionFilterProp="label"
                  className="w-full"
                >
                  {mcpCtrl.catalogGroups.team.length > 0 && (
                    <Select.OptGroup label={t("playground:composer.mcpCatalogTeam", "Team catalogs")}>
                      {mcpCtrl.catalogGroups.team.map((catalog) => (
                        <Select.Option
                          key={`team-${catalog.id}`}
                          value={catalog.id}
                          label={catalog.name}
                        >
                          <div className="flex flex-col">
                            <span className="text-sm">{catalog.name}</span>
                            <span className="text-[11px] text-text-muted">ID {catalog.id}</span>
                          </div>
                        </Select.Option>
                      ))}
                    </Select.OptGroup>
                  )}
                  {mcpCtrl.catalogGroups.org.length > 0 && (
                    <Select.OptGroup label={t("playground:composer.mcpCatalogOrg", "Org catalogs")}>
                      {mcpCtrl.catalogGroups.org.map((catalog) => (
                        <Select.Option
                          key={`org-${catalog.id}`}
                          value={catalog.id}
                          label={catalog.name}
                        >
                          <div className="flex flex-col">
                            <span className="text-sm">{catalog.name}</span>
                            <span className="text-[11px] text-text-muted">ID {catalog.id}</span>
                          </div>
                        </Select.Option>
                      ))}
                    </Select.OptGroup>
                  )}
                  {mcpCtrl.catalogGroups.global.length > 0 && (
                    <Select.OptGroup label={t("playground:composer.mcpCatalogGlobal", "Global catalogs")}>
                      {mcpCtrl.catalogGroups.global.map((catalog) => (
                        <Select.Option
                          key={`global-${catalog.id}`}
                          value={catalog.id}
                          label={catalog.name}
                        >
                          <div className="flex flex-col">
                            <span className="text-sm">{catalog.name}</span>
                            <span className="text-[11px] text-text-muted">ID {catalog.id}</span>
                          </div>
                        </Select.Option>
                      ))}
                    </Select.OptGroup>
                  )}
                </Select>
                <Input
                  size="small"
                  placeholder={t("playground:composer.mcpCatalogPlaceholder", "catalog name")}
                  value={mcpCtrl.catalogDraft}
                  onChange={(e) => mcpCtrl.setCatalogDraft(e.target.value)}
                  onBlur={mcpCtrl.commitCatalog}
                  onPressEnter={mcpCtrl.commitCatalog}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-text-muted">
                  {t("playground:composer.mcpCatalogIdLabel", "Catalog ID")}
                </label>
                <InputNumber
                  size="small"
                  min={0}
                  value={toolCatalogId ?? undefined}
                  onChange={(value) =>
                    setToolCatalogId(
                      typeof value === "number" && Number.isFinite(value)
                        ? value
                        : null
                    )
                  }
                  placeholder={t("playground:composer.mcpCatalogIdPlaceholder", "optional")}
                  className="w-full"
                />
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-text-muted">
                  {t("playground:composer.mcpCatalogStrictLabel", "Strict catalog filter")}
                </span>
                <Switch
                  size="small"
                  checked={toolCatalogStrict}
                  onChange={(checked) => setToolCatalogStrict(checked)}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-text-muted">
                  {t("playground:composer.mcpModuleLabel", "Module")}
                </label>
                <Select
                  size="small"
                  allowClear
                  showSearch
                  mode="multiple"
                  loading={moduleOptionsLoading}
                  disabled={moduleOptionsLoading || moduleOptions.length === 0}
                  value={toolModules.length > 0 ? toolModules : undefined}
                  placeholder={t("playground:composer.mcpModuleSelectPlaceholder", "Select modules")}
                  onChange={(value) => handleModuleSelect(value as string[] | undefined)}
                  optionFilterProp="label"
                  className="w-full"
                >
                  {moduleOptions.map((moduleId) => (
                    <Select.Option key={moduleId} value={moduleId} label={moduleId}>
                      <span className="text-sm">{moduleId}</span>
                    </Select.Option>
                  ))}
                </Select>
              </div>
              {isSmallModel && (
                <div className="rounded-md border border-border bg-surface2/60 px-2 py-1 text-[11px] text-text-muted">
                  {t(
                    "playground:composer.mcpSmallModelHint",
                    "Small/fast model: use catalog/module filters or the discovery tools (mcp.catalogs.list → mcp.modules.list → mcp.tools.list) to keep tool context light."
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
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
