import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import React from "react"
import useDynamicTextareaSize from "~/hooks/useDynamicTextareaSize"
import { toBase64 } from "~/libs/to-base64"
import { useMessageOption } from "~/hooks/useMessageOption"
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
  Button
} from "antd"
import { useWebUI } from "~/store/webui"
import { defaultEmbeddingModelForRag } from "~/services/tldw-server"
import {
  ChevronRight,
  EraserIcon,
  BookPlus,
  GitBranch,
  ImageIcon,
  MicIcon,
  Headphones,
  Hash,
  SlidersHorizontal,
  StopCircleIcon,
  Star,
  X,
  FileIcon,
  FileText,
  PaperclipIcon,
  Gauge,
  Search,
  CornerUpLeft,
  Settings2,
  HelpCircle,
  ArrowRight
} from "lucide-react"
import { getVariable } from "@/utils/select-variable"
import { useTranslation } from "react-i18next"
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition"
import { isFirefoxTarget } from "@/config/platform"
import { handleChatInputKeyDown } from "@/utils/key-down"
import { getIsSimpleInternetSearch } from "@/services/search"
import { getProviderDisplayName } from "@/utils/provider-registry"
import { formatPinnedResults } from "@/utils/rag-format"
import { useStorage } from "@plasmohq/storage/hook"
import { useTabMentions } from "~/hooks/useTabMentions"
import { useFocusShortcuts } from "~/hooks/keyboard"
import { isMac } from "@/hooks/useKeyboardShortcuts"
import { useDraftPersistence } from "@/hooks/useDraftPersistence"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { useVoiceChatSettings } from "@/hooks/useVoiceChatSettings"
import { useVoiceChatStream } from "@/hooks/useVoiceChatStream"
import { useVoiceChatMessages } from "@/hooks/useVoiceChatMessages"
import { MentionsDropdown } from "./MentionsDropdown"
import { otherUnsupportedTypes } from "../Knowledge/utils/unsupported-types"
import { PASTED_TEXT_CHAR_LIMIT } from "@/utils/constant"
import { isFireFoxPrivateMode } from "@/utils/is-private-mode"
import { CurrentChatModelSettings } from "@/components/Common/Settings/CurrentChatModelSettings"
import { ActorPopout } from "@/components/Common/Settings/ActorPopout"
import { PromptSelect } from "@/components/Common/PromptSelect"
import {
  PromptInsertModal,
  type PromptInsertItem
} from "@/components/Common/PromptInsertModal"
import { useConnectionState } from "@/hooks/useConnectionState"
import { ConnectionPhase } from "@/types/connection"
import { Link, useNavigate } from "react-router-dom"
import { fetchChatModels, fetchImageModels } from "@/services/tldw-server"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useTldwAudioStatus } from "@/hooks/useTldwAudioStatus"
import { useMcpTools } from "@/hooks/useMcpTools"
import { tldwChat, tldwModels, type ChatMessage } from "@/services/tldw"
import { tldwClient, type ConversationState } from "@/services/tldw/TldwApiClient"
import { CharacterSelect } from "@/components/Common/CharacterSelect"
import { ProviderIcons } from "@/components/Common/ProviderIcon"
import type { Character } from "@/types/character"
import { KnowledgePanel, type KnowledgeTab } from "@/components/Knowledge"
import { BetaTag } from "@/components/Common/Beta"
import {
  SlashCommandMenu,
  type SlashCommandItem
} from "@/components/Sidepanel/Chat/SlashCommandMenu"
import { DocumentGeneratorDrawer } from "@/components/Common/Playground/DocumentGeneratorDrawer"
import { useUiModeStore } from "@/store/ui-mode"
import { useStoreChatModelSettings } from "@/store/model"
import { TokenProgressBar } from "./TokenProgressBar"
import { AttachmentsSummary } from "./AttachmentsSummary"
import { VoiceChatIndicator } from "./VoiceChatIndicator"
import { VoiceModeSelector } from "./VoiceModeSelector"
import { PlaygroundTour, usePlaygroundTour } from "./PlaygroundTour"
import {
  ParameterPresets,
  SystemPromptTemplatesButton,
  SessionCostEstimation,
  type PromptTemplate
} from "./playground-features"
import { useMobile } from "@/hooks/useMediaQuery"
import { clearSetting, getSetting } from "@/services/settings/registry"
import { DISCUSS_MEDIA_PROMPT_SETTING } from "@/services/settings/ui-settings"
import { Button as TldwButton } from "@/components/Common/Button"
import { useSimpleForm } from "@/hooks/useSimpleForm"
import { useAntdNotification } from "@/hooks/useAntdNotification"

const getPersistenceModeLabel = (
  t: (...args: any[]) => any,
  temporaryChat: boolean,
  isConnectionReady: boolean,
  serverChatId: string | null
) => {
  if (temporaryChat) {
    return t(
      "playground:composer.persistence.ephemeral",
      "Not saved: cleared when you close this window."
    )
  }
  if (serverChatId || isConnectionReady) {
    return t(
      "playground:composer.persistence.server",
      "Saved to your tldw server (and locally)."
    )
  }
  return t(
    "playground:composer.persistence.local",
    "Saved locally until your tldw server is connected."
  )
}

type CollapsedRange = {
  start: number
  end: number
}

type ModelSortMode = "favorites" | "az" | "provider" | "localFirst"

const LOCAL_PROVIDERS = new Set([
  "lmstudio",
  "llamafile",
  "ollama",
  "ollama2",
  "llamacpp",
  "vllm",
  "custom",
  "local",
  "tldw",
  "chrome"
])

type Props = {
  droppedFiles: File[]
}

