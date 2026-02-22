import React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useStoreMessageOption } from "~/store/option"
import { generateID } from "@/db/dexie/helpers"
import { useTranslation } from "react-i18next"
import { usePageAssist } from "@/context"
import { useWebUI } from "@/store/webui"
import { useStorage } from "@plasmohq/storage/hook"
import { useStoreChatModelSettings } from "@/store/model"
import { UploadedFile } from "@/db/dexie/types"
import { formatFileSize } from "@/utils/format"
import { useAntdNotification } from "./useAntdNotification"
import { useChatBaseState } from "@/hooks/chat/useChatBaseState"
import { useSelectServerChat } from "@/hooks/chat/useSelectServerChat"
import { useServerChatHistoryId } from "@/hooks/chat/useServerChatHistoryId"
import { useServerChatLoader } from "@/hooks/chat/useServerChatLoader"
import { useClearChat } from "@/hooks/chat/useClearChat"
import { useCompareMode } from "@/hooks/chat/useCompareMode"
import { useChatActions } from "@/hooks/chat/useChatActions"
import type { Character } from "@/types/character"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { useSetting } from "@/hooks/useSetting"
import { CONTEXT_FILE_SIZE_MB_SETTING } from "@/services/settings/ui-settings"
import {
  DEFAULT_RAG_SETTINGS,
  toRagAdvancedOptions,
  type RagSettings
} from "@/services/rag/unified-rag"
import {
  DEFAULT_MESSAGE_STEERING_PROMPTS,
  MESSAGE_STEERING_PROMPTS_STORAGE_KEY
} from "@/utils/message-steering"
import type { MessageSteeringPromptTemplates } from "@/types/message-steering"

export const useMessageOption = (
  opts: { forceCompareEnabled?: boolean } = {}
) => {
  const e2eDebugEnabled =
    typeof window !== "undefined" && (window as any).__tldw_e2e_debug
  const e2eDebugCounts = React.useRef({
    syncSystem: 0,
    syncQuick: 0,
    storeSystem: 0,
    storeQuick: 0
  })
  const logE2EDebug = (
    key: keyof typeof e2eDebugCounts.current,
    payload: Record<string, unknown>
  ) => {
    if (!e2eDebugEnabled) return
    const counts = e2eDebugCounts.current
    counts[key] += 1
    if (counts[key] <= 10 || counts[key] % 50 === 0) {
      console.log(`[E2E_DEBUG] ${key}`, {
        count: counts[key],
        ...payload
      })
    }
  }
  // Controllers come from Context (for aborting streaming requests)
  const {
    controller: abortController,
    setController: setAbortController
  } = usePageAssist()

  const {
    messages,
    setMessages,
    history,
    setHistory,
    streaming,
    setStreaming,
    isFirstMessage,
    setIsFirstMessage,
    historyId,
    setHistoryId,
    isLoading,
    setIsLoading,
    isProcessing,
    setIsProcessing,
    chatMode,
    setChatMode,
    isEmbedding,
    setIsEmbedding,
    selectedQuickPrompt,
    setSelectedQuickPrompt,
    selectedSystemPrompt,
    setSelectedSystemPrompt,
    useOCR,
    setUseOCR
  } = useChatBaseState(useStoreMessageOption)

  const {
    webSearch,
    setWebSearch,
    toolChoice,
    setToolChoice,
    isSearchingInternet,
    setIsSearchingInternet,
    queuedMessages: storeQueuedMessages,
    addQueuedMessage: storeAddQueuedMessage,
    clearQueuedMessages: storeClearQueuedMessages,
    selectedKnowledge,
    setSelectedKnowledge,
    temporaryChat,
    setTemporaryChat,
    documentContext,
    setDocumentContext,
    uploadedFiles,
    setUploadedFiles,
    contextFiles,
    setContextFiles,
    actionInfo,
    setActionInfo,
    setFileRetrievalEnabled,
    fileRetrievalEnabled,
    ragMediaIds,
    setRagMediaIds,
    ragSearchMode,
    setRagSearchMode,
    ragTopK,
    setRagTopK,
    ragEnableGeneration,
    setRagEnableGeneration,
    ragEnableCitations,
    setRagEnableCitations,
    ragSources,
    setRagSources,
    ragAdvancedOptions,
    setRagAdvancedOptions,
    ragPinnedResults,
    setRagPinnedResults,
    serverChatId,
    setServerChatId,
    serverChatTitle,
    setServerChatTitle,
    serverChatCharacterId,
    setServerChatCharacterId,
    serverChatMetaLoaded,
    setServerChatMetaLoaded,
    serverChatState,
    setServerChatState,
    serverChatVersion,
    setServerChatVersion,
    serverChatTopic,
    setServerChatTopic,
    serverChatClusterId,
    setServerChatClusterId,
    serverChatSource,
    setServerChatSource,
    serverChatExternalRef,
    setServerChatExternalRef,
    messageSteeringMode,
    setMessageSteeringMode,
    messageSteeringForceNarrate,
    setMessageSteeringForceNarrate,
    clearMessageSteering,
    replyTarget,
    clearReplyTarget
  } = useStoreMessageOption()

  const {
    compareMode,
    setCompareMode,
    compareFeatureEnabled,
    setCompareFeatureEnabled,
    compareSelectedModels,
    setCompareSelectedModels,
    compareSelectionByCluster,
    setCompareSelectionForCluster,
    compareActiveModelsByCluster,
    setCompareActiveModelsForCluster,
    compareParentByHistory,
    setCompareParentForHistory,
    compareCanonicalByCluster,
    setCompareCanonicalForCluster,
    compareContinuationModeByCluster,
    setCompareContinuationModeForCluster,
    compareSplitChats,
    setCompareSplitChat,
    compareMaxModels,
    setCompareMaxModels,
    compareModeActive,
    markCompareHistoryCreated,
    compareAutoDisabledFlag,
    setCompareAutoDisabledFlag
  } = useCompareMode({ historyId, forceEnabled: opts.forceCompareEnabled })

  const currentChatModelSettings = useStoreChatModelSettings()
  const selectedModelFromStore = useStoreMessageOption((s) => s.selectedModel)
  const setSelectedModelInStore = useStoreMessageOption((s) => s.setSelectedModel)
  const [storedSelectedModel, setStoredSelectedModel, selectedModelStorageMeta] =
    useStorage<string | null>("selectedModel", null)
  const normalizeSelectedModel = React.useCallback((value: string | null | undefined) => {
    if (typeof value !== "string") return null
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
  }, [])
  const selectedModel = React.useMemo(
    () =>
      normalizeSelectedModel(selectedModelFromStore) ??
      normalizeSelectedModel(storedSelectedModel),
    [normalizeSelectedModel, selectedModelFromStore, storedSelectedModel]
  )
  const setSelectedModel = React.useCallback(
    (
      nextOrUpdater: string | null | ((current: string | null) => string | null)
    ) => {
      const resolved =
        typeof nextOrUpdater === "function"
          ? nextOrUpdater(selectedModel)
          : nextOrUpdater
      const normalized = normalizeSelectedModel(resolved)
      setSelectedModelInStore(normalized)
      void setStoredSelectedModel(normalized)
    },
    [
      normalizeSelectedModel,
      selectedModel,
      setSelectedModelInStore,
      setStoredSelectedModel
    ]
  )
  const [selectedCharacter, setSelectedCharacter] =
    useSelectedCharacter<Character | null>(null)
  const [defaultInternetSearchOn] = useStorage("defaultInternetSearchOn", false)
  const [speechToTextLanguage, setSpeechToTextLanguage] = useStorage(
    "speechToTextLanguage",
    "en-US"
  )
  const [storedRagSettings] = useStorage<RagSettings>(
    "ragSearchSettingsV2",
    DEFAULT_RAG_SETTINGS
  )
  const [messageSteeringPrompts] =
    useStorage<MessageSteeringPromptTemplates>(
      MESSAGE_STEERING_PROMPTS_STORAGE_KEY,
      DEFAULT_MESSAGE_STEERING_PROMPTS
    )

  const { ttsEnabled } = useWebUI()

  const { t } = useTranslation("option")
  const [contextFileMaxSizeMb] = useSetting(CONTEXT_FILE_SIZE_MB_SETTING)
  const maxContextFileSizeBytes = React.useMemo(
    () => contextFileMaxSizeMb * 1024 * 1024,
    [contextFileMaxSizeMb]
  )
  const maxContextFileSizeLabel = React.useMemo(
    () => formatFileSize(maxContextFileSizeBytes),
    [maxContextFileSizeBytes]
  )
  const queryClient = useQueryClient()
  const invalidateServerChatHistory = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
  }, [queryClient])
  const notification = useAntdNotification()

  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const selectServerChat = useSelectServerChat()
  const { ensureServerChatHistoryId } = useServerChatHistoryId({
    serverChatId,
    historyId,
    setHistoryId,
    temporaryChat,
    t
  })

  useServerChatLoader({ ensureServerChatHistoryId, notification, t })

  const resetServerChatState = React.useCallback(() => {
    setServerChatState("in-progress")
    setServerChatVersion(null)
    setServerChatTitle(null)
    setServerChatCharacterId(null)
    setServerChatMetaLoaded(false)
    setServerChatTopic(null)
    setServerChatClusterId(null)
    setServerChatSource(null)
    setServerChatExternalRef(null)
  }, [
    setServerChatCharacterId,
    setServerChatClusterId,
    setServerChatExternalRef,
    setServerChatMetaLoaded,
    setServerChatSource,
    setServerChatState,
    setServerChatTitle,
    setServerChatTopic,
    setServerChatVersion
  ])

  const lastCharacterIdRef = React.useRef<string | null>(
    selectedCharacter?.id ? String(selectedCharacter.id) : null
  )

  React.useEffect(() => {
    const normalizedStoreModel = normalizeSelectedModel(selectedModelFromStore)
    const normalizedStoredModel = normalizeSelectedModel(storedSelectedModel)

    if (!normalizedStoreModel && normalizedStoredModel) {
      setSelectedModelInStore(normalizedStoredModel)
      return
    }

    if (normalizedStoreModel !== normalizedStoredModel) {
      void setStoredSelectedModel(normalizedStoreModel)
    }
  }, [
    normalizeSelectedModel,
    selectedModelFromStore,
    setSelectedModelInStore,
    setStoredSelectedModel,
    storedSelectedModel
  ])

  React.useEffect(() => {
    const nextId = selectedCharacter?.id ? String(selectedCharacter.id) : null
    if (lastCharacterIdRef.current === nextId) {
      return
    }
    lastCharacterIdRef.current = nextId
    setServerChatId(null)
    resetServerChatState()
    setMessages([])
    setHistory([])
    setHistoryId(null)
  }, [
    resetServerChatState,
    selectedCharacter?.id,
    setHistory,
    setHistoryId,
    setMessages,
    setServerChatId
  ])

  React.useEffect(() => {
    if (!serverChatId || temporaryChat) return
    void ensureServerChatHistoryId(serverChatId, serverChatTitle || undefined)
  }, [ensureServerChatHistoryId, serverChatId, serverChatTitle, temporaryChat])

  // Persist prompt selections across views/contexts
  const [storedSystemPrompt, setStoredSystemPrompt] = useStorage<string | null>(
    "selectedSystemPrompt",
    null
  )
  const [storedQuickPrompt, setStoredQuickPrompt] = useStorage<string | null>(
    "selectedQuickPrompt",
    null
  )
  const storedSystemPromptRef = React.useRef<string | null>(storedSystemPrompt)
  const storedQuickPromptRef = React.useRef<string | null>(storedQuickPrompt)

  React.useEffect(() => {
    if (storedSystemPrompt && storedSystemPrompt !== selectedSystemPrompt) {
      logE2EDebug("syncSystem", {
        storedSystemPrompt,
        selectedSystemPrompt
      })
      storedSystemPromptRef.current = storedSystemPrompt
      setSelectedSystemPrompt(storedSystemPrompt)
    }
  }, [selectedSystemPrompt, setSelectedSystemPrompt, storedSystemPrompt])

  React.useEffect(() => {
    if (storedQuickPrompt && storedQuickPrompt !== selectedQuickPrompt) {
      logE2EDebug("syncQuick", {
        storedQuickPrompt,
        selectedQuickPrompt
      })
      storedQuickPromptRef.current = storedQuickPrompt
      setSelectedQuickPrompt(storedQuickPrompt)
    }
  }, [selectedQuickPrompt, setSelectedQuickPrompt, storedQuickPrompt])

  React.useEffect(() => {
    const nextValue = selectedSystemPrompt ?? null
    if (nextValue === storedSystemPromptRef.current) {
      return
    }
    logE2EDebug("storeSystem", {
      nextValue,
      storedSystemPromptRef: storedSystemPromptRef.current
    })
    storedSystemPromptRef.current = nextValue
    setStoredSystemPrompt(nextValue)
  }, [selectedSystemPrompt, setStoredSystemPrompt])

  React.useEffect(() => {
    const nextValue = selectedQuickPrompt ?? null
    if (nextValue === storedQuickPromptRef.current) {
      return
    }
    logE2EDebug("storeQuick", {
      nextValue,
      storedQuickPromptRef: storedQuickPromptRef.current
    })
    storedQuickPromptRef.current = nextValue
    setStoredQuickPrompt(nextValue)
  }, [selectedQuickPrompt, setStoredQuickPrompt])

  const lastHydratedRagDefaultsRef = React.useRef<string | null>(null)
  React.useEffect(() => {
    if (historyId || serverChatId || messages.length > 0) {
      lastHydratedRagDefaultsRef.current = null
      return
    }

    const normalizedSettings = {
      ...DEFAULT_RAG_SETTINGS,
      ...(storedRagSettings || {})
    }
    const serialized = JSON.stringify(normalizedSettings)
    if (serialized === lastHydratedRagDefaultsRef.current) {
      return
    }
    lastHydratedRagDefaultsRef.current = serialized

    const searchMode =
      normalizedSettings.search_mode === "fts" ||
      normalizedSettings.search_mode === "vector" ||
      normalizedSettings.search_mode === "hybrid"
        ? normalizedSettings.search_mode
        : DEFAULT_RAG_SETTINGS.search_mode
    const topKValue =
      typeof normalizedSettings.top_k === "number" &&
      Number.isFinite(normalizedSettings.top_k)
        ? normalizedSettings.top_k
        : DEFAULT_RAG_SETTINGS.top_k
    const sourcesValue =
      Array.isArray(normalizedSettings.sources) &&
      normalizedSettings.sources.every((source) => typeof source === "string")
        ? normalizedSettings.sources
        : DEFAULT_RAG_SETTINGS.sources

    setRagSearchMode(searchMode)
    setRagTopK(topKValue)
    setRagEnableGeneration(Boolean(normalizedSettings.enable_generation))
    setRagEnableCitations(Boolean(normalizedSettings.enable_citations))
    setRagSources(sourcesValue)
    setRagAdvancedOptions(toRagAdvancedOptions(normalizedSettings))
  }, [
    historyId,
    messages.length,
    serverChatId,
    setRagAdvancedOptions,
    setRagEnableCitations,
    setRagEnableGeneration,
    setRagSearchMode,
    setRagSources,
    setRagTopK,
    storedRagSettings
  ])

  const handleFileUpload = async (file: File) => {
    try {
      const isImage = file.type.startsWith("image/")

      if (isImage) {
        return file
      }

      if (file.size > maxContextFileSizeBytes) {
        notification.error({
          message: t("upload.fileTooLargeTitle", "File Too Large"),
          description: t("upload.fileTooLargeDescription", {
            defaultValue: "File size must be less than {{size}}",
            size: maxContextFileSizeLabel
          })
        })
        return
      }

      const fileId = generateID()

      const { processFileUpload } = await import("~/utils/file-processor")
      const source = await processFileUpload(file)

      const uploadedFile: UploadedFile = {
        id: fileId,
        filename: file.name,
        type: file.type,
        content: source.content,
        size: file.size,
        uploadedAt: Date.now(),
        processed: false
      }

      setUploadedFiles([...uploadedFiles, uploadedFile])
      setContextFiles([...contextFiles, uploadedFile])

      return file
    } catch (error) {
      console.error("Error uploading file:", error)
      notification.error({
        message: t("upload.uploadFailedTitle", "Upload Failed"),
        description: t(
          "upload.uploadFailedDescription",
          "Failed to upload file. Please try again."
        )
      })
      throw error
    }
  }

  const removeUploadedFile = async (fileId: string) => {
    setUploadedFiles(uploadedFiles.filter((f) => f.id !== fileId))
    setContextFiles(contextFiles.filter((f) => f.id !== fileId))
  }

  const clearUploadedFiles = () => {
    setUploadedFiles([])
  }

  const handleSetFileRetrievalEnabled = async (enabled: boolean) => {
    setFileRetrievalEnabled(enabled)
  }

  const clearChat = useClearChat({ textareaRef })
  const {
    onSubmit,
    sendPerModelReply,
    regenerateLastMessage,
    stopStreamingRequest,
    editMessage,
    deleteMessage,
    toggleMessagePinned,
    createChatBranch,
    createCompareBranch
  } = useChatActions({
    t,
    notification,
    abortController,
    setAbortController,
    messages,
    setMessages,
    history,
    setHistory,
    historyId,
    setHistoryId,
    temporaryChat,
    selectedModel,
    useOCR,
    selectedSystemPrompt,
    selectedKnowledge,
    toolChoice,
    webSearch,
    currentChatModelSettings,
    setIsSearchingInternet,
    setIsProcessing,
    setStreaming,
    setActionInfo,
    fileRetrievalEnabled,
    ragMediaIds,
    ragSearchMode,
    ragTopK,
    ragEnableGeneration,
    ragEnableCitations,
    ragSources,
    ragAdvancedOptions,
    serverChatId,
    serverChatTitle,
    serverChatCharacterId,
    serverChatState,
    serverChatTopic,
    serverChatClusterId,
    serverChatSource,
    serverChatExternalRef,
    setServerChatId,
    setServerChatTitle,
    setServerChatCharacterId,
    setServerChatMetaLoaded,
    setServerChatState,
    setServerChatVersion,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef,
    ensureServerChatHistoryId,
    contextFiles,
    setContextFiles,
    documentContext,
    setDocumentContext,
    uploadedFiles,
    compareModeActive,
    compareSelectedModels,
    compareMaxModels,
    compareFeatureEnabled,
    markCompareHistoryCreated,
    compareAutoDisabledFlag,
    setCompareAutoDisabledFlag,
    messageSteeringPrompts,
    messageSteeringMode,
    messageSteeringForceNarrate,
    clearMessageSteering,
    replyTarget,
    clearReplyTarget,
    setSelectedQuickPrompt,
    setSelectedSystemPrompt,
    invalidateServerChatHistory,
    selectedCharacter
  })

  return {
    editMessage,
    deleteMessage,
    toggleMessagePinned,
    messages,
    setMessages,
    onSubmit,
    setStreaming,
    streaming,
    setHistory,
    historyId,
    setHistoryId,
    selectServerChat,
    setIsFirstMessage,
    isLoading,
    setIsLoading,
    isProcessing,
    setIsProcessing,
    stopStreamingRequest,
    clearChat,
    selectedModel,
    selectedModelIsLoading: selectedModelStorageMeta.isLoading,
    setSelectedModel,
    chatMode,
    setChatMode,
    isEmbedding,
    setIsEmbedding,
    speechToTextLanguage,
    setSpeechToTextLanguage,
    regenerateLastMessage,
    webSearch,
    setWebSearch,
    toolChoice,
    setToolChoice,
    isSearchingInternet,
    setIsSearchingInternet,
    selectedQuickPrompt,
    setSelectedQuickPrompt,
    selectedSystemPrompt,
    setSelectedSystemPrompt,
    messageSteeringMode,
    setMessageSteeringMode,
    messageSteeringForceNarrate,
    setMessageSteeringForceNarrate,
    clearMessageSteering,
    textareaRef,
    selectedKnowledge,
    setSelectedKnowledge,
    ttsEnabled,
    temporaryChat,
    setTemporaryChat,
    useOCR,
    setUseOCR,
    defaultInternetSearchOn,
    history,
    uploadedFiles,
    contextFiles,
    fileRetrievalEnabled,
    setFileRetrievalEnabled: handleSetFileRetrievalEnabled,
    handleFileUpload,
    removeUploadedFile,
    clearUploadedFiles,
    actionInfo,
    setActionInfo,
    setContextFiles,
    createChatBranch,
    queuedMessages: storeQueuedMessages,
    addQueuedMessage: storeAddQueuedMessage,
    clearQueuedMessages: storeClearQueuedMessages,
    serverChatId,
    setServerChatId,
    serverChatTitle,
    setServerChatTitle,
    serverChatCharacterId,
    setServerChatCharacterId,
    serverChatMetaLoaded,
    setServerChatMetaLoaded,
    serverChatState,
    setServerChatState,
    serverChatVersion,
    setServerChatVersion,
    serverChatTopic,
    setServerChatTopic,
    serverChatClusterId,
    setServerChatClusterId,
    serverChatSource,
    setServerChatSource,
    serverChatExternalRef,
    setServerChatExternalRef,
    ragMediaIds,
    setRagMediaIds,
    ragSearchMode,
    setRagSearchMode,
    ragTopK,
    setRagTopK,
    ragEnableGeneration,
    setRagEnableGeneration,
    ragEnableCitations,
    setRagEnableCitations,
    ragSources,
    setRagSources,
    ragPinnedResults,
    setRagPinnedResults,
    documentContext,
    compareMode,
    setCompareMode,
    compareFeatureEnabled,
    setCompareFeatureEnabled,
    compareSelectedModels,
    setCompareSelectedModels,
    compareSelectionByCluster,
    setCompareSelectionForCluster,
    compareActiveModelsByCluster,
    setCompareActiveModelsForCluster,
    sendPerModelReply,
    createCompareBranch,
    compareParentByHistory,
    setCompareParentForHistory,
    compareCanonicalByCluster,
    setCompareCanonicalForCluster,
    compareContinuationModeByCluster,
    setCompareContinuationModeForCluster,
    compareSplitChats,
    setCompareSplitChat,
    compareMaxModels,
    setCompareMaxModels,
    selectedCharacter,
    setSelectedCharacter,
    replyTarget,
    clearReplyTarget
  }
}