export const PlaygroundForm = ({ droppedFiles }: Props) => {
  const { t } = useTranslation(["playground", "common", "option"])
  const notificationApi = useAntdNotification()
  const inputRef = React.useRef<HTMLInputElement>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const processedFilesRef = React.useRef<WeakSet<File>>(new WeakSet())
  const navigate = useNavigate()

  const [typing, setTyping] = React.useState<boolean>(false)
  const [checkWideMode] = useStorage("checkWideMode", false)
  const {
    onSubmit,
    messages,
    selectedModel,
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
    ragPinnedResults
  } = useMessageOption()

  const [autoSubmitVoiceMessage] = useStorage("autoSubmitVoiceMessage", false)
  const isMobileViewport = useMobile()
  const [openModelSettings, setOpenModelSettings] = React.useState(false)
  const [openActorSettings, setOpenActorSettings] = React.useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = React.useState(false)
  const [modelSearchQuery, setModelSearchQuery] = React.useState("")
  const [favoriteModels, setFavoriteModels] = useStorage<string[]>(
    "favoriteChatModels",
    []
  )
  const [modelSortMode, setModelSortMode] = useStorage<ModelSortMode>(
    "modelSelectSortMode",
    "provider"
  )
  const apiProvider = useStoreChatModelSettings((state) => state.apiProvider)
  const numCtx = useStoreChatModelSettings((state) => state.numCtx)
  const systemPrompt = useStoreChatModelSettings((state) => state.systemPrompt)
  const setSystemPrompt = useStoreChatModelSettings(
    (state) => state.setSystemPrompt
  )
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
    if (import.meta?.env?.DEV) {
      console.count("PlaygroundForm/voiceChatTriggerPhrases")
    }
    setVoiceChatTriggerInput((prev) => (prev === next ? prev : next))
  }, [voiceChatTriggerPhrases])

  const { phase, isConnected } = useConnectionState()
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
  const [catalogDraft, setCatalogDraft] = React.useState(toolCatalog)

  React.useEffect(() => {
    setCatalogDraft(toolCatalog)
  }, [toolCatalog])

  const commitCatalog = React.useCallback(() => {
    const next = catalogDraft.trim()
    if (next !== toolCatalog) {
      setToolCatalog(next)
    }
    if (toolCatalogId !== null && next !== toolCatalog) {
      setToolCatalogId(null)
    }
  }, [catalogDraft, setToolCatalog, toolCatalog, toolCatalogId, setToolCatalogId])

  const catalogGroups = React.useMemo(() => {
    const global: typeof mcpCatalogs = []
    const org: typeof mcpCatalogs = []
    const team: typeof mcpCatalogs = []
    for (const catalog of mcpCatalogs) {
      if (!catalog) continue
      if (catalog.team_id != null) {
        team.push(catalog)
      } else if (catalog.org_id != null) {
        org.push(catalog)
      } else {
        global.push(catalog)
      }
    }
    return { global, org, team }
  }, [mcpCatalogs])

  const catalogById = React.useMemo(() => {
    const map = new Map<number, (typeof mcpCatalogs)[number]>()
    for (const catalog of mcpCatalogs) {
      if (catalog?.id == null) continue
      map.set(catalog.id, catalog)
    }
    return map
  }, [mcpCatalogs])

  const handleCatalogSelect = React.useCallback(
    (value?: number) => {
      if (value === null || value === undefined) {
        setToolCatalogId(null)
        setToolCatalog("")
        return
      }
      const catalog = catalogById.get(value)
      setToolCatalogId(value)
      if (catalog?.name) {
        setToolCatalog(catalog.name)
      }
    },
    [catalogById, setToolCatalog, setToolCatalogId]
  )

  const handleModuleSelect = React.useCallback(
    (value?: string[]) => {
      setToolModules(Array.isArray(value) ? value : [])
    },
    [setToolModules]
  )
  const hasServerAudio =
    isConnectionReady && !capsLoading && capabilities?.hasAudio
  const { healthState: audioHealthState } = useTldwAudioStatus()
  const canUseServerAudio = hasServerAudio && audioHealthState !== "unhealthy"
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
  const [promptInsertOpen, setPromptInsertOpen] = React.useState(false)
  const [promptInsertChoice, setPromptInsertChoice] =
    React.useState<PromptInsertItem | null>(null)
  const [documentGeneratorSeed, setDocumentGeneratorSeed] = React.useState<{
    conversationId?: string | null
    message?: string | null
    messageId?: string | null
  }>({})
  const [autoStopTimeout] = useStorage("autoStopTimeout", 2000)
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
  const [imageBackendDefault, setImageBackendDefault] = useStorage(
    "imageBackendDefault",
    ""
  )
  const [selectedCharacter] = useSelectedCharacter<Character | null>(null)
  const [serverPersistenceHintSeen, setServerPersistenceHintSeen] = useStorage(
    "serverPersistenceHintSeen",
    false
  )
  const [showServerPersistenceHint, setShowServerPersistenceHint] =
    React.useState(false)
  const serverSaveInFlightRef = React.useRef(false)
  const uiMode = useUiModeStore((state) => state.mode)
  const isProMode = uiMode === "pro"
  const { runTour, completeTour } = usePlaygroundTour()
  const [contextToolsOpen, setContextToolsOpen] = useStorage(
    "playgroundKnowledgeSearchOpen",
    false
  )
  const [knowledgePanelTab, setKnowledgePanelTab] =
    React.useState<KnowledgeTab>("search")
  const [knowledgePanelTabRequestId, setKnowledgePanelTabRequestId] =
    React.useState(0)
  const replyLabel = replyTarget
    ? [
        t("common:replyingTo", "Replying to"),
        replyTarget.name ? `${replyTarget.name}:` : null,
        replyTarget.preview
      ]
        .filter(Boolean)
        .join(" ")
    : ""

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

  // Auto-select model on initial load when no model is selected
  // Priority: 1) First favorite model, 2) First available model
  React.useEffect(() => {
    if (selectedModel || !composerModels?.length) return

    // Try to find first favorite model
    if (favoriteModels?.length) {
      const firstFavorite = (composerModels as any[]).find(m =>
        favoriteModels.includes(String(m.model))
      )
      if (firstFavorite) {
        setSelectedModel(firstFavorite.model)
        return
      }
    }

    // Fall back to first available model
    const firstModel = (composerModels as any[])[0]
    if (firstModel?.model) {
      setSelectedModel(firstModel.model)
    }
  }, [composerModels, selectedModel, favoriteModels, setSelectedModel])

  const compareModeActive = compareFeatureEnabled && compareMode

  const modelSummaryLabel = React.useMemo(() => {
    if (!selectedModel) {
      return t(
        "playground:composer.modelPlaceholder",
        "API / model"
      )
    }
    const models = (composerModels as any[]) || []
    const match = models.find((m) => m.model === selectedModel)
    return (
      match?.nickname ||
      match?.model ||
      selectedModel
    )
  }, [composerModels, selectedModel, t])

  const voiceChatModelOptions = React.useMemo(() => {
    const options = [
      {
        value: "",
        label: t("playground:voiceChat.useChatModel", "Use chat model")
      }
    ]
    const models = (composerModels as any[]) || []
    for (const model of models) {
      const providerLabel = getProviderDisplayName(model.provider || "")
      const modelLabel = model.nickname || model.model || model.name
      const label = providerLabel
        ? `${providerLabel} - ${modelLabel}`
        : modelLabel
      options.push({
        value: model.model || model.name,
        label
      })
    }
    return options
  }, [composerModels, t])

  const selectedModelMeta = React.useMemo(() => {
    if (!selectedModel) return null
    const models = (composerModels as any[]) || []
    return models.find((model) => model.model === selectedModel) || null
  }, [composerModels, selectedModel])

  const modelContextLength = React.useMemo(() => {
    const value =
      selectedModelMeta?.context_length ??
      selectedModelMeta?.contextLength ??
      selectedModelMeta?.details?.context_length
    return typeof value === "number" && Number.isFinite(value) ? value : null
  }, [selectedModelMeta])

  const modelCapabilities = React.useMemo(() => {
    const caps = selectedModelMeta?.details?.capabilities
    return Array.isArray(caps) ? caps.map((cap) => String(cap).toLowerCase()) : []
  }, [selectedModelMeta])

  const isSmallModel =
    modelCapabilities.includes("fast") ||
    (typeof modelContextLength === "number" && modelContextLength <= 8192)

  const resolvedMaxContext = React.useMemo(() => {
    if (typeof numCtx === "number" && Number.isFinite(numCtx) && numCtx > 0) {
      return numCtx
    }
    if (typeof modelContextLength === "number" && modelContextLength > 0) {
      return modelContextLength
    }
    return null
  }, [modelContextLength, numCtx])

  const resolvedProviderKey = React.useMemo(() => {
    const fromOverride = typeof apiProvider === "string" ? apiProvider.trim() : ""
    if (fromOverride) return fromOverride.toLowerCase()
    const provider =
      typeof selectedModelMeta?.provider === "string"
        ? selectedModelMeta.provider
        : "custom"
    return provider.toLowerCase()
  }, [apiProvider, selectedModelMeta])

  const providerLabel = React.useMemo(
    () => tldwModels.getProviderDisplayName(resolvedProviderKey || "custom"),
    [resolvedProviderKey]
  )

  const apiModelLabel = React.useMemo(() => {
    if (!selectedModel) {
      return t(
        "playground:composer.selectModel",
        "Select a model"
      )
    }
    return `${providerLabel} / ${modelSummaryLabel}`
  }, [modelSummaryLabel, providerLabel, selectedModel, t])

  // Whether model selector should show warning state (no model selected)
  const modelSelectorWarning = !selectedModel

  const favoriteModelSet = React.useMemo(
    () => new Set((favoriteModels || []).map((value) => String(value))),
    [favoriteModels]
  )

  const toggleFavoriteModel = React.useCallback(
    (modelId: string) => {
      void setFavoriteModels((prev) => {
        const list = Array.isArray(prev) ? prev.map(String) : []
        const next = new Set(list)
        if (next.has(modelId)) {
          next.delete(modelId)
        } else {
          next.add(modelId)
        }
        return Array.from(next)
      })
      setModelDropdownOpen(true)
    },
    [setFavoriteModels]
  )

  const filteredModels = React.useMemo(() => {
    const list = (composerModels as any[]) || []
    const q = modelSearchQuery.trim().toLowerCase()
    if (!q) return list
    return list.filter((model) => {
      const providerRaw = String(model.provider || "").toLowerCase()
      const providerLabel = getProviderDisplayName(providerRaw).toLowerCase()
      const name = String(model.nickname || model.model || "").toLowerCase()
      const modelId = String(model.model || "").toLowerCase()
      return (
        providerRaw.includes(q) ||
        providerLabel.includes(q) ||
        name.includes(q) ||
        modelId.includes(q)
      )
    })
  }, [composerModels, modelSearchQuery])

  const modelDropdownMenuItems = React.useMemo(() => {
    const models = filteredModels || []
    const allModels = (composerModels as any[]) || []

    if (allModels.length === 0) {
      return [
        {
          key: "no-models",
          disabled: true,
          label: (
            <div className="px-1 py-1 text-xs text-text-muted">
              {t(
                "playground:composer.noModelsAvailable",
                "No models available. Connect your server in Settings."
              )}
            </div>
          )
        },
        {
          type: "divider" as const,
          key: "no-models-divider"
        },
        {
          key: "open-model-settings",
          label: t(
            "playground:composer.openModelSettings",
            "Open model settings"
          ),
          onClick: () => navigate("/settings/tldw")
        }
      ]
    }

    if (models.length === 0) {
      return [
        {
          key: "no-matches",
          disabled: true,
          label: (
            <div className="px-1 py-1 text-xs text-text-muted">
              {t(
                "playground:composer.noModelsMatch",
                "No models match your search."
              )}
            </div>
          )
        }
      ]
    }

    const toProviderKey = (provider?: string) =>
      typeof provider === "string" && provider.trim()
        ? provider.trim().toLowerCase()
        : "other"

    const toGroupKey = (providerRaw: string) =>
      providerRaw === "chrome"
        ? "default"
        : LOCAL_PROVIDERS.has(providerRaw)
          ? "custom"
          : providerRaw

    const byLabel = (a: any, b: any) => {
      const aProvider = getProviderDisplayName(toProviderKey(a.provider))
      const bProvider = getProviderDisplayName(toProviderKey(b.provider))
      const aLabel = `${aProvider} ${a.nickname || a.model}`.toLowerCase()
      const bLabel = `${bProvider} ${b.nickname || b.model}`.toLowerCase()
      return aLabel.localeCompare(bLabel)
    }

    // Find first favorite for "(Recommended)" tag
    const firstFavoriteModel = favoriteModels?.length
      ? models.find(m => favoriteModels.includes(String(m.model)))?.model
      : null

    // Generate a brief description for a model based on its capabilities
    const getModelDescription = (model: any, capabilities: string[], contextLength: number | undefined) => {
      const parts: string[] = []
      const providerDisplay = getProviderDisplayName(toProviderKey(model.provider))

      // Add provider context
      parts.push(`${providerDisplay} model.`)

      // Add capability descriptions
      if (capabilities.includes("vision") || model.supportsVision) {
        parts.push("Can analyze images.")
      }
      if (capabilities.includes("tools") || model.supportsTools) {
        parts.push("Supports tool use and function calling.")
      }
      if (typeof contextLength === "number") {
        if (contextLength > 100000) {
          parts.push(`Long context (${Math.round(contextLength / 1000)}k tokens).`)
        } else if (contextLength > 0) {
          parts.push(`Context: ${Math.round(contextLength / 1000)}k tokens.`)
        }
      }
      if (capabilities.includes("fast") || model.fast) {
        parts.push("Optimized for speed.")
      }

      return parts.join(" ")
    }

    const buildItem = (model: any) => {
      const providerRaw = toProviderKey(model.provider)
      const modelLabel = model.nickname || model.model
      const isFavorite = favoriteModelSet.has(String(model.model))
      const isRecommended = firstFavoriteModel && String(model.model) === String(firstFavoriteModel)
      const favoriteTitle = isFavorite
        ? t("playground:composer.favoriteRemove", "Remove from favorites")
        : t("playground:composer.favoriteAdd", "Add to favorites")

      // Build capability badges (max 2)
      const capabilities = model.details?.capabilities || model.capabilities || []
      const contextLength = model.context_length ?? model.contextLength ?? model.details?.context_length
      const capabilityBadges: string[] = []
      if (capabilities.includes("vision") || model.supportsVision) capabilityBadges.push("Vision")
      if (capabilities.includes("fast") || model.fast) capabilityBadges.push("Fast")
      if (typeof contextLength === "number" && contextLength > 100000) capabilityBadges.push("Long context")
      if (capabilities.includes("tools") || model.supportsTools) capabilityBadges.push("Tools")

      // Generate tooltip description
      const modelDescription = getModelDescription(model, capabilities, contextLength)

      return {
        key: model.model,
        label: (
          <Tooltip
            title={modelDescription}
            placement="right"
            mouseEnterDelay={0.5}
            overlayStyle={{ maxWidth: 280 }}
          >
            <div className="flex items-center gap-2 text-sm">
              <ProviderIcons provider={providerRaw} className="h-3 w-3 text-text-subtle" />
              <span className="truncate flex-1">{modelLabel}</span>
              {isRecommended && (
                <span className="rounded-full bg-blue-100 dark:bg-blue-900/30 px-1.5 py-0.5 text-[10px] text-blue-600 dark:text-blue-400">
                  {t("playground:composer.recommended", "Recommended")}
                </span>
              )}
              {capabilityBadges.slice(0, 2).map(cap => (
                <span key={cap} className="rounded bg-surface2 px-1 py-0.5 text-[9px] text-text-muted">
                  {cap}
                </span>
              ))}
              <button
                type="button"
                className="rounded p-0.5 text-text-subtle transition hover:bg-surface2"
                onMouseDown={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                }}
                onClick={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                  toggleFavoriteModel(String(model.model))
                }}
                aria-label={favoriteTitle}
                title={favoriteTitle}
              >
                <Star
                  className={`h-3.5 w-3.5 ${
                    isFavorite ? "fill-warn text-warn" : "text-text-subtle"
                  }`}
                />
              </button>
            </div>
          </Tooltip>
        ),
        onClick: () => setSelectedModel(model.model)
      }
    }

    if (modelSortMode === "az") {
      return models.slice().sort(byLabel).map(buildItem)
    }

    if (modelSortMode === "favorites") {
      const favorites = models.filter((model) =>
        favoriteModelSet.has(String(model.model))
      )
      const others = models.filter(
        (model) => !favoriteModelSet.has(String(model.model))
      )
      const items: any[] = []
      if (favorites.length > 0) {
        items.push({
          type: "group" as const,
          key: "favorites",
          label: t("playground:composer.favorites", "Favorites"),
          children: favorites.slice().sort(byLabel).map(buildItem)
        })
      }
      items.push(...others.slice().sort(byLabel).map(buildItem))
      return items
    }

    const groups = new Map<string, any[]>()
    for (const model of models) {
      const providerRaw = toProviderKey(model.provider)
      const groupKey = toGroupKey(providerRaw)
      if (!groups.has(groupKey)) groups.set(groupKey, [])
      groups.get(groupKey)!.push(buildItem(model))
    }

    const entries = Array.from(groups.entries())
    if (modelSortMode === "localFirst") {
      entries.sort(([aKey], [bKey]) => {
        const aLocal = LOCAL_PROVIDERS.has(aKey) || aKey === "default"
        const bLocal = LOCAL_PROVIDERS.has(bKey) || bKey === "default"
        if (aLocal !== bLocal) return aLocal ? -1 : 1
        return aKey.localeCompare(bKey)
      })
    }

    return entries.map(([key, children]) => ({
      type: "group" as const,
      key: `group-${key}`,
      label: (
        <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-text-subtle">
          <ProviderIcons provider={key} className="h-3 w-3" />
          <span>{getProviderDisplayName(key)}</span>
        </div>
      ),
      children
    }))
  }, [
    composerModels,
    favoriteModels,
    favoriteModelSet,
    filteredModels,
    modelSearchQuery,
    modelSortMode,
    navigate,
    setSelectedModel,
    t,
    toggleFavoriteModel
  ])

  const sendLabel = React.useMemo(() => {
    if (compareModeActive && compareSelectedModels.length > 1) {
      return t("playground:composer.compareSendToModels", "Send to {{count}} models", {
        count: compareSelectedModels.length
      })
    }
    return t("common:send", "Send")
  }, [compareModeActive, compareSelectedModels.length, t])

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

  const setFieldValueRef = React.useRef(form.setFieldValue)
  React.useEffect(() => {
    setFieldValueRef.current = form.setFieldValue
  }, [form.setFieldValue])

  const pendingCaretRef = React.useRef<number | null>(null)
  const lastDisplaySelectionRef = React.useRef<{
    start: number
    end: number
  } | null>(null)
  const pendingCollapsedStateRef = React.useRef<{
    message: string
    range: CollapsedRange
    caret: number
  } | null>(null)
  const pointerDownRef = React.useRef(false)
  const selectionFromPointerRef = React.useRef(false)
  const [isMessageCollapsed, setIsMessageCollapsed] = React.useState(false)
  const [collapsedRange, setCollapsedRange] =
    React.useState<CollapsedRange | null>(null)
  const [hasExpandedLargeText, setHasExpandedLargeText] = React.useState(false)
  const normalizeCollapsedRange = React.useCallback(
    (range: CollapsedRange, messageLength: number): CollapsedRange => {
      const start = Math.max(0, Math.min(range.start, messageLength))
      const end = Math.max(start, Math.min(range.end, messageLength))
      return { start, end }
    },
    []
  )

  const parseCollapsedRange = React.useCallback(
    (value: unknown, messageLength: number): CollapsedRange | null => {
      if (!value || typeof value !== "object") return null
      const start = Number((value as { start?: number }).start)
      const end = Number((value as { end?: number }).end)
      if (!Number.isFinite(start) || !Number.isFinite(end)) return null
      const range = normalizeCollapsedRange({ start, end }, messageLength)
      if (range.end <= range.start) return null
      return range
    },
    [normalizeCollapsedRange]
  )

  const restoreMessageValue = React.useCallback(
    (
      value: string,
      metadata?: { wasExpanded?: boolean; collapsedRange?: CollapsedRange | null }
    ) => {
      setFieldValueRef.current("message", value)
      if (value.length <= PASTED_TEXT_CHAR_LIMIT) {
        setIsMessageCollapsed(false)
        setHasExpandedLargeText(false)
        setCollapsedRange(null)
        return
      }
      const wasExpanded = Boolean(metadata?.wasExpanded)
      if (wasExpanded) {
        setIsMessageCollapsed(false)
        setHasExpandedLargeText(true)
        setCollapsedRange(null)
        return
      }
      const range =
        parseCollapsedRange(metadata?.collapsedRange, value.length) ?? {
          start: 0,
          end: value.length
        }
      setIsMessageCollapsed(true)
      setHasExpandedLargeText(false)
      setCollapsedRange(range)
    },
    [parseCollapsedRange]
  )

  const buildCollapsedMessageLabel = React.useCallback(
    (text: string) => {
      // Avoid allocating an array for very large messages.
      const lineCount =
        text ? (text.match(/\r\n|\r|\n/g)?.length ?? 0) + 1 : 0
      return t(
        "playground:composer.collapsedMessageLabel",
        "[{lines, plural, one {# line} other {# lines}}/{chars, plural, one {# char} other {# chars}} in message]",
        { lines: lineCount, chars: text.length }
      )
    },
    [t]
  )

  const getCollapsedDisplayMeta = React.useCallback(
    (text: string, range: CollapsedRange) => {
      const normalizedRange = normalizeCollapsedRange(range, text.length)
      const collapsedText = text.slice(
        normalizedRange.start,
        normalizedRange.end
      )
      const label = buildCollapsedMessageLabel(collapsedText)
      const prefix = text.slice(0, normalizedRange.start)
      const suffix = text.slice(normalizedRange.end)
      const labelStart = prefix.length
      const labelEnd = labelStart + label.length
      const blockLength = normalizedRange.end - normalizedRange.start
      return {
        display: `${prefix}${label}${suffix}`,
        label,
        labelStart,
        labelEnd,
        labelLength: label.length,
        blockLength,
        rangeStart: normalizedRange.start,
        rangeEnd: normalizedRange.end,
        messageLength: text.length
      }
    },
    [buildCollapsedMessageLabel, normalizeCollapsedRange]
  )

  const getDisplayCaretFromMessage = React.useCallback(
    (
      messageCaret: number,
      meta: ReturnType<typeof getCollapsedDisplayMeta>
    ) => {
      if (messageCaret <= meta.rangeStart) return messageCaret
      if (messageCaret >= meta.rangeEnd) {
        return (
          messageCaret -
          meta.blockLength +
          meta.labelLength
        )
      }
      return meta.labelEnd
    },
    []
  )

  const getMessageCaretFromDisplay = React.useCallback(
    (
      displayCaret: number,
      meta: ReturnType<typeof getCollapsedDisplayMeta>,
      options?: { prefer?: "before" | "after" }
    ) => {
      if (displayCaret <= meta.labelStart) return displayCaret
      if (displayCaret >= meta.labelEnd) {
        return (
          displayCaret -
          meta.labelLength +
          meta.blockLength
        )
      }
      return options?.prefer === "before"
        ? meta.rangeStart
        : meta.rangeEnd
    },
    []
  )

  const collapseLargeMessage = React.useCallback(
    (text: string, options?: { force?: boolean; range?: CollapsedRange }) => {
      if (text.length <= PASTED_TEXT_CHAR_LIMIT) {
        setIsMessageCollapsed(false)
        setHasExpandedLargeText(false)
        setCollapsedRange(null)
        return
      }
      if (!options?.force && hasExpandedLargeText) return
      const range =
        options?.range ?? { start: 0, end: text.length }
      const normalizedRange = normalizeCollapsedRange(range, text.length)
      setIsMessageCollapsed(true)
      setHasExpandedLargeText(false)
      setCollapsedRange(normalizedRange)
    },
    [hasExpandedLargeText, normalizeCollapsedRange]
  )

  const expandLargeMessage = React.useCallback(
    (options?: { caret?: number; force?: boolean }) => {
      if (!isMessageCollapsed && !options?.force) return
      setIsMessageCollapsed(false)
      setHasExpandedLargeText(true)
      setCollapsedRange(null)
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        const caret =
          typeof options?.caret === "number"
            ? Math.min(options.caret, el.value.length)
            : pendingCaretRef.current ?? el.value.length
        pendingCaretRef.current = null
        el.focus()
        el.setSelectionRange(caret, caret)
      })
    },
    [isMessageCollapsed, textareaRef]
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

  const numberFormatter = React.useMemo(() => new Intl.NumberFormat(), [])
  const formatNumber = React.useCallback(
    (value: number | null) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return "—"
      return numberFormatter.format(Math.round(value))
    },
    [numberFormatter]
  )

  const estimateTokensForText = React.useCallback((text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return 0
    return tldwChat.estimateTokens([
      { role: "user", content: trimmed }
    ])
  }, [])

  const draftTokenCount = React.useMemo(
    () => estimateTokensForText(form.values.message || ""),
    [estimateTokensForText, form.values.message]
  )

  const conversationTokenCountRef = React.useRef(0)
  const conversationTokenCount = React.useMemo(() => {
    if (isSending) {
      return conversationTokenCountRef.current
    }
    const convoMessages: ChatMessage[] = []
    const trimmedSystem = systemPrompt?.trim()
    if (trimmedSystem) {
      convoMessages.push({ role: "system", content: trimmedSystem })
    }
    messages.forEach((message) => {
      const content = typeof message.message === "string" ? message.message.trim() : ""
      if (!content) return
      if (message.isBot) {
        convoMessages.push({ role: "assistant", content })
      } else {
        convoMessages.push({ role: "user", content })
      }
    })
    if (convoMessages.length === 0) return 0
    const count = tldwChat.estimateTokens(convoMessages)
    conversationTokenCountRef.current = count
    return count
  }, [isSending, messages, systemPrompt])

  const promptTokenLabel = React.useMemo(
    () =>
      `${t("playground:tokens.prompt", "prompt")} ${formatNumber(draftTokenCount)}`,
    [draftTokenCount, formatNumber, t]
  )
  const convoTokenLabel = React.useMemo(
    () =>
      `${t("playground:tokens.total", "tokens")} ${formatNumber(conversationTokenCount)}`,
    [conversationTokenCount, formatNumber, t]
  )
  const contextTokenLabel = React.useMemo(
    () => `${formatNumber(resolvedMaxContext)} ctx`,
    [formatNumber, resolvedMaxContext]
  )
  const tokenUsageLabel = React.useMemo(
    () => `${promptTokenLabel} · ${convoTokenLabel} / ${contextTokenLabel}`,
    [contextTokenLabel, convoTokenLabel, promptTokenLabel]
  )
  const tokenUsageCompactLabel = React.useMemo(() => {
    const prompt = formatNumber(draftTokenCount)
    const convo = formatNumber(conversationTokenCount)
    const ctx = formatNumber(resolvedMaxContext)
    return `${prompt} · ${convo}/${ctx} ctx`
  }, [conversationTokenCount, draftTokenCount, formatNumber, resolvedMaxContext])
  const tokenUsageDisplay = isProMode
    ? tokenUsageLabel
    : tokenUsageCompactLabel
  const contextLabel = React.useMemo(
    () =>
      t(
        "common:modelSettings.form.numCtx.label",
        "Context Window Size (num_ctx)"
      ),
    [t]
  )
  const tokenUsageTooltip = React.useMemo(
    () =>
      `${apiModelLabel} · ${promptTokenLabel} · ${convoTokenLabel} · ${contextLabel} ${formatNumber(resolvedMaxContext)}`,
    [
      apiModelLabel,
      contextLabel,
      convoTokenLabel,
      formatNumber,
      promptTokenLabel,
      resolvedMaxContext
    ]
  )

  const imageBackendOptions = React.useMemo<
    { value: string; label: string; provider?: string }[]
  >(() => {
    const dynamicOptions = (imageModels || [])
      .filter((model: any) => model && model.id)
      .map((model: any) => ({
        value: String(model.id),
        label: String(model.name || model.id),
        provider: model.provider ? String(model.provider) : undefined
      }))

    const fallbackOptions = [
      {
        value: "tldw_server-Flux-Klein",
        label: t("playground:imageBackend.fluxKlein", "Flux-Klein"),
        provider: undefined
      },
      {
        value: "tldw_server-ZTurbo",
        label: t("playground:imageBackend.zTurbo", "ZTurbo"),
        provider: undefined
      }
    ]

    const baseOptions = dynamicOptions.length > 0 ? dynamicOptions : fallbackOptions
    return [
      {
        value: "",
        label: t("playground:imageBackend.none", "None")
      },
      ...baseOptions
    ]
  }, [imageModels, t])
  const imageBackendDefaultTrimmed = React.useMemo(
    () => (imageBackendDefault || "").trim(),
    [imageBackendDefault]
  )
  const imageBackendLabel = React.useMemo(() => {
    if (!imageBackendDefaultTrimmed) {
      return t("playground:imageBackend.none", "None")
    }
    const match = imageBackendOptions.find(
      (option) => option.value === imageBackendDefaultTrimmed
    )
    if (match?.provider) {
      return `${getProviderDisplayName(match.provider)} · ${match.label}`
    }
    return match?.label || imageBackendDefaultTrimmed
  }, [imageBackendDefaultTrimmed, imageBackendOptions, t])
  const imageBackendActiveKey =
    imageBackendDefaultTrimmed.length > 0 ? imageBackendDefaultTrimmed : "none"
  const imageBackendMenuItems = React.useMemo(
    () =>
      imageBackendOptions.map((option: any) => {
        const providerLabel = option.provider
          ? getProviderDisplayName(option.provider)
          : null
        const labelText = providerLabel
          ? `${providerLabel} · ${option.label}`
          : option.label
        return {
          key: option.value || "none",
          label: (
            <div className="flex items-center gap-2 text-sm">
              <ImageIcon className="h-3 w-3 text-text-subtle" />
              <span className="truncate">{labelText}</span>
            </div>
          ),
          onClick: () => setImageBackendDefault(option.value)
        }
      }),
    [imageBackendOptions, setImageBackendDefault]
  )
  const imageBackendBadgeLabel = imageBackendDefaultTrimmed
    ? t("playground:imageBackend.badge", "Image: {{backend}}", {
        backend: imageBackendLabel
      })
    : t("playground:imageBackend.noneBadge", "Image: none")

  const showModelLabel = !isProMode
  const modelUsageBadge = (
    <div className="inline-flex items-center gap-2">
      {showModelLabel && (
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
          dropdownRender={(menu) => (
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
              data-testid="model-selector"
              className={`inline-flex min-w-0 items-center gap-1 rounded-full border px-2 h-9 text-[10px] cursor-pointer transition-colors ${
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
            </button>
          </Tooltip>
        </Dropdown>
      )}
      <TokenProgressBar
        conversationTokens={conversationTokenCount}
        draftTokens={draftTokenCount}
        maxTokens={resolvedMaxContext}
        modelLabel={isProMode ? apiModelLabel : undefined}
        compact={!isProMode}
      />
    </div>
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

  const buildDiscussMediaHint = (payload: {
    mediaId?: string
    url?: string
    title?: string
    content?: string
  }): string => {
    if (payload?.content && (payload.title || payload.mediaId)) {
      const header = `Chat with this media: ${
        payload.title || payload.mediaId
      }`.trim()
      return `${header}\n\n${payload.content}`.trim()
    }
    if (payload?.url) {
      return `Let's talk about the media I just ingested: ${payload.url}`
    }
    if (payload?.mediaId) {
      return `Let's talk about media ${payload.mediaId}.`
    }
    return ""
  }

  // Seed composer when a media item requests discussion (e.g., from Quick ingest or Review page)
  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const payload = await getSetting(DISCUSS_MEDIA_PROMPT_SETTING)
      if (cancelled || !payload) return
      void clearSetting(DISCUSS_MEDIA_PROMPT_SETTING)
      const hint = buildDiscussMediaHint(payload)
      if (!hint) return
      setMessageValue(hint, { collapseLarge: true, forceCollapse: true })
      textAreaFocus()
    })()
    return () => {
      cancelled = true
    }
  }, [setMessageValue, textAreaFocus])

  React.useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as any
      if (!detail) return
      const hint = buildDiscussMediaHint(detail || {})
      if (!hint) return
      setMessageValue(hint, { collapseLarge: true, forceCollapse: true })
      textAreaFocus()
    }
    window.addEventListener("tldw:discuss-media", handler as any)
    return () => {
      window.removeEventListener("tldw:discuss-media", handler as any)
    }
  }, [setMessageValue, textAreaFocus])

  React.useEffect(() => {
    textAreaFocus()
  }, [textAreaFocus])

  React.useEffect(() => {
    if (import.meta?.env?.DEV) {
      console.count("PlaygroundForm/defaultInternetSearchOn")
    }
    if (defaultInternetSearchOn && !webSearch) {
      setWebSearch(true)
    }
  }, [defaultInternetSearchOn, webSearch, setWebSearch])

  React.useEffect(() => {
    if (isConnectionReady) {
      setShowConnectBanner(false)
    }
  }, [isConnectionReady])

  React.useEffect(() => {
    if (import.meta?.env?.DEV) {
      console.count("PlaygroundForm/queuedMessagesBanner")
    }
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
  const { sendWhenEnter, setSendWhenEnter } = useWebUI()
  const speechAvailable =
    browserSupportsSpeechRecognition || canUseServerAudio
  const speechUsesServer = canUseServerAudio

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

  const applySystemPrompt = React.useCallback(
    (nextPrompt: string) => {
      setSelectedSystemPrompt(null)
      setSystemPrompt(nextPrompt)
    },
    [setSelectedSystemPrompt, setSystemPrompt]
  )

  const insertMessageAtCaret = React.useCallback(
    (text: string) => {
      if (!text) return
      const currentValue = form.values.message || ""
      if (isMessageCollapsed && collapsedRange) {
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
          replaceCollapsedRange(currentValue, meta, editStart, editEnd, text)
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
        replaceCollapsedRange(currentValue, meta, insertAt, insertAt, text)
        return
      }
      const textarea = textareaRef.current
      const selectionStart = textarea?.selectionStart ?? currentValue.length
      const selectionEnd = textarea?.selectionEnd ?? selectionStart
      const nextValue =
        currentValue.slice(0, selectionStart) +
        text +
        currentValue.slice(selectionEnd)
      if (nextValue.length > PASTED_TEXT_CHAR_LIMIT) {
        const blockRange = {
          start: selectionStart,
          end: selectionStart + text.length
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
        return
      }
      setMessageValue(nextValue, { collapseLarge: true })
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        const nextCaret = selectionStart + text.length
        el.focus()
        el.setSelectionRange(nextCaret, nextCaret)
      })
    },
    [
      collapsedRange,
      form.values.message,
      getCollapsedDisplayMeta,
      getMessageCaretFromDisplay,
      isMessageCollapsed,
      replaceCollapsedRange,
      setMessageValue,
      textareaRef
    ]
  )

  const handlePromptInsert = React.useCallback(
    (prompt: PromptInsertItem) => {
      setPromptInsertOpen(false)
      const hasSystem = Boolean(prompt.systemPrompt?.trim())
      const hasUser = Boolean(prompt.userPrompt?.trim())
      if (hasSystem && hasUser) {
        setPromptInsertChoice(prompt)
        return
      }
      if (hasSystem && prompt.systemPrompt) {
        applySystemPrompt(prompt.systemPrompt)
        return
      }
      if (hasUser && prompt.userPrompt) {
        insertMessageAtCaret(prompt.userPrompt)
      }
    },
    [
      applySystemPrompt,
      insertMessageAtCaret,
      setPromptInsertChoice,
      setPromptInsertOpen
    ]
  )

  const queryClient = useQueryClient()
  const invalidateServerChatHistory = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
  }, [queryClient])

  const { mutateAsync: sendMessage } = useMutation({
    mutationFn: onSubmit,
    onSuccess: () => {
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
      if (!ragPinnedResults || ragPinnedResults.length === 0) return message
      const pinnedText = formatPinnedResults(ragPinnedResults, "markdown")
      return message ? `${message}\n\n${pinnedText}` : pinnedText
    },
    [ragPinnedResults]
  )

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
          if (!selectedModel || selectedModel.length === 0) {
            form.setFieldError("message", t("formError.noModel"))
            return
          }
        } else if (!compareSelectedModels || compareSelectedModels.length === 0) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareSelectModelsInline",
              "Select at least one model for Compare mode."
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
          : undefined
      })
    })()
  }

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
          if (!selectedModel || selectedModel.length === 0) {
            form.setFieldError("message", t("formError.noModel"))
            return
          }
        } else if (!compareSelectedModels || compareSelectedModels.length === 0) {
          form.setFieldError(
            "message",
            t(
              "playground:composer.validationCompareSelectModelsInline",
              "Select at least one model for Compare mode."
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
          : undefined
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

  const handleImageUpload = React.useCallback(() => {
    inputRef.current?.click()
  }, [])

  const handleDocumentUpload = React.useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const slashCommands = React.useMemo<SlashCommandItem[]>(
    () => [
      {
        id: "slash-search",
        command: "search",
        label: t(
          "common:commandPalette.toggleKnowledgeSearch",
          "Toggle Search & Context"
        ),
        description: t(
          "common:commandPalette.toggleKnowledgeSearchDesc",
          "Search your knowledge base and context"
        ),
        keywords: ["rag", "context", "knowledge", "search"],
        action: () => setChatMode(chatMode === "rag" ? "normal" : "rag")
      },
      {
        id: "slash-web",
        command: "web",
        label: t(
          "common:commandPalette.toggleWebSearch",
          "Toggle Web Search"
        ),
        description: t(
          "common:commandPalette.toggleWebDesc",
          "Search the internet"
        ),
        keywords: ["web", "internet", "browse"],
        action: () => setWebSearch(!webSearch)
      },
      {
        id: "slash-vision",
        command: "vision",
        label: t("playground:actions.upload", "Attach image"),
        description: t(
          "playground:composer.slashVisionDesc",
          "Attach an image for vision"
        ),
        keywords: ["image", "ocr", "vision"],
        action: handleImageUpload
      },
      {
        id: "slash-generate-image",
        command: "generate-image",
        label: t(
          "playground:composer.slashGenerateImage",
          "Generate image"
        ),
        description: imageBackendDefaultTrimmed
          ? t(
              "playground:composer.slashGenerateImageDescDefault",
              "Generate an image (default: {{backend}}). Use /generate-image:<provider> to override.",
              { backend: imageBackendLabel }
            )
          : t(
              "playground:composer.slashGenerateImageDesc",
              "Generate an image. Use /generate-image:<provider> <prompt>."
            ),
        keywords: ["image", "image gen", "flux", "zturbo", "art"],
        insertText: imageBackendDefaultTrimmed
          ? "/generate-image "
          : "/generate-image:"
      },
      {
        id: "slash-model",
        command: "model",
        label: t("common:commandPalette.switchModel", "Switch Model"),
        description: t(
          "common:currentChatModelSettings",
          "Open current chat settings"
        ),
        keywords: ["settings", "parameters", "temperature"],
        action: () => setOpenModelSettings(true)
      }
    ],
    [
      chatMode,
      handleImageUpload,
      imageBackendDefaultTrimmed,
      imageBackendLabel,
      setChatMode,
      setWebSearch,
      t,
      webSearch,
      setOpenModelSettings
    ]
  )

  const slashCommandLookup = React.useMemo(
    () => new Map(slashCommands.map((command) => [command.command, command])),
    [slashCommands]
  )

  const slashMatch = React.useMemo(
    () => form.values.message.match(/^\s*\/([\w-]*)$/),
    [form.values.message]
  )
  const slashQuery = slashMatch?.[1] ?? ""
  const showSlashMenu = Boolean(slashMatch)
  const [slashActiveIndex, setSlashActiveIndex] = React.useState(0)

  const filteredSlashCommands = React.useMemo(() => {
    if (!slashQuery) return slashCommands
    const q = slashQuery.toLowerCase()
    return slashCommands.filter((command) => {
      if (command.command.startsWith(q)) return true
      if (command.label.toLowerCase().includes(q)) return true
      return (command.keywords || []).some((keyword) =>
        keyword.toLowerCase().includes(q)
      )
    })
  }, [slashCommands, slashQuery])

  React.useEffect(() => {
    if (!showSlashMenu) {
      setSlashActiveIndex(0)
      return
    }
    setSlashActiveIndex((prev) => {
      if (filteredSlashCommands.length === 0) return 0
      return Math.min(prev, filteredSlashCommands.length - 1)
    })
  }, [showSlashMenu, filteredSlashCommands.length, slashQuery])

  const parseSlashInput = React.useCallback((text: string) => {
    const trimmed = text.trimStart()
    const match = trimmed.match(/^\/(\w+)(?:\s+([\s\S]*))?$/)
    if (!match) return null
    return {
      command: match[1].toLowerCase(),
      remainder: match[2] || ""
    }
  }, [])

  const parseImageSlashCommand = React.useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed.toLowerCase().startsWith("/generate-image")) return null
      const remainder = trimmed.slice("/generate-image".length)
      const colonMatch = remainder.match(
        /^\s*:\s*([^\s]+)(?:\s+([\s\S]*))?$/i
      )
      if (colonMatch) {
        const provider = colonMatch[1]?.trim() || ""
        const prompt = (colonMatch[2] || "").trim()
        const missingProvider = provider.length === 0
        return {
          provider,
          prompt,
          invalid: missingProvider,
          missingProvider
        }
      }

      const prompt = remainder.trim()
      if (imageBackendDefaultTrimmed) {
        return {
          provider: imageBackendDefaultTrimmed,
          prompt,
          invalid: false,
          missingProvider: false
        }
      }

      return {
        provider: "",
        prompt,
        invalid: true,
        missingProvider: true
      }
    },
    [imageBackendDefaultTrimmed]
  )

  const applySlashCommand = React.useCallback(
    (text: string) => {
      const parsed = parseSlashInput(text)
      if (!parsed) {
        return { handled: false, message: text }
      }
      const command = slashCommandLookup.get(parsed.command)
      if (!command) {
        return { handled: false, message: text }
      }
      command.action()
      return { handled: true, message: parsed.remainder }
    },
    [parseSlashInput, slashCommandLookup]
  )

  const resolveSubmissionIntent = React.useCallback(
    (rawMessage: string) => {
      const imageCommand = parseImageSlashCommand(rawMessage)
      if (imageCommand) {
        return {
          handled: true,
          message: imageCommand.prompt,
          imageBackendOverride: imageCommand.provider,
          isImageCommand: true,
          invalidImageCommand: imageCommand.invalid,
          imageCommandMissingProvider: Boolean(imageCommand.missingProvider)
        }
      }
      const slashResult = applySlashCommand(rawMessage)
      return {
        handled: slashResult.handled,
        message: slashResult.handled ? slashResult.message : rawMessage,
        imageBackendOverride: undefined,
        isImageCommand: false,
        invalidImageCommand: false,
        imageCommandMissingProvider: false
      }
    },
    [applySlashCommand, parseImageSlashCommand]
  )
  const activeImageCommand = React.useMemo(
    () => Boolean(parseImageSlashCommand(form.values.message)),
    [form.values.message, parseImageSlashCommand]
  )

  const handleSlashCommandSelect = React.useCallback(
    (command: SlashCommandItem) => {
      const parsed = parseSlashInput(form.values.message)
      if (command.insertText) {
        form.setFieldValue("message", command.insertText)
        requestAnimationFrame(() => textareaRef.current?.focus())
        return
      }
      command.action?.()
      form.setFieldValue("message", parsed?.remainder || "")
      requestAnimationFrame(() => textareaRef.current?.focus())
    },
    [form, parseSlashInput, textareaRef]
  )

  const serverRecorderRef = React.useRef<MediaRecorder | null>(null)
  const serverChunksRef = React.useRef<BlobPart[]>([])
  const [isServerDictating, setIsServerDictating] = React.useState(false)

  const stopServerDictation = React.useCallback(() => {
    const rec = serverRecorderRef.current
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop()
      } catch {}
    }
  }, [])

  const handleSpeechToggle = React.useCallback(() => {
    if (isListening) {
      stopSpeechRecognition()
    } else {
      resetTranscript()
      startListening({
        continuous: true,
        lang: speechToTextLanguage
      })
    }
  }, [isListening, resetTranscript, speechToTextLanguage, startListening, stopSpeechRecognition])

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

  const handleServerDictationToggle = React.useCallback(async () => {
    if (isServerDictating) {
      stopServerDictation()
      return
    }
    if (!canUseServerAudio) {
      notificationApi.error({
        message: t(
          "playground:actions.speechUnavailableTitle",
          "Dictation unavailable"
        ),
        description: t(
          "playground:actions.speechUnavailableBody",
          "Connect to a tldw server that exposes the audio transcriptions API to use dictation."
        )
      })
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      serverChunksRef.current = []
      recorder.ondataavailable = (ev: BlobEvent) => {
        if (ev.data && ev.data.size > 0) {
          serverChunksRef.current.push(ev.data)
        }
      }
      recorder.onerror = (event: Event) => {
        console.error("MediaRecorder error", event)
        notificationApi.error({
          message: t("playground:actions.speechErrorTitle", "Dictation failed"),
          description: t(
            "playground:actions.speechErrorBody",
            "Microphone recording error. Check your permissions and try again."
          )
        })
      }
      recorder.onstop = async () => {
        try {
          const blob = new Blob(serverChunksRef.current, {
            type: recorder.mimeType || "audio/webm"
          })
          if (blob.size === 0) {
            return
          }
          const sttOptions: Record<string, any> = {
            language: speechToTextLanguage
          }
          if (sttModel && sttModel.trim().length > 0) {
            sttOptions.model = sttModel.trim()
          }
          if (sttTimestampGranularities) {
            sttOptions.timestamp_granularities = sttTimestampGranularities
          }
          if (sttPrompt && sttPrompt.trim().length > 0) {
            sttOptions.prompt = sttPrompt.trim()
          }
          if (sttTask) {
            sttOptions.task = sttTask
          }
          if (sttResponseFormat) {
            sttOptions.response_format = sttResponseFormat
          }
          if (typeof sttTemperature === "number") {
            sttOptions.temperature = sttTemperature
          }
          if (sttUseSegmentation) {
            sttOptions.segment = true
            if (typeof sttSegK === "number") {
              sttOptions.seg_K = sttSegK
            }
            if (typeof sttSegMinSegmentSize === "number") {
              sttOptions.seg_min_segment_size = sttSegMinSegmentSize
            }
            if (typeof sttSegLambdaBalance === "number") {
              sttOptions.seg_lambda_balance = sttSegLambdaBalance
            }
            if (typeof sttSegUtteranceExpansionWidth === "number") {
              sttOptions.seg_utterance_expansion_width =
                sttSegUtteranceExpansionWidth
            }
            if (sttSegEmbeddingsProvider?.trim()) {
              sttOptions.seg_embeddings_provider =
                sttSegEmbeddingsProvider.trim()
            }
            if (sttSegEmbeddingsModel?.trim()) {
              sttOptions.seg_embeddings_model = sttSegEmbeddingsModel.trim()
            }
          }
          const res = await tldwClient.transcribeAudio(blob, sttOptions)
          let text = ""
          if (res) {
            if (typeof res === "string") {
              text = res
            } else if (typeof (res as any).text === "string") {
              text = (res as any).text
            } else if (typeof (res as any).transcript === "string") {
              text = (res as any).transcript
            } else if (Array.isArray((res as any).segments)) {
              text = (res as any).segments
                .map((s: any) => s?.text || "")
                .join(" ")
                .trim()
            }
          }
          if (text) {
            setMessageValue(text, { collapseLarge: true, forceCollapse: true })
          } else {
            notificationApi.error({
              message: t("playground:actions.speechErrorTitle", "Dictation failed"),
              description: t(
                "playground:actions.speechNoText",
                "The transcription did not return any text."
              )
            })
          }
        } catch (e: any) {
          notificationApi.error({
            message: t("playground:actions.speechErrorTitle", "Dictation failed"),
            description: e?.message || t(
              "playground:actions.speechErrorBody",
              "Transcription request failed. Check tldw server health."
            )
          })
        } finally {
          try {
            stream.getTracks().forEach((trk) => trk.stop())
          } catch {}
          serverRecorderRef.current = null
          setIsServerDictating(false)
        }
      }
      serverRecorderRef.current = recorder
      recorder.start()
      setIsServerDictating(true)
    } catch (e: any) {
      notificationApi.error({
        message: t("playground:actions.speechErrorTitle", "Dictation failed"),
        description: t(
          "playground:actions.speechMicError",
          "Unable to access your microphone. Check browser permissions and try again."
        )
      })
    }
  }, [
    canUseServerAudio,
    isServerDictating,
    notificationApi,
    speechToTextLanguage,
    sttModel,
    sttTimestampGranularities,
    sttUseSegmentation,
    setMessageValue,
    stopServerDictation,
    t
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

  const moreToolsContent = React.useMemo(
    () => (
      <div className="flex w-72 flex-col gap-2 p-1">
        {/* SEARCH & CONTEXT Section */}
        <div className="flex flex-col gap-2">
          <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider px-2">
            {t("playground:tools.searchContext", "Search & Context")}
          </span>
          <button
            type="button"
            onClick={() => toggleKnowledgePanel("search")}
            aria-pressed={contextToolsOpen}
            title={
              contextToolsOpen
                ? (t(
                    "playground:composer.contextKnowledgeClose",
                    "Close Search & Context"
                  ) as string)
                : (t(
                    "playground:composer.contextKnowledge",
                    "Knowledge Search"
                  ) as string)
            }
            className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm transition ${
              contextToolsOpen
                ? "bg-surface2 text-accent"
                : "text-text hover:bg-surface2"
            }`}
          >
            <span>
              {t("playground:composer.contextKnowledge", "Knowledge Search")}
            </span>
            <Search className="h-4 w-4" />
          </button>
          <div className="flex items-center justify-between px-2">
            <span className="text-sm text-text">
              {t("playground:actions.webSearchOff", "Web search")}
            </span>
            <Switch
              size="small"
              checked={webSearch}
              onChange={(value) => setWebSearch(value)}
            />
          </div>
        </div>

        <div className="border-t border-border my-1" />

        {/* ATTACHMENTS Section */}
        <div className="flex flex-col gap-2">
          <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider px-2">
            {t("playground:tools.attachments", "Attachments")}
          </span>
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
                      ? "text-red-600"
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

            {/* MCP Tools Summary */}
            {hasMcp && (
              <div className="px-2 py-1">
                <div className="text-xs font-semibold text-text-muted mb-1">
                  {t("playground:composer.mcpToolsLabel", "MCP tools")}
                </div>
                <span className="text-xs text-text-muted">
                  {mcpToolsLoading
                    ? t("playground:composer.mcpToolsLoading", "Loading tools...")
                    : t("playground:tools.mcpSummary", "{{count}} tools available", { count: mcpTools.length })}
                </span>
                <div className="mt-2 flex flex-col gap-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-text-muted">
                      {t("playground:composer.mcpCatalogLabel", "Catalog")}
                    </label>
                    <Select
                      size="small"
                      allowClear
                      showSearch
                      loading={mcpCatalogsLoading}
                      value={toolCatalogId ?? undefined}
                      placeholder={t("playground:composer.mcpCatalogSelectPlaceholder", "Select a catalog")}
                      onChange={(value) => handleCatalogSelect(value as number | undefined)}
                      optionFilterProp="label"
                      className="w-full"
                    >
                      {catalogGroups.team.length > 0 && (
                        <Select.OptGroup label={t("playground:composer.mcpCatalogTeam", "Team catalogs")}>
                          {catalogGroups.team.map((catalog) => (
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
                      {catalogGroups.org.length > 0 && (
                        <Select.OptGroup label={t("playground:composer.mcpCatalogOrg", "Org catalogs")}>
                          {catalogGroups.org.map((catalog) => (
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
                      {catalogGroups.global.length > 0 && (
                        <Select.OptGroup label={t("playground:composer.mcpCatalogGlobal", "Global catalogs")}>
                          {catalogGroups.global.map((catalog) => (
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
                      value={catalogDraft}
                      onChange={(e) => setCatalogDraft(e.target.value)}
                      onBlur={commitCatalog}
                      onPressEnter={commitCatalog}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-text-muted">
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
                    <span className="text-[11px] text-text-muted">
                      {t("playground:composer.mcpCatalogStrictLabel", "Strict catalog filter")}
                    </span>
                    <Switch
                      size="small"
                      checked={toolCatalogStrict}
                      onChange={(checked) => setToolCatalogStrict(checked)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-text-muted">
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
              </div>
            )}

            {/* Tool Choice */}
            <div className="px-2">
              <div className="text-xs font-semibold text-text-muted mb-1">
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
            </div>
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
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-red-600 transition hover:bg-red-50 dark:hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40 disabled:text-text-muted disabled:hover:bg-transparent"
        >
          <span>{t("playground:actions.clearConversation", "Clear conversation")}</span>
          <EraserIcon className="h-4 w-4" />
        </button>
      </div>
    ),
    [
      advancedToolsExpanded,
      catalogDraft,
      catalogGroups,
      moduleOptions,
      moduleOptionsLoading,
      handleCatalogSelect,
      handleModuleSelect,
      commitCatalog,
      contextToolsOpen,
      handleClearContext,
      openKnowledgePanel,
      toggleKnowledgePanel,
      handleVoiceChatToggle,
      history.length,
      imageProviderControl,
      isSending,
      setWebSearch,
      setToolChoice,
      t,
      toolCatalogStrict,
      setToolCatalogStrict,
      toolCatalogId,
      toolChoice,
      toolModules,
      setToolCatalogId,
      voiceChatAvailable,
      voiceChatEnabled,
      voiceChat.state,
      voiceChatSettingsFields,
      voiceChatStatusLabel,
      webSearch,
      hasMcp,
      mcpCatalogsLoading,
      mcpHealthState,
      mcpTools,
      mcpToolsLoading,
      isSmallModel
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

  const persistenceModeLabel = React.useMemo(
    () =>
      getPersistenceModeLabel(
        t,
        temporaryChat,
        isConnectionReady,
        serverChatId
      ),
    [isConnectionReady, serverChatId, temporaryChat, t]
  )

  const persistencePillLabel = React.useMemo(() => {
    if (temporaryChat) {
      return t(
        "playground:composer.persistence.ephemeralPill",
        "Not saved"
      )
    }
    if (serverChatId || isConnectionReady) {
      return t(
        "playground:composer.persistence.serverPill",
        "Server"
      )
    }
    return t(
      "playground:composer.persistence.localPill",
      "Local"
    )
  }, [isConnectionReady, serverChatId, temporaryChat, t])

  const persistenceTooltip = React.useMemo(
    () => (
      <div className="flex flex-col gap-0.5 text-xs">
        <span className="font-medium">{persistencePillLabel}</span>
        <span className="text-text-subtle">{persistenceModeLabel}</span>
      </div>
    ),
    [persistenceModeLabel, persistencePillLabel]
  )

  const focusConnectionCard = React.useCallback(() => {
    try {
      const card = document.getElementById("server-connection-card")
      if (card) {
        card.scrollIntoView({ block: "nearest", behavior: "smooth" })
        ;(card as HTMLElement).focus()
        return
      }
    } catch {
      // ignore DOM errors and fall through to hash navigation
    }
    try {
      const base =
        window.location.href.replace(/#.*$/, "") || "/options.html"
      const target = `${base}#/settings/tldw`
      window.location.href = target
    } catch {
      // ignore navigation failures
    }
  }, [])

  const hasContext =
    form.values.image.length > 0 ||
    selectedDocuments.length > 0 ||
    uploadedFiles.length > 0

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
            ? "bg-red-100 text-red-600 dark:bg-red-900/30"
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
      overlayClassName="playground-more-tools">
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
        <Tooltip title={imageAttachmentDisabled || undefined}>
          <span className="block">
            <button
              type="button"
              onClick={handleImageUpload}
              disabled={chatMode === "rag"}
              title={t("playground:actions.upload", "Attach image") as string}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm text-text transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-40 disabled:text-text-muted"
            >
              <span className="flex flex-col items-start">
                <span>{t("playground:actions.attachImage", "Attach image")}</span>
                <span className="text-[10px] text-text-muted">
                  {t(
                    "playground:actions.attachImageHint",
                    "JPG/PNG (Vision)"
                  )}
                </span>
              </span>
              <ImageIcon className="h-4 w-4" />
            </button>
          </span>
        </Tooltip>
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
      chatMode,
      handleDocumentUpload,
      handleImageUpload,
      imageAttachmentDisabled,
      openKnowledgePanel,
      t
    ]
  )

  const attachmentButton = (
    <Popover
      trigger="click"
      placement="topRight"
      content={attachmentMenu}
      overlayClassName="playground-attachment-menu"
    >
      <TldwButton
        variant="outline"
        size="sm"
        shape={isProMode ? "rounded" : "pill"}
        iconOnly={!isProMode}
        ariaLabel={t("playground:actions.attach", "Attach") as string}
        title={t("playground:actions.attach", "Attach") as string}
        data-testid="attachment-button"
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
              {t("playground:actions.attach", "Attach")}
            </span>
          </>
        )}
      </TldwButton>
    </Popover>
  )

  const sendControl = !isSending ? (
    <Dropdown.Button
      size={isProMode ? "middle" : "small"}
      htmlType="submit"
      disabled={isSending || !isConnectionReady}
      title={
        !isConnectionReady
          ? (t(
              "playground:composer.connectToSend",
              "Connect to your tldw server to start chatting."
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
      className={`!justify-end !w-auto ${
        isProMode ? "" : "!h-9 !rounded-full !px-3 !text-xs"
      }`}
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
          },
          {
            key: 2,
            label: (
              <Checkbox
                checked={useOCR}
                onChange={(e) =>
                  setUseOCR(e.target.checked)
                }>
                {t("useOCR")}
              </Checkbox>
            )
          }
        ]
      }}>
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
    </Dropdown.Button>
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

  return (
    <div className="flex w-full flex-col items-center px-4 pb-6">
      <div
        data-checkwidemode={checkWideMode}
        data-ui-mode={uiMode}
        className="relative z-10 flex w-full max-w-[52rem] flex-col items-center justify-center gap-2 text-base data-[checkwidemode='true']:max-w-none">
        <div className="relative flex w-full flex-row justify-center">
          <div
            data-istemporary-chat={temporaryChat}
            className={`relative w-full rounded-3xl border border-border/80 bg-surface/95 p-3 text-text shadow-card backdrop-blur-lg transition-all duration-200 data-[istemporary-chat='true']:border-t-4 data-[istemporary-chat='true']:border-t-purple-500 data-[istemporary-chat='true']:border-dashed data-[istemporary-chat='true']:opacity-90 ${
              !isConnectionReady ? "opacity-80" : ""
            }`}>
            {/* Attachments summary (collapsed context management) */}
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
                        if (!selectedModel || selectedModel.length === 0) {
                          form.setFieldError("message", t("formError.noModel"))
                          return
                        }
                      } else if (
                        !compareSelectedModels ||
                        compareSelectedModels.length === 0
                      ) {
                        form.setFieldError(
                          "message",
                          t(
                            "playground:composer.validationCompareSelectModelsInline",
                            "Select at least one model for Compare mode."
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
                        : undefined
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
                    onChange={onFileInputChange}
                  />

                  <div
                    className={`w-full flex flex-col px-2 ${
                      !isConnectionReady
                        ? "rounded-md border border-dashed border-border bg-surface2"
                        : ""
                    }`}>
                    <div
                      className={contextToolsOpen ? "mb-2" : "hidden"}
                      aria-hidden={!contextToolsOpen}
                    >
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="flex flex-col gap-4">
                          <div>
                            <div className="mb-2 text-xs font-semibold text-text">
                              {t(
                                "playground:composer.knowledgeSearch",
                                "Search & Context"
                              )}
                            </div>
                            <KnowledgePanel
                              onInsert={(text) => {
                                const current = form.values.message || ""
                                const next = current ? `${current}\n\n${text}` : text
                                setMessageValue(next, { collapseLarge: true })
                                textAreaFocus()
                              }}
                              onAsk={(text, options) => {
                                const trimmed = text.trim()
                                if (!trimmed) return
                                form.setFieldValue("message", trimmed)
                                queueMicrotask(() =>
                                  submitForm({ ignorePinnedResults: options?.ignorePinnedResults })
                                )
                              }}
                              isConnected={isConnectionReady}
                              open={contextToolsOpen}
                              onOpenChange={(nextOpen) => setContextToolsOpen(nextOpen)}
                              openTab={knowledgePanelTab}
                              openTabRequestId={knowledgePanelTabRequestId}
                              autoFocus
                              showToggle={false}
                              variant="embedded"
                              currentMessage={form.values.message}
                              showAttachedContext
                              attachedImage={form.values.image}
                              attachedTabs={selectedDocuments}
                              availableTabs={availableTabs}
                              attachedFiles={uploadedFiles}
                              onRemoveImage={() => form.setFieldValue("image", "")}
                              onRemoveTab={removeDocument}
                              onAddTab={addDocument}
                              onClearTabs={clearSelectedDocuments}
                              onRefreshTabs={reloadTabs}
                              onAddFile={() => fileInputRef.current?.click()}
                              onRemoveFile={removeUploadedFile}
                              onClearFiles={clearUploadedFiles}
                              fileRetrievalEnabled={fileRetrievalEnabled}
                              onFileRetrievalChange={setFileRetrievalEnabled}
                            />
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
                      <div className="relative rounded-2xl border border-border/70 bg-surface/80 px-1 py-1.5 transition focus-within:border-focus/60 focus-within:ring-2 focus-within:ring-focus/30">
                        <SlashCommandMenu
                          open={showSlashMenu}
                          commands={filteredSlashCommands}
                          activeIndex={slashActiveIndex}
                          onActiveIndexChange={setSlashActiveIndex}
                          onSelect={handleSlashCommandSelect}
                          emptyLabel={t(
                            "common:commandPalette.noResults",
                            "No results found"
                          )}
                          className="absolute bottom-full left-3 right-3 mb-2"
                        />
                        <textarea
                          id="textarea-message"
                          data-testid="chat-input"
                          onCompositionStart={() => {
                            if (!isFirefoxTarget) {
                              setTyping(true)
                            }
                          }}
                          onCompositionEnd={() => {
                            if (!isFirefoxTarget) {
                              setTyping(false)
                            }
                          }}
                          onMouseDown={() => {
                            if (isMessageCollapsed) {
                              pointerDownRef.current = true
                              selectionFromPointerRef.current = true
                            }
                          }}
                          onMouseUp={() => {
                            pointerDownRef.current = false
                            if (selectionFromPointerRef.current) {
                              requestAnimationFrame(() => {
                                selectionFromPointerRef.current = false
                              })
                            }
                          }}
                          onKeyDown={(e) => {
                            if (handleCollapsedKeyDown(e)) return
                            handleKeyDown(e)
                          }}
                          onFocus={() => {
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
                          }}
                          ref={textareaRef}
                          className={`w-full resize-none bg-transparent text-base leading-6 text-text placeholder:text-text-muted/80 focus-within:outline-none focus:ring-0 focus-visible:ring-0 ring-0 border-0 ${
                            !isConnectionReady
                              ? "cursor-not-allowed text-text-muted placeholder:text-text-subtle"
                              : ""
                          } ${isProMode ? "px-3 py-2.5" : "px-3 py-2"}`}
                          onPaste={handlePaste}
                          aria-expanded={!isMessageCollapsed}
                          rows={1}
                          style={{ minHeight: isProMode ? "60px" : "44px" }}
                          tabIndex={0}
                          placeholder={
                            isConnectionReady
                              ? t("playground:composer.placeholderWithSlash", "Type a message... (/ for commands)")
                              : t(
                                  "playground:composer.connectionPlaceholder",
                                  "Connect to tldw to start chatting."
                                )
                          }
                          {...form.getInputProps("message")}
                          value={messageDisplayValue}
                          onChange={(e) => {
                            if (isMessageCollapsed) return
                            form.getInputProps("message").onChange(e)
                            if (tabMentionsEnabled && textareaRef.current) {
                              handleTextChange(
                                e.target.value,
                                textareaRef.current.selectionStart || 0
                              )
                            }
                          }}
                          onSelect={() => {
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
                                getCollapsedDisplayMeta(
                                  message,
                                  collapsedRange
                                )
                              const selectionStart =
                                textarea.selectionStart ?? meta.labelStart
                              const selectionEnd =
                                textarea.selectionEnd ?? selectionStart
                              const displayStart = Math.min(
                                selectionStart,
                                selectionEnd
                              )
                              const displayEnd = Math.max(
                                selectionStart,
                                selectionEnd
                              )
                              const hasSelection = displayStart !== displayEnd
                              const selectionTouchesLabel =
                                displayStart < meta.labelEnd &&
                                displayEnd > meta.labelStart
                              const fromPointer = selectionFromPointerRef.current
                              selectionFromPointerRef.current = false
                              if (hasSelection) {
                                pendingCaretRef.current = null
                                return
                              }
                              const caretInsideLabel =
                                displayStart > meta.labelStart &&
                                displayStart < meta.labelEnd
                              if (
                                selectionTouchesLabel &&
                                fromPointer &&
                                caretInsideLabel
                              ) {
                                pendingCaretRef.current = meta.rangeEnd
                                expandLargeMessage({ force: true })
                                return
                              }
                              const prefer =
                                caretInsideLabel &&
                                (pendingCaretRef.current ?? meta.rangeEnd) <=
                                  meta.rangeStart
                                  ? "before"
                                  : "after"
                              const caret = getMessageCaretFromDisplay(
                                displayStart,
                                meta,
                                {
                                  prefer: caretInsideLabel ? prefer : undefined
                                }
                              )
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
                          }}
                        />

                        <MentionsDropdown
                          show={showMentions}
                          tabs={filteredTabs}
                          mentionPosition={mentionPosition}
                          onSelectTab={(tab) =>
                            insertMention(tab, form.values.message, (value) =>
                              form.setFieldValue("message", value)
                            )
                          }
                          onClose={closeMentions}
                          textareaRef={textareaRef}
                          refetchTabs={async () => {
                            await reloadTabs()
                          }}
                          onMentionsOpen={handleMentionsOpen}
                        />
                        {/* Draft saved indicator */}
                        {draftSaved && (
                          <span
                            className="absolute bottom-1 right-2 text-label text-text-subtle transition-opacity pointer-events-none"
                            role="status"
                            aria-live="polite"
                          >
                            {t("sidepanel:composer.draftSaved", "Draft saved")}
                          </span>
                        )}
                      </div>
                    </div>
                    {/* Inline error message with shake animation */}
                    {form.errors.message && (
                      <div
                        role="alert"
                        aria-live="assertive"
                        aria-atomic="true"
                        className="flex items-center justify-between gap-2 px-2 py-1 text-xs text-red-600 dark:text-red-400 animate-shake"
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
                          className="flex-shrink-0 text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
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
                    {isProMode ? (
                      <div className="mt-2 flex flex-col gap-1">
                        <div className="mt-1 flex flex-col gap-2">
                          <div className="flex flex-wrap items-start gap-3">
                            <div className="flex flex-col gap-0.5 text-xs text-text">
                              <Tooltip title={persistenceTooltip}>
                                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                                    <Switch
                                      size="small"
                                      checked={!temporaryChat}
                                      disabled={privateChatLocked || isFireFoxPrivateMode}
                                      onChange={(checked) =>
                                        handleToggleTemporaryChat(!checked)
                                      }
                                    aria-label={
                                      temporaryChat
                                        ? (t(
                                            "playground:actions.temporaryOn",
                                            "Don't save chat"
                                          ) as string)
                                        : (t(
                                            "playground:actions.temporaryOff",
                                            "Save chat to history"
                                          ) as string)
                                    }
                                  />
                                  <span>
                                    {temporaryChat
                                      ? t(
                                          "playground:actions.temporaryOn",
                                          "Don't save chat"
                                        )
                                      : t(
                                          "playground:actions.temporaryOff",
                                          "Save chat to history"
                                        )}
                                  </span>
                                </div>
                              </Tooltip>
                              {!temporaryChat && !isConnectionReady && (
                                <button
                                  type="button"
                                  onClick={focusConnectionCard}
                                  title={
                                    t(
                                      "playground:composer.persistence.connectToSave",
                                      "Connect your server to sync chats."
                                    ) as string
                                  }
                                  className="mt-1 inline-flex w-fit items-center gap-1 text-[11px] font-medium text-primary hover:text-primaryStrong">
                                  {t(
                                    "playground:composer.persistence.connectToSave",
                                    "Connect your server to sync chats."
                                  )}
                                </button>
                              )}
                              {!temporaryChat && serverChatId && showServerPersistenceHint && (
                                <p className="mt-1 max-w-md text-[11px] text-text-muted">
                                  <span className="font-semibold">
                                    {t(
                                      "playground:composer.persistence.serverInlineTitle",
                                      "Saved locally + on your server"
                                    )}
                                    {": "}
                                  </span>
                                  {t(
                                    "playground:composer.persistence.serverInlineBody",
                                    "This chat is stored both in this browser and on your tldw server, so you can reopen it from server history, keep a long-term record, and analyze it alongside other conversations."
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => setShowServerPersistenceHint(false)}
                                    title={t("common:dismiss", "Dismiss") as string}
                                    className="ml-1 text-[11px] font-medium text-primary hover:text-primaryStrong"
                                  >
                                    {t("common:dismiss", "Dismiss")}
                                  </button>
                                </p>
                              )}
                            </div>
                          </div>
                          {/* Enhanced Playground Features Row */}
                          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 pt-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <ParameterPresets compact />
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <SystemPromptTemplatesButton
                                onSelect={(template: PromptTemplate) => {
                                  setSystemPrompt(template.content)
                                  setSelectedSystemPrompt(undefined)
                                }}
                              />
                              {messages.length > 0 && (
                                <SessionCostEstimation
                                  modelId={selectedModel}
                                  provider={resolvedProviderKey}
                                  messages={messages}
                                />
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                              <button
                                type="button"
                                onClick={() => toggleKnowledgePanel("search")}
                                title={
                                  contextToolsOpen
                                    ? (t(
                                        "playground:composer.contextKnowledgeClose",
                                        "Close Search & Context"
                                      ) as string)
                                    : (t(
                                        "playground:composer.contextKnowledge",
                                        "Search & Context"
                                      ) as string)
                                }
                                aria-pressed={contextToolsOpen}
                                aria-expanded={contextToolsOpen}
                                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition ${
                                  contextToolsOpen
                                    ? "border-accent bg-surface2 text-accent hover:bg-surface"
                                    : "border-border text-text-muted hover:bg-surface2 hover:text-text"
                                }`}
                              >
                                <Search className="h-3 w-3" />
                                <span>
                                  {contextToolsOpen
                                    ? t(
                                        "playground:composer.contextKnowledgeClose",
                                        "Close Search & Context"
                                      )
                                    : t(
                                        "playground:composer.contextKnowledge",
                                        "Search & Context"
                                      )}
                                </span>
                              </button>
                              {selectedDocuments.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const chips =
                                      document.querySelector<HTMLElement>(
                                        "[data-playground-tabs='true']"
                                      )
                                    if (chips) {
                                      chips.focus()
                                      chips.scrollIntoView({ block: "nearest" })
                                    }
                                  }}
                                  title={
                                    t(
                                      "playground:composer.contextTabsHint",
                                      "Review or remove referenced tabs, or add more from your open browser tabs."
                                    ) as string
                                  }
                                  className="inline-flex items-center gap-1 rounded-full border border-transparent px-2 py-0.5 hover:border-border hover:bg-surface2">
                                  <FileText className="h-3 w-3 text-text-subtle" />
                                  <span>
                                    {t("playground:composer.contextTabs", {
                                      defaultValue: "{{count}} tabs",
                                      count: selectedDocuments.length
                                    } as any) as string}
                                  </span>
                                </button>
                              )}
                              {uploadedFiles.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    const files =
                                      document.querySelector<HTMLElement>(
                                        "[data-playground-uploads='true']"
                                      )
                                    if (files) {
                                      files.focus()
                                      files.scrollIntoView({ block: "nearest" })
                                    }
                                  }}
                                  title={
                                    t(
                                      "playground:composer.contextFilesHint",
                                      "Review attached files, remove them, or add more."
                                    ) as string
                                  }
                                  className="inline-flex items-center gap-1 rounded-full border border-transparent px-2 py-0.5 hover:border-border hover:bg-surface2">
                                  <FileIcon className="h-3 w-3 text-text-subtle" />
                                  <span>
                                    {t("playground:composer.contextFiles", {
                                      defaultValue: "{{count}} files",
                                      count: uploadedFiles.length
                                    } as any) as string}
                                  </span>
                                </button>
                              )}
                            </div>
                            <div className="flex items-center justify-end gap-3 flex-wrap">
                              <CharacterSelect
                                className="min-w-0 min-h-0 rounded-full border border-border px-2 py-1 text-text-muted hover:bg-surface2 hover:text-text"
                                iconClassName="h-4 w-4"
                              />
                              <Tooltip
                                title={
                                  t(
                                    "option:promptInsert.useInChat",
                                    "Insert prompt"
                                  ) as string
                                }>
                                <button
                                  type="button"
                                  onClick={() => setPromptInsertOpen(true)}
                                  aria-label={
                                    t(
                                      "option:promptInsert.useInChat",
                                      "Insert prompt"
                                    ) as string
                                  }
                                  className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-1 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
                                >
                                  <BookPlus className="h-4 w-4" />
                                  <span className="hidden text-xs font-medium sm:inline">
                                    {t(
                                      "option:promptInsert.useInChat",
                                      "Insert prompt"
                                    )}
                                  </span>
                                </button>
                              </Tooltip>
                              {(browserSupportsSpeechRecognition || hasServerAudio) && (
                                <Tooltip
                                  title={
                                    !speechAvailable
                                      ? t(
                                          "playground:actions.speechUnavailableBody",
                                          "Connect to a tldw server that exposes the audio transcriptions API to use dictation."
                                        )
                                      : speechUsesServer
                                        ? t(
                                            "playground:tooltip.speechToTextServer",
                                            "Dictation via your tldw server"
                                          ) +
                                          " " +
                                          t(
                                            "playground:tooltip.speechToTextDetails",
                                            "Uses {{model}} · {{task}} · {{format}}. Configure in Settings → General → Speech-to-Text.",
                                            {
                                              model: sttModel || "whisper-1",
                                              task:
                                                sttTask === "translate"
                                                  ? "translate"
                                                  : "transcribe",
                                              format: (sttResponseFormat || "json").toUpperCase()
                                            } as any
                                          )
                                        : t(
                                            "playground:tooltip.speechToTextBrowser",
                                            "Dictation via browser speech recognition"
                                          )
                                  }
                                >
                                  <button
                                    type="button"
                                    onClick={speechUsesServer ? handleServerDictationToggle : handleSpeechToggle}
                                    disabled={!speechAvailable || voiceChatEnabled}
                                    className={`inline-flex items-center justify-center rounded-full border text-xs transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50 ${
                                      speechAvailable &&
                                      ((speechUsesServer && isServerDictating) ||
                                        (!speechUsesServer && isListening))
                                        ? "border-primary text-primaryStrong"
                                        : "border-border text-text-muted"
                                    } ${isProMode ? "px-2 py-1" : "h-9 w-9 p-0"}`}
                                    aria-label={
                                      !speechAvailable
                                        ? (t(
                                            "playground:actions.speechUnavailableTitle",
                                            "Dictation unavailable"
                                          ) as string)
                                        : speechUsesServer
                                          ? (isServerDictating
                                              ? (t("playground:actions.speechStop", "Stop dictation") as string)
                                              : (t("playground:actions.speechStart", "Start dictation") as string))
                                          : (isListening
                                              ? (t("playground:actions.speechStop", "Stop dictation") as string)
                                              : (t("playground:actions.speechStart", "Start dictation") as string))
                                    }
                                  >
                                    <MicIcon className="h-4 w-4" />
                                  </button>
                                </Tooltip>
                              )}
                              {modelUsageBadge}
                              <Tooltip
                                title={
                                  t(
                                    "common:currentChatModelSettings"
                                  ) as string
                                }>
                                <button
                                  type="button"
                                  onClick={() => setOpenModelSettings(true)}
                                  aria-label={
                                    t(
                                      "common:currentChatModelSettings"
                                    ) as string
                                  }
                                  className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs text-text transition hover:bg-surface2">
                                  <Gauge
                                    className="h-4 w-4"
                                    aria-hidden="true"
                                  />
                                  <span className="flex flex-col items-start text-left">
                                    <span className="font-medium">
                                      {t("playground:composer.chatSettings", "Chat Settings")}
                                    </span>
                                    <span className="text-[11px] text-text-muted">
                                      {modelSummaryLabel} • {promptSummaryLabel}
                                    </span>
                                  </span>
                                </button>
                              </Tooltip>
                              {voiceChatButton}
                              {attachmentButton}
                              {toolsButton}
                              {sendControl}
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-nowrap">
                          <Tooltip title={persistenceTooltip}>
                            <div className="flex items-center gap-1">
                                <Switch
                                  size="small"
                                  checked={!temporaryChat}
                                  disabled={privateChatLocked || isFireFoxPrivateMode}
                                  onChange={(checked) =>
                                    handleToggleTemporaryChat(!checked)
                                  }
                                aria-label={
                                  temporaryChat
                                    ? (t(
                                        "playground:actions.temporaryOn",
                                        "Don't save chat"
                                      ) as string)
                                    : (t(
                                        "playground:actions.temporaryOff",
                                        "Save chat to history"
                                      ) as string)
                                }
                              />
                              <span className="text-xs text-text whitespace-nowrap">
                                {temporaryChat
                                  ? t(
                                      "playground:actions.temporaryOn",
                                      "Don't save chat"
                                    )
                                  : t(
                                      "playground:actions.temporaryOff",
                                      "Save chat to history"
                                    )}
                              </span>
                            </div>
                          </Tooltip>
                          <button
                            type="button"
                            onClick={() => toggleKnowledgePanel("search")}
                            title={
                              contextToolsOpen
                                ? (t(
                                    "playground:composer.contextKnowledgeClose",
                                    "Close Search & Context"
                                  ) as string)
                                : (t(
                                    "playground:composer.contextKnowledge",
                                    "Search & Context"
                                  ) as string)
                            }
                            aria-pressed={contextToolsOpen}
                            aria-expanded={contextToolsOpen}
                            className={`inline-flex min-w-0 max-w-[140px] items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-medium transition ${
                              contextToolsOpen
                                ? "border-accent bg-surface2 text-accent hover:bg-surface"
                                : "border-border text-text-muted hover:bg-surface2 hover:text-text"
                            }`}
                          >
                            <Search className="h-3 w-3" />
                            <span className="truncate">
                              {contextToolsOpen
                                ? t(
                                    "playground:composer.contextKnowledgeClose",
                                    "Close Search & Context"
                                  )
                                : t(
                                    "playground:composer.contextKnowledge",
                                    "Search & Context"
                                  )}
                            </span>
                          </button>
                        </div>
                        <div className="flex items-center gap-2 flex-nowrap">
                          <CharacterSelect
                            showLabel={false}
                            className="min-w-0 min-h-0 h-9 w-9 rounded-full border border-border text-text-muted hover:bg-surface2 hover:text-text"
                            iconClassName="h-4 w-4"
                          />
                          <Tooltip
                            title={
                              t(
                                "option:promptInsert.useInChat",
                                "Insert prompt"
                              ) as string
                            }>
                            <button
                              type="button"
                              onClick={() => setPromptInsertOpen(true)}
                              aria-label={
                                t(
                                  "option:promptInsert.useInChat",
                                  "Insert prompt"
                                ) as string
                              }
                              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border text-text-muted transition hover:bg-surface2 hover:text-text"
                            >
                              <BookPlus className="h-4 w-4" />
                            </button>
                          </Tooltip>
                          {(browserSupportsSpeechRecognition || hasServerAudio) && (
                            <Tooltip
                              title={
                                !speechAvailable
                                  ? t(
                                      "playground:actions.speechUnavailableBody",
                                      "Connect to a tldw server that exposes the audio transcriptions API to use dictation."
                                    )
                                  : speechUsesServer
                                    ? t(
                                        "playground:tooltip.speechToTextServer",
                                        "Dictation via your tldw server"
                                      )
                                    : t(
                                        "playground:tooltip.speechToTextBrowser",
                                        "Dictation via browser speech recognition"
                                      )
                              }>
                              <button
                                type="button"
                                onClick={speechUsesServer ? handleServerDictationToggle : handleSpeechToggle}
                                disabled={!speechAvailable || voiceChatEnabled}
                                className={`inline-flex items-center justify-center rounded-full border px-2 py-1 text-xs transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50 ${
                                  speechAvailable &&
                                  ((speechUsesServer && isServerDictating) ||
                                    (!speechUsesServer && isListening))
                                    ? "border-primary text-primaryStrong"
                                    : "border-border text-text-muted"
                                }`}
                                aria-label={
                                  !speechAvailable
                                    ? (t(
                                        "playground:actions.speechUnavailableTitle",
                                        "Dictation unavailable"
                                      ) as string)
                                    : speechUsesServer
                                      ? (isServerDictating
                                          ? (t("playground:actions.speechStop", "Stop dictation") as string)
                                          : (t("playground:actions.speechStart", "Start dictation") as string))
                                      : (isListening
                                          ? (t("playground:actions.speechStop", "Stop dictation") as string)
                                          : (t("playground:actions.speechStart", "Start dictation") as string))
                                }>
                                <MicIcon className="h-4 w-4" />
                              </button>
                            </Tooltip>
                          )}
                          {modelUsageBadge}
                          <Tooltip
                            title={
                              t(
                                "common:currentChatModelSettings"
                              ) as string
                            }>
                            <TldwButton
                              variant="outline"
                              shape="pill"
                              iconOnly
                              onClick={() => setOpenModelSettings(true)}
                              ariaLabel={
                                t(
                                  "common:currentChatModelSettings"
                                ) as string
                              }
                              className="text-text-muted">
                              <Gauge className="h-4 w-4" aria-hidden="true" />
                              <span className="sr-only">
                                {t(
                                  "playground:composer.chatSettings",
                                  "Chat Settings"
                                )}
                              </span>
                            </TldwButton>
                          </Tooltip>
                          {voiceChatButton}
                          {attachmentButton}
                          {toolsButton}
                          {sendControl}
                        </div>
                      </div>
                    )}
                    {showConnectBanner && !isConnectionReady && (
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500 dark:bg-[#2a2310] dark:text-amber-100">
                        <p className="max-w-xs text-left">
                          {t(
                            "playground:composer.connectNotice",
                            "Connect to your tldw server in Settings to send messages."
                          )}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to="/settings/tldw"
                            className="text-xs font-medium text-amber-900 underline hover:text-amber-700 dark:text-amber-100 dark:hover:text-amber-300"
                          >
                            {t("settings:tldw.setupLink", "Set up server")}
                          </Link>
                          <Link
                            to="/settings/health"
                            className="text-xs font-medium text-amber-900 underline hover:text-amber-700 dark:text-amber-100 dark:hover:text-amber-300"
                          >
                            {t(
                              "settings:healthSummary.diagnostics",
                              "Health & diagnostics"
                            )}
                          </Link>
                          <button
                            type="button"
                            onClick={() => setShowConnectBanner(false)}
                            className="inline-flex items-center rounded-full p-1 text-amber-700 hover:bg-amber-100 dark:text-amber-200 dark:hover:bg-[#3a2b10]"
                            aria-label={t("common:close", "Dismiss")}
                            title={t("common:close", "Dismiss") as string}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    )}
                    {queuedMessages.length > 0 && showQueuedBanner && (
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md border border-green-300 bg-green-50 px-3 py-2 text-xs text-green-900 dark:border-green-500 dark:bg-[#102a10] dark:text-green-100">
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
                            className={`rounded-md border border-green-300 bg-white px-2 py-1 text-xs font-medium text-green-900 hover:bg-green-100 dark:bg-[#163816] dark:text-green-50 dark:hover:bg-[#194419] ${
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
                            className="text-xs font-medium text-green-900 underline hover:text-green-700 dark:text-green-100 dark:hover:text-green-300"
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
                            className="text-xs font-medium text-green-900 underline hover:text-green-700 dark:text-green-100 dark:hover:text-green-300"
                          >
                            {t(
                              "settings:healthSummary.diagnostics",
                              "Health & diagnostics"
                            )}
                          </Link>
                          <button
                            type="button"
                            onClick={() => setShowQueuedBanner(false)}
                            className="inline-flex items-center rounded-full p-1 text-green-700 hover:bg-green-100 dark:text-green-200 dark:hover:bg-[#163816]"
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
      <PromptInsertModal
        open={promptInsertOpen}
        onClose={() => setPromptInsertOpen(false)}
        onInsertPrompt={handlePromptInsert}
      />
      <Modal
        title={t("option:promptInsert.confirmTitle", {
          defaultValue: "Use prompt in chat?"
        })}
        open={Boolean(promptInsertChoice)}
        onCancel={() => setPromptInsertChoice(null)}
        footer={null}
        centered
        destroyOnHidden
      >
        <div className="space-y-3">
          <p className="text-sm text-text">
            {t("option:promptInsert.choiceDescription", {
              defaultValue:
                "This prompt includes both a system prompt and a user prompt. Choose how you want to use it."
            })}
          </p>
          {promptInsertChoice?.title && (
            <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium">
              {promptInsertChoice.title}
            </div>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button onClick={() => setPromptInsertChoice(null)}>
              {t("common:cancel", "Cancel")}
            </Button>
            <Button
              onClick={() => {
                if (promptInsertChoice?.userPrompt) {
                  insertMessageAtCaret(promptInsertChoice.userPrompt)
                }
                setPromptInsertChoice(null)
              }}
            >
              {t("option:promptInsert.insertUser", {
                defaultValue: "Insert user prompt"
              })}
            </Button>
            <Button
              type="primary"
              onClick={() => {
                if (promptInsertChoice?.systemPrompt) {
                  applySystemPrompt(promptInsertChoice.systemPrompt)
                }
                setPromptInsertChoice(null)
              }}
            >
              {t("option:promptInsert.applySystem", {
                defaultValue: "Apply system prompt"
              })}
            </Button>
          </div>
        </div>
      </Modal>
      <CurrentChatModelSettings
        open={openModelSettings}
        setOpen={setOpenModelSettings}
        isOCREnabled={useOCR}
      />
      <ActorPopout open={openActorSettings} setOpen={setOpenActorSettings} />
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
      {voiceChatEnabled && voiceChat.state !== "idle" && (
        <VoiceChatIndicator
          state={voiceChat.state}
          statusLabel={voiceChatStatusLabel}
          onStop={handleVoiceChatToggle}
        />
      )}
      <VoiceModeSelector
        open={voiceModeSelectorOpen}
        onClose={() => setVoiceModeSelectorOpen(false)}
        onSelectDictation={() => {
          if (speechUsesServer) {
            handleServerDictationToggle()
          } else {
            handleSpeechToggle()
          }
        }}
        onSelectConversation={handleVoiceChatToggle}
        dictationAvailable={speechAvailable}
        conversationAvailable={voiceChatAvailable}
      />
      <PlaygroundTour run={runTour} onComplete={completeTour} />
    </div>
  )
}
