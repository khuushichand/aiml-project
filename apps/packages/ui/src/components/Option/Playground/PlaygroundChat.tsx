import React from "react"
import { useQuery } from "@tanstack/react-query"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import { PlaygroundEmpty } from "./PlaygroundEmpty"
import { PlaygroundMessage } from "@/components/Common/Playground/Message"
import { ProviderIcons } from "@/components/Common/ProviderIcon"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"
import { Clock, DollarSign, Hash } from "lucide-react"
import { generateID, updateMessageMedia } from "@/db/dexie/helpers"
import { decodeChatErrorPayload } from "@/utils/chat-error-message"
import { humanizeMilliseconds } from "@/utils/humanize-milliseconds"
import { trackCompareMetric } from "@/utils/compare-metrics"
import { resolveMessageCostUsd } from "@/components/Common/Playground/message-usage"
import { formatCost } from "@/utils/model-pricing"
import { fetchChatModels } from "@/services/tldw-server"
import { tldwModels } from "@/services/tldw"
import { tldwClient, type ChatLinkedResearchRun } from "@/services/tldw/TldwApiClient"
import { applyVariantToMessage } from "@/utils/message-variants"
import {
  buildNormalizedPreview,
  computeNormalizedPreviewBudget
} from "./compare-normalized-preview"
import { computeResponseDiffPreview } from "./compare-response-diff"
import { ResearchRunStatusStack } from "./ResearchRunStatusStack"
import { getChatLinkedResearchRefetchInterval } from "./research-run-status"
import type { Character } from "@/types/character"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { ChatGreetingPicker } from "@/components/Common/ChatGreetingPicker"
import {
  deriveAttachedResearchContext,
  isDeepResearchCompletionMetadata,
  type AttachedResearchContext
} from "./research-chat-context"
import {
  IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
  IMAGE_GENERATION_USER_MESSAGE_TYPE,
  isImageGenerationMessageType,
  normalizeImageGenerationVariantBundle,
  type ImageGenerationRequestSnapshot
} from "@/utils/image-generation-chat"

type TimelineBlock =
  | { kind: "single"; index: number }
  | {
      kind: "compare"
      userIndex: number
      assistantIndices: number[]
      clusterId: string
    }

type TimelineMessageShape = {
  messageType?: string
  message_type?: string
  clusterId?: string
}

const resolveTimelineMessageType = (
  message: TimelineMessageShape
): string | undefined => message.messageType ?? message.message_type

const shouldHideTimelineMessage = (message: TimelineMessageShape): boolean =>
  resolveTimelineMessageType(message) === IMAGE_GENERATION_USER_MESSAGE_TYPE

type PlaygroundChatProps = {
  searchQuery?: string
  matchedMessageIndices?: Set<number>
  activeSearchMessageIndex?: number | null
  onAttachResearchContext?: (context: AttachedResearchContext) => void
}

const PerModelMiniComposer: React.FC<{
  placeholder: string
  disabled?: boolean
  helperText?: string | null
  onSend: (text: string) => Promise<void> | void
}> = ({ placeholder, disabled = false, helperText, onSend }) => {
  const { t } = useTranslation(["common"])
  const [value, setValue] = React.useState("")

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) {
      return
    }
    await onSend(trimmed)
    setValue("")
  }

  return (
    <div className="mt-2 space-y-1 text-[11px]">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          className="flex-1 rounded border border-border bg-surface px-2 py-1 text-[11px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || value.trim().length === 0}
          title={t("common:send", "Send") as string}
          className="rounded bg-primary px-2 py-1 text-[11px] font-medium text-surface disabled:cursor-not-allowed disabled:opacity-60 hover:bg-primaryStrong">
          {t("common:send", "Send")}
        </button>
      </form>
      {helperText && (
        <div className="text-[10px] text-text-subtle">
          {helperText}
        </div>
      )}
    </div>
  )
}

const buildBlocks = (messages: TimelineMessageShape[]): TimelineBlock[] => {
  const blocks: TimelineBlock[] = []
  const used = new Set<number>()

  messages.forEach((msg, idx) => {
    if (used.has(idx)) return
    if (shouldHideTimelineMessage(msg)) {
      used.add(idx)
      return
    }
    const messageType = resolveTimelineMessageType(msg)

    if (messageType === "compare:user" && msg.clusterId) {
      const assistants: number[] = []
      messages.forEach((m, j) => {
        if (j === idx || used.has(j)) return
        if (shouldHideTimelineMessage(m)) {
          used.add(j)
          return
        }
        if (m.clusterId === msg.clusterId) {
          if (resolveTimelineMessageType(m) === "compare:reply") {
            assistants.push(j)
          }
          used.add(j)
        }
      })
      used.add(idx)
      blocks.push({
        kind: "compare",
        userIndex: idx,
        assistantIndices: assistants,
        clusterId: msg.clusterId
      })
    } else {
      blocks.push({ kind: "single", index: idx })
    }
  })

  return blocks
}

export const PlaygroundChat = ({
  searchQuery,
  matchedMessageIndices,
  activeSearchMessageIndex = null,
  onAttachResearchContext
}: PlaygroundChatProps) => {
  const { t } = useTranslation(["playground", "common"])
  const notification = useAntdNotification()
  const {
    messages,
    setMessages,
    streaming,
    isProcessing,
    regenerateLastMessage,
    isSearchingInternet,
    editMessage,
    deleteMessage,
    toggleMessagePinned,
    ttsEnabled,
    onSubmit,
    actionInfo,
    messageSteeringMode,
    setMessageSteeringMode,
    messageSteeringForceNarrate,
    setMessageSteeringForceNarrate,
    clearMessageSteering,
    createChatBranch,
    createCompareBranch,
    temporaryChat,
    serverChatId,
    serverChatCharacterId,
    serverChatLoadState,
    serverChatLoadError,
    stopStreamingRequest,
    isEmbedding,
    compareMode,
    compareFeatureEnabled,
    compareSelectionByCluster,
    setCompareSelectionForCluster,
    compareActiveModelsByCluster,
    setCompareActiveModelsForCluster,
    setCompareSelectedModels,
    historyId,
    setSelectedModel,
    setCompareMode,
    sendPerModelReply,
    compareCanonicalByCluster,
    setCompareCanonicalForCluster,
    compareContinuationModeByCluster,
    setCompareContinuationModeForCluster,
    setCompareParentForHistory,
    compareSplitChats,
    setCompareSplitChat,
    compareMaxModels
  } = useMessageOption()
  const [openReasoning] = useStorage("openReasoning", false)
  const [selectedCharacter] = useSelectedCharacter<Character | null>(null)
  const { data: chatModels = [] } = useQuery({
    queryKey: ["playground:chatModels"],
    queryFn: () => fetchChatModels({ returnEmpty: true }),
    enabled: true
  })
  const [collapsedClusters, setCollapsedClusters] = React.useState<
    Record<string, boolean>
  >({})
  const [hiddenModelsByCluster, setHiddenModelsByCluster] = React.useState<
    Record<string, string[]>
  >({})
  const [normalizedPreviewByCluster, setNormalizedPreviewByCluster] =
    React.useState<Record<string, boolean>>({})
  const [diffPreviewByCluster, setDiffPreviewByCluster] = React.useState<
    Record<string, boolean>
  >({})
  const compareModeActive = compareFeatureEnabled && compareMode
  const stableHistoryId =
    temporaryChat || historyId === "temp" ? null : historyId
  const linkedResearchRunsEnabled = Boolean(serverChatId) && !temporaryChat
  const [conversationInstanceId, setConversationInstanceId] = React.useState(
    () => generateID()
  )
  const [linkedResearchRunErrorCount, setLinkedResearchRunErrorCount] = React.useState(0)
  const previousMessageCount = React.useRef(messages.length)
  const latestLinkedResearchSuccessAt = React.useRef(0)
  const latestLinkedResearchErrorAt = React.useRef(0)

  const linkedResearchRunsQuery = useQuery({
    queryKey: ["playground:chat-linked-research-runs", serverChatId],
    queryFn: async () => {
      if (!serverChatId) {
        return { runs: [] as ChatLinkedResearchRun[] }
      }
      await tldwClient.initialize().catch(() => null)
      return await tldwClient.listChatResearchRuns(serverChatId)
    },
    enabled: linkedResearchRunsEnabled,
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data as { runs?: ChatLinkedResearchRun[] } | undefined
      const runs = Array.isArray(data?.runs) ? data.runs : []
      return getChatLinkedResearchRefetchInterval(runs, linkedResearchRunErrorCount)
    }
  })

  React.useEffect(() => {
    const hasStableId = Boolean(serverChatId || stableHistoryId)
    if (
      !hasStableId &&
      messages.length === 0 &&
      previousMessageCount.current > 0
    ) {
      setConversationInstanceId(generateID())
    }
    previousMessageCount.current = messages.length
  }, [messages.length, serverChatId, stableHistoryId])

  React.useEffect(() => {
    if (!linkedResearchRunsEnabled) {
      latestLinkedResearchSuccessAt.current = 0
      latestLinkedResearchErrorAt.current = 0
      setLinkedResearchRunErrorCount(0)
    }
  }, [linkedResearchRunsEnabled])

  React.useEffect(() => {
    if (
      linkedResearchRunsQuery.isSuccess &&
      linkedResearchRunsQuery.dataUpdatedAt > 0 &&
      linkedResearchRunsQuery.dataUpdatedAt !== latestLinkedResearchSuccessAt.current
    ) {
      latestLinkedResearchSuccessAt.current = linkedResearchRunsQuery.dataUpdatedAt
      latestLinkedResearchErrorAt.current = 0
      setLinkedResearchRunErrorCount(0)
    }
  }, [linkedResearchRunsQuery.dataUpdatedAt, linkedResearchRunsQuery.isSuccess])

  React.useEffect(() => {
    if (
      linkedResearchRunsQuery.isError &&
      linkedResearchRunsQuery.errorUpdatedAt > 0 &&
      linkedResearchRunsQuery.errorUpdatedAt !== latestLinkedResearchErrorAt.current
    ) {
      latestLinkedResearchErrorAt.current = linkedResearchRunsQuery.errorUpdatedAt
      setLinkedResearchRunErrorCount((current) => current + 1)
    }
  }, [linkedResearchRunsQuery.errorUpdatedAt, linkedResearchRunsQuery.isError])
  const blocks = React.useMemo(() => buildBlocks(messages), [messages])
  const linkedResearchRuns = React.useMemo(() => {
    if (!linkedResearchRunsEnabled || !linkedResearchRunsQuery.isSuccess) {
      return []
    }
    return Array.isArray(linkedResearchRunsQuery.data?.runs)
      ? linkedResearchRunsQuery.data.runs
      : []
  }, [linkedResearchRunsEnabled, linkedResearchRunsQuery.data?.runs, linkedResearchRunsQuery.isSuccess])
  const handleAttachResearchRun = React.useCallback(
    async (runId: string, query: string) => {
      if (!onAttachResearchContext) {
        return
      }
      await tldwClient.initialize().catch(() => null)
      const bundle = await tldwClient.getResearchBundle(runId)
      onAttachResearchContext(
        deriveAttachedResearchContext(bundle, runId, query)
      )
    },
    [onAttachResearchContext]
  )
  const buildMessageUseInChatHandler = React.useCallback(
    (metadataExtra?: Record<string, unknown>) => {
      const completion = isDeepResearchCompletionMetadata(
        metadataExtra?.deep_research_completion
      )
        ? metadataExtra.deep_research_completion
        : null
      if (!completion) {
        return undefined
      }
      return () => {
        void handleAttachResearchRun(completion.run_id, completion.query)
      }
    },
    [handleAttachResearchRun]
  )
  const showSelectedServerChatLoadFailure =
    messages.length === 0 &&
    Boolean(serverChatId) &&
    serverChatLoadState === "failed"
  const selectedServerChatLoadFailureMessage =
    serverChatLoadError?.trim() ||
    (t(
      "playground:selectedServerChatLoadFailure",
      "Failed to load the selected conversation."
    ) as string)
  const normalizedSearchQuery =
    typeof searchQuery === "string" ? searchQuery.trim() : ""
  const resolveSearchMatch = React.useCallback(
    (messageIndex: number): "active" | "match" | null => {
      if (!normalizedSearchQuery) return null
      if (!matchedMessageIndices?.has(messageIndex)) return null
      return activeSearchMessageIndex === messageIndex ? "active" : "match"
    },
    [activeSearchMessageIndex, matchedMessageIndices, normalizedSearchQuery]
  )
  const runContinue = React.useCallback(() => {
    void onSubmit({
      image: "",
      message: "",
      isContinue: true
    })
  }, [onSubmit])
  const runSteeredContinue = React.useCallback(
    (mode: "continue_as_user" | "impersonate_user") => {
      void onSubmit({
        image: "",
        message: "",
        isContinue: true,
        messageSteeringOverride: {
          mode,
          forceNarrate: messageSteeringForceNarrate
        },
        continueOutputTarget:
          mode === "impersonate_user" ? "composer_input" : "chat"
      })
    },
    [messageSteeringForceNarrate, onSubmit]
  )
  const handleRegenerateGeneratedImage = React.useCallback(
    async (payload: {
      messageId?: string
      request: ImageGenerationRequestSnapshot | null
    }) => {
      const request = payload.request
      if (!request?.prompt || !request?.backend) {
        notification.warning({
          message: t("warning", { defaultValue: "Warning" }),
          description: t(
            "playground:imageGeneration.regenUnavailable",
            "Original image prompt metadata is unavailable for regeneration."
          )
        })
        return
      }
      const regenerateFromMessage =
        payload.messageId && payload.messageId.length > 0
          ? messages.find((entry) => entry.id === payload.messageId)
          : undefined
      const nextMessages =
        regenerateFromMessage?.id && messages.length > 0
          ? messages.filter((entry) => entry.id !== regenerateFromMessage.id)
          : messages

      if (regenerateFromMessage?.id) {
        setMessages(nextMessages)
      }

      await onSubmit({
        message: request.prompt,
        image: "",
        docs: [],
        isRegenerate: Boolean(regenerateFromMessage),
        regenerateFromMessage,
        messages: nextMessages,
        imageBackendOverride: request.backend,
        userMessageType: IMAGE_GENERATION_USER_MESSAGE_TYPE,
        assistantMessageType: IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
        imageGenerationRequest: request,
        imageGenerationSource: "message-regen"
      })
    },
    [messages, notification, onSubmit, setMessages, t]
  )
  const normalizeImageVariantState = React.useCallback(
    (
      entry: any,
      variants: any[],
      activeVariantIndex: number,
      options?: {
        hasVisibleVariant?: boolean
        generationInfo?: unknown
      }
    ) => {
      const normalized = normalizeImageGenerationVariantBundle({
        messageId: entry.id,
        messageGenerationInfo:
          options?.generationInfo !== undefined
            ? options.generationInfo
            : entry.generationInfo,
        variants,
        activeVariantIndex,
        fallbackCreatedAt: Date.now(),
        hasVisibleVariant: options?.hasVisibleVariant ?? true
      })

      if (variants.length === 0) {
        return {
          ...entry,
          variants: [],
          activeVariantIndex: normalized.activeVariantIndex,
          generationInfo: normalized.generationInfo ?? entry.generationInfo
        }
      }

      const activeVariant = normalized.variants[normalized.activeVariantIndex]
      if (!activeVariant) {
        return {
          ...entry,
          variants: normalized.variants,
          activeVariantIndex: normalized.activeVariantIndex,
          generationInfo: normalized.generationInfo ?? entry.generationInfo
        }
      }

      return applyVariantToMessage(
        {
          ...entry,
          variants: normalized.variants,
          activeVariantIndex: normalized.activeVariantIndex,
          generationInfo: normalized.generationInfo ?? entry.generationInfo
        },
        activeVariant,
        normalized.activeVariantIndex
      )
    },
    []
  )
  const handleDeleteGeneratedImage = React.useCallback(
    (payload: { messageId?: string; imageIndex: number }) => {
      if (!payload.messageId) return
      let nextImages: string[] | null = null
      let nextGenerationInfo: unknown = undefined
      setMessages((prev) =>
        prev.map((entry) => {
          if (entry.id !== payload.messageId) return entry
          const variants = Array.isArray(entry.variants) ? entry.variants : []
          if (
            variants.length > 0 &&
            typeof entry.activeVariantIndex === "number"
          ) {
            const activeVariantIndex = Math.max(
              0,
              Math.min(entry.activeVariantIndex, variants.length - 1)
            )
            const currentVariant = variants[activeVariantIndex]
            const currentVariantImages = Array.isArray(currentVariant?.images)
              ? currentVariant.images
              : []
            const remainingVariantImages = currentVariantImages.filter(
              (_, idx) => idx !== payload.imageIndex
            )

            if (remainingVariantImages.length > 0) {
              const nextVariants = [...variants]
              nextVariants[activeVariantIndex] = {
                ...currentVariant,
                images: remainingVariantImages
              }
              const updatedEntry = normalizeImageVariantState(
                {
                  ...entry,
                  variants: nextVariants,
                  activeVariantIndex
                },
                nextVariants,
                activeVariantIndex
              )
              nextImages = Array.isArray(updatedEntry.images)
                ? updatedEntry.images
                : []
              nextGenerationInfo = updatedEntry.generationInfo
              return updatedEntry
            }

            const nextVariants = variants.filter(
              (_, idx) => idx !== activeVariantIndex
            )
            if (nextVariants.length > 0) {
              const nextActiveIndex = Math.max(
                0,
                Math.min(activeVariantIndex, nextVariants.length - 1)
              )
              const updatedEntry = normalizeImageVariantState(
                {
                  ...entry,
                  variants: nextVariants,
                  activeVariantIndex: nextActiveIndex
                },
                nextVariants,
                nextActiveIndex
              )
              nextImages = Array.isArray(updatedEntry.images)
                ? updatedEntry.images
                : []
              nextGenerationInfo = updatedEntry.generationInfo
              return updatedEntry
            }

            nextImages = []
            const updatedEntry = normalizeImageVariantState(
              {
                ...entry,
                images: [],
                variants: [],
                activeVariantIndex: 0
              },
              [],
              0,
              { hasVisibleVariant: false }
            )
            nextGenerationInfo = updatedEntry.generationInfo
            return updatedEntry
          }
          const current = Array.isArray(entry.images) ? entry.images : []
          const remainingImages = current.filter((_, idx) => idx !== payload.imageIndex)
          const updatedEntry = normalizeImageVariantState(
            {
              ...entry,
              images: remainingImages
            },
            [],
            0,
            { hasVisibleVariant: remainingImages.length > 0 }
          )
          nextImages = Array.isArray(updatedEntry.images)
            ? updatedEntry.images
            : remainingImages
          nextGenerationInfo = updatedEntry.generationInfo
          return updatedEntry
        })
      )
      if (nextImages !== null && stableHistoryId) {
        const updates: { images?: string[]; generationInfo?: any } = {
          images: nextImages
        }
        if (nextGenerationInfo !== undefined) {
          updates.generationInfo = nextGenerationInfo
        }
        void updateMessageMedia(payload.messageId, updates).catch(() => null)
      }
    },
    [normalizeImageVariantState, setMessages, stableHistoryId]
  )
  const handleSelectGeneratedImageVariant = React.useCallback(
    (payload: { messageId?: string; variantIndex: number }) => {
      if (!payload.messageId) return
      let nextImages: string[] | null = null
      let nextGenerationInfo: unknown = undefined
      setMessages((prev) =>
        prev.map((entry) => {
          if (entry.id !== payload.messageId) return entry
          const variants = Array.isArray(entry.variants) ? entry.variants : []
          if (variants.length === 0) return entry
          if (
            payload.variantIndex < 0 ||
            payload.variantIndex >= variants.length
          ) {
            return entry
          }
          const updatedEntry = normalizeImageVariantState(
            {
              ...entry,
              variants,
              activeVariantIndex: payload.variantIndex
            },
            variants,
            payload.variantIndex
          )
          nextImages = Array.isArray(updatedEntry.images)
            ? updatedEntry.images
            : []
          nextGenerationInfo = updatedEntry.generationInfo
          return updatedEntry
        })
      )
      if (nextImages !== null && stableHistoryId) {
        const updates: { images?: string[]; generationInfo?: any } = {
          images: nextImages
        }
        if (nextGenerationInfo !== undefined) {
          updates.generationInfo = nextGenerationInfo
        }
        void updateMessageMedia(payload.messageId, updates).catch(() => null)
      }
    },
    [normalizeImageVariantState, setMessages, stableHistoryId]
  )
  const handleKeepGeneratedImageVariant = React.useCallback(
    (payload: { messageId?: string; variantIndex: number }) => {
      if (!payload.messageId) return
      let nextImages: string[] | null = null
      let nextGenerationInfo: unknown = undefined
      setMessages((prev) =>
        prev.map((entry) => {
          if (entry.id !== payload.messageId) return entry
          const variants = Array.isArray(entry.variants) ? entry.variants : []
          if (variants.length === 0) return entry
          const targetIndex = Math.max(
            0,
            Math.min(payload.variantIndex, variants.length - 1)
          )
          const targetVariant = variants[targetIndex]
          const nextVariants = [
            ...variants.filter((_, idx) => idx !== targetIndex),
            targetVariant
          ]
          const nextActiveIndex = nextVariants.length - 1
          const updatedEntry = normalizeImageVariantState(
            {
              ...entry,
              variants: nextVariants,
              activeVariantIndex: nextActiveIndex
            },
            nextVariants,
            nextActiveIndex
          )
          nextImages = Array.isArray(updatedEntry.images)
            ? updatedEntry.images
            : []
          nextGenerationInfo = updatedEntry.generationInfo
          return updatedEntry
        })
      )
      if (nextImages !== null && stableHistoryId) {
        const updates: { images?: string[]; generationInfo?: any } = {
          images: nextImages
        }
        if (nextGenerationInfo !== undefined) {
          updates.generationInfo = nextGenerationInfo
        }
        void updateMessageMedia(payload.messageId, updates).catch(() => null)
      }
    },
    [normalizeImageVariantState, setMessages, stableHistoryId]
  )
  const handleDeleteGeneratedImageVariant = React.useCallback(
    (payload: { messageId?: string; variantIndex: number }) => {
      if (!payload.messageId) return
      let nextImages: string[] | null = null
      let nextGenerationInfo: unknown = undefined
      setMessages((prev) =>
        prev.map((entry) => {
          if (entry.id !== payload.messageId) return entry
          const variants = Array.isArray(entry.variants) ? entry.variants : []
          if (variants.length === 0) return entry
          if (
            payload.variantIndex < 0 ||
            payload.variantIndex >= variants.length
          ) {
            return entry
          }
          const nextVariants = variants.filter(
            (_, idx) => idx !== payload.variantIndex
          )
          if (nextVariants.length === 0) {
            nextImages = []
            const updatedEntry = normalizeImageVariantState(
              {
                ...entry,
                images: [],
                variants: [],
                activeVariantIndex: 0
              },
              [],
              0,
              { hasVisibleVariant: false }
            )
            nextGenerationInfo = updatedEntry.generationInfo
            return updatedEntry
          }
          const nextActiveIndex = Math.max(
            0,
            Math.min(payload.variantIndex, nextVariants.length - 1)
          )
          const updatedEntry = normalizeImageVariantState(
            {
              ...entry,
              variants: nextVariants,
              activeVariantIndex: nextActiveIndex
            },
            nextVariants,
            nextActiveIndex
          )
          nextImages = Array.isArray(updatedEntry.images)
            ? updatedEntry.images
            : []
          nextGenerationInfo = updatedEntry.generationInfo
          return updatedEntry
        })
      )
      if (nextImages !== null && stableHistoryId) {
        const updates: { images?: string[]; generationInfo?: any } = {
          images: nextImages
        }
        if (nextGenerationInfo !== undefined) {
          updates.generationInfo = nextGenerationInfo
        }
        void updateMessageMedia(payload.messageId, updates).catch(() => null)
      }
    },
    [normalizeImageVariantState, setMessages, stableHistoryId]
  )
  const handleDeleteAllGeneratedImageVariants = React.useCallback(
    (payload: { messageId?: string }) => {
      if (!payload.messageId) return
      let nextGenerationInfo: unknown = undefined
      setMessages((prev) =>
        prev.map((entry) =>
          entry.id === payload.messageId
            ? (() => {
                const updatedEntry = normalizeImageVariantState(
                  {
                    ...entry,
                    images: [],
                    variants: [],
                    activeVariantIndex: 0
                  },
                  [],
                  0,
                  { hasVisibleVariant: false }
                )
                nextGenerationInfo = updatedEntry.generationInfo
                return updatedEntry
              })()
            : entry
        )
      )
      if (stableHistoryId) {
        const updates: { images?: string[]; generationInfo?: any } = {
          images: []
        }
        if (nextGenerationInfo !== undefined) {
          updates.generationInfo = nextGenerationInfo
        }
        void updateMessageMedia(payload.messageId, updates).catch(() => null)
      }
    },
    [normalizeImageVariantState, setMessages, stableHistoryId]
  )
  const selectedGreeting = React.useMemo(() => {
    if (!selectedCharacter || typeof selectedCharacter.greeting !== "string") {
      return ""
    }
    return selectedCharacter.greeting.trim()
  }, [selectedCharacter])
  const normalizeGreetingText = React.useCallback(
    (value: string) => value.replace(/\s+/g, " ").trim().toLowerCase(),
    []
  )
  const greetingNeedle = React.useMemo(() => {
    if (!selectedGreeting) return ""
    const normalized = normalizeGreetingText(selectedGreeting)
    if (!normalized) return ""
    return normalized.slice(0, 180)
  }, [normalizeGreetingText, selectedGreeting])
  const firstAssistantIndex = React.useMemo(
    () => messages.findIndex((msg) => msg?.role === "assistant" || msg?.isBot),
    [messages]
  )
  const firstUserIndex = React.useMemo(
    () =>
      messages.findIndex(
        (msg) => msg?.role === "user" || msg?.isBot === false
      ),
    [messages]
  )
  const hasSelectedCharacter = Boolean(selectedCharacter?.id)
  const characterIdentityEnabled = React.useMemo(() => {
    if (!selectedCharacter?.id) return false
    if (compareModeActive) return false
    if (serverChatId) {
      if (serverChatCharacterId == null) return false
      return String(serverChatCharacterId) === String(selectedCharacter.id)
    }
    return true
  }, [
    compareModeActive,
    selectedCharacter?.id,
    serverChatCharacterId,
    serverChatId
  ])
  const resolveMessageType = React.useCallback(
    (message: any, index: number) => {
      const explicit = message?.messageType ?? message?.message_type
      if (explicit) return explicit
      if (!serverChatId && hasSelectedCharacter) {
        const isFirstAssistant = index === firstAssistantIndex
        const hasNoUserBefore = firstUserIndex === -1 || firstUserIndex > index
        if (
          isFirstAssistant &&
          hasNoUserBefore &&
          message?.isBot &&
          typeof message?.message === "string"
        ) {
          const normalizedMessage = normalizeGreetingText(message.message)
          if (greetingNeedle && normalizedMessage.includes(greetingNeedle)) {
            return "character:greeting"
          }
        }
      }
      return undefined
    },
    [
      firstAssistantIndex,
      firstUserIndex,
      hasSelectedCharacter,
      greetingNeedle,
      normalizeGreetingText,
      serverChatId
    ]
  )
  const getPreviousUserMessage = React.useCallback(
    (index: number) => {
      for (let i = index - 1; i >= 0; i--) {
        const candidate = messages[i]
        if (
          !candidate?.isBot &&
          !isImageGenerationMessageType(
            candidate?.messageType ?? candidate?.message_type
          )
        ) {
          return candidate
        }
      }
      return null
    },
    [messages]
  )
  const modelMetaById = React.useMemo(() => {
    const map = new Map<string, { label: string; provider: string }>()
    const models = (chatModels as any[]) || []
    models.forEach((model) => {
      if (!model?.model) {
        return
      }
      map.set(model.model, {
        label: model.nickname || model.model,
        provider: String(model.provider || "custom").toLowerCase()
      })
    })
    return map
  }, [chatModels])
  const getTokenCount = React.useCallback((generationInfo?: any) => {
    if (!generationInfo || typeof generationInfo !== "object") {
      return null
    }
    const toNumber = (value: unknown) =>
      typeof value === "number" && Number.isFinite(value) ? value : null
    const usage = (generationInfo as any)?.usage
    const prompt =
      toNumber(generationInfo.prompt_eval_count) ??
      toNumber(generationInfo.prompt_tokens) ??
      toNumber(generationInfo.input_tokens) ??
      toNumber(usage?.prompt_tokens) ??
      toNumber(usage?.input_tokens)
    const completion =
      toNumber(generationInfo.eval_count) ??
      toNumber(generationInfo.completion_tokens) ??
      toNumber(generationInfo.output_tokens) ??
      toNumber(usage?.completion_tokens) ??
      toNumber(usage?.output_tokens)
    const total =
      toNumber(generationInfo.total_tokens) ??
      toNumber(generationInfo.total_token_count) ??
      toNumber(usage?.total_tokens)
    const resolvedTotal =
      total ?? (prompt != null && completion != null ? prompt + completion : null)
    if (resolvedTotal == null) {
      return null
    }
    return Math.round(resolvedTotal)
  }, [])

  const handleVariantSwipe = React.useCallback(
    (messageId: string | undefined, direction: "prev" | "next") => {
      if (!messageId) return
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== messageId) return msg
          const variants = msg.variants ?? []
          if (variants.length < 2) return msg
          const currentIndex =
            typeof msg.activeVariantIndex === "number"
              ? msg.activeVariantIndex
              : variants.length - 1
          const nextIndex =
            direction === "prev" ? currentIndex - 1 : currentIndex + 1
          if (nextIndex < 0 || nextIndex >= variants.length) return msg
          return applyVariantToMessage(msg, variants[nextIndex], nextIndex)
        })
      )
    },
    [setMessages]
  )

  return (
    <>
      <div className="relative flex w-full flex-col items-center pt-16 pb-4">
        {showSelectedServerChatLoadFailure ? (
          <div className="mt-32 w-full px-6">
            <div className="mx-auto max-w-xl rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-4 text-center text-sm text-text">
              {selectedServerChatLoadFailureMessage}
            </div>
          </div>
        ) : messages.length === 0 && serverChatLoadState !== "loading" && (
          <div className="mt-32 w-full">
            <PlaygroundEmpty />
          </div>
        )}
        <ChatGreetingPicker
          selectedCharacter={selectedCharacter}
          messages={messages}
          historyId={historyId}
          serverChatId={serverChatId}
          className="mb-6 mt-4"
        />
        <ResearchRunStatusStack
          runs={linkedResearchRuns}
          onUseInChat={(run) => {
            void handleAttachResearchRun(run.run_id, run.query)
          }}
        />
        {blocks.map((block, blockIndex) => {
          if (block.kind === "single") {
            const message = messages[block.index]
            const previousUserMessage = getPreviousUserMessage(block.index)
            const resolvedMessageType = resolveMessageType(message, block.index)
            const isImageGenerationAssistantEvent =
              resolvedMessageType === IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
            return (
              <PlaygroundMessage
                key={`m-${blockIndex}`}
                isBot={message.isBot}
                message={message.message}
                name={message.name}
                role={message.role}
                images={message.images || []}
                currentMessageIndex={block.index}
                totalMessages={messages.length}
                onRegenerate={regenerateLastMessage}
                onRegenerateImage={(payload) => {
                  void handleRegenerateGeneratedImage(payload)
                }}
                onDeleteImage={handleDeleteGeneratedImage}
                onSelectImageVariant={handleSelectGeneratedImageVariant}
                onKeepImageVariant={handleKeepGeneratedImageVariant}
                onDeleteImageVariant={handleDeleteGeneratedImageVariant}
                onDeleteAllImageVariants={handleDeleteAllGeneratedImageVariants}
                isProcessing={isProcessing}
                isSearchingInternet={isSearchingInternet}
                sources={message.sources}
                onEditFormSubmit={(value, isSend) => {
                  editMessage(block.index, value, !message.isBot, isSend)
                }}
                onDeleteMessage={() => {
                  deleteMessage(block.index)
                }}
                onTogglePinned={() => {
                  void toggleMessagePinned(block.index)
                }}
                onNewBranch={() => {
                  createChatBranch(block.index)
                }}
                isTTSEnabled={ttsEnabled}
                generationInfo={message?.generationInfo}
                toolCalls={message?.toolCalls}
                toolResults={message?.toolResults}
                isStreaming={streaming}
                reasoningTimeTaken={message?.reasoning_time_taken}
                openReasoning={openReasoning}
                modelImage={message?.modelImage}
                modelName={message?.modelName}
                createdAt={message?.createdAt}
                temporaryChat={temporaryChat}
                onStopStreaming={stopStreamingRequest}
                onContinue={runContinue}
                onRunSteeredContinue={runSteeredContinue}
                documents={message?.documents}
                actionInfo={actionInfo}
                serverChatId={serverChatId}
                serverMessageId={message.serverMessageId}
                messageId={message.id}
                pinned={Boolean(message.pinned)}
                metadataExtra={message.metadataExtra}
                onUseInChat={buildMessageUseInChatHandler(message.metadataExtra)}
                discoSkillComment={message.discoSkillComment}
                historyId={stableHistoryId ?? undefined}
                conversationInstanceId={conversationInstanceId}
                feedbackQuery={previousUserMessage?.message ?? null}
                isEmbedding={isEmbedding}
                characterIdentity={selectedCharacter}
                characterIdentityEnabled={characterIdentityEnabled}
                speakerCharacterId={message.speakerCharacterId ?? null}
                speakerCharacterName={message.speakerCharacterName}
                moodLabel={message.moodLabel ?? null}
                moodConfidence={message.moodConfidence ?? null}
                moodTopic={message.moodTopic ?? null}
                searchQuery={normalizedSearchQuery || undefined}
                searchMatch={resolveSearchMatch(block.index)}
                message_type={resolvedMessageType}
                variants={message.variants}
                activeVariantIndex={message.activeVariantIndex}
                onSwipePrev={() => handleVariantSwipe(message.id, "prev")}
                onSwipeNext={() => handleVariantSwipe(message.id, "next")}
                messageSteeringMode={messageSteeringMode}
                onMessageSteeringModeChange={setMessageSteeringMode}
                messageSteeringForceNarrate={messageSteeringForceNarrate}
                onMessageSteeringForceNarrateChange={setMessageSteeringForceNarrate}
                onClearMessageSteering={clearMessageSteering}
                hideEditAndRegenerate={isImageGenerationAssistantEvent}
                hideContinue={isImageGenerationAssistantEvent}
              />
            )
          }

          const userMessage = messages[block.userIndex]
          const previousUserMessage = getPreviousUserMessage(block.userIndex)
          const replyItems = block.assistantIndices.map((i) => {
            const message = messages[i]
            const modelKey =
              (message as any).modelId || message.modelName || message.name
            return {
              index: i,
              message,
              modelKey
            }
          })
          const clusterSelection =
            compareSelectionByCluster[block.clusterId] || []
          const clusterActiveModels =
            compareActiveModelsByCluster[block.clusterId] || clusterSelection
          const modelLabels = new Map<string, string>()
          replyItems.forEach(({ message, modelKey }) => {
            if (!modelLabels.has(modelKey)) {
              modelLabels.set(
                modelKey,
                message?.modelName || message.name || modelKey
              )
            }
          })
          const getModelLabel = (modelKey: string) =>
            modelMetaById.get(modelKey)?.label ||
            modelLabels.get(modelKey) ||
            modelKey
          const getModelProvider = (modelKey: string) =>
            modelMetaById.get(modelKey)?.provider || "custom"
          const clusterModelKeys = Array.from(
            new Set(replyItems.map((item) => item.modelKey))
          )
          const selectedModelKey =
            clusterSelection.length === 1 ? clusterSelection[0] : null
          const continuationMode =
            compareContinuationModeByCluster[block.clusterId] ||
            (clusterActiveModels.length > 1 ? "compare" : "winner")
          const isChosenState = !compareModeActive && !!selectedModelKey
          const hiddenModels = hiddenModelsByCluster[block.clusterId] || []
          const normalizedPreviewEnabled =
            normalizedPreviewByCluster[block.clusterId] ?? false
          const diffPreviewEnabled = diffPreviewByCluster[block.clusterId] ?? false
          const filteredReplyItems =
            hiddenModels.length > 0
              ? replyItems.filter((item) => !hiddenModels.includes(item.modelKey))
              : replyItems
          const chosenItem = selectedModelKey
            ? replyItems.find((item) => item.modelKey === selectedModelKey) || null
            : null
          const isCollapsed = isChosenState
            ? collapsedClusters[block.clusterId] ?? true
            : false
          let visibleReplyItems =
            isCollapsed && isChosenState && selectedModelKey
              ? filteredReplyItems.filter(
                  (item) => item.modelKey === selectedModelKey
                )
              : filteredReplyItems
          if (visibleReplyItems.length === 0 && chosenItem) {
            visibleReplyItems = [chosenItem]
          }
          const alternativeCount = selectedModelKey
            ? Math.max(replyItems.length - 1, 0)
            : 0
          const setClusterCollapsed = (next: boolean) => {
            setCollapsedClusters((prev) => ({
              ...prev,
              [block.clusterId]: next
            }))
          }
          const toggleModelFilter = (modelKey: string) => {
            setHiddenModelsByCluster((prev) => {
              const hidden = new Set(prev[block.clusterId] || [])
              if (hidden.has(modelKey)) {
                hidden.delete(modelKey)
              } else {
                hidden.add(modelKey)
              }
              return {
                ...prev,
                [block.clusterId]: Array.from(hidden)
              }
            })
          }
          const clearModelFilter = () => {
            setHiddenModelsByCluster((prev) => {
              const next = { ...prev }
              delete next[block.clusterId]
              return next
            })
          }
          const setNormalizedPreview = (nextValue: boolean) => {
            setNormalizedPreviewByCluster((prev) => ({
              ...prev,
              [block.clusterId]: nextValue
            }))
          }
          const setDiffPreview = (nextValue: boolean) => {
            setDiffPreviewByCluster((prev) => ({
              ...prev,
              [block.clusterId]: nextValue
            }))
          }
          const diffBaselineModelKey =
            selectedModelKey ||
            clusterSelection[0] ||
            filteredReplyItems[0]?.modelKey ||
            null
          const diffBaselineItem = diffBaselineModelKey
            ? replyItems.find((item) => item.modelKey === diffBaselineModelKey) ||
              null
            : null
          const diffBaselineText =
            typeof diffBaselineItem?.message?.message === "string"
              ? diffBaselineItem.message.message
              : ""
          const handleContinueWithModel = (modelKey: string) => {
            setCompareMode(false)
            setSelectedModel(modelKey)
            setCompareSelectedModels([modelKey])
            setCompareActiveModelsForCluster(block.clusterId, [modelKey])
            setCompareContinuationModeForCluster(block.clusterId, "winner")
            setClusterCollapsed(true)
            notification.success({
              message: t(
                "playground:composer.compareContinueContract",
                "Next turns continue with {{model}} only. Re-enable Compare to send to multiple models again.",
                { model: getModelLabel(modelKey) } as any
              )
            })
          }
          const handleCompareAgain = () => {
            if (!compareFeatureEnabled) {
              return
            }
            const maxModels =
              typeof compareMaxModels === "number" && compareMaxModels > 0
                ? compareMaxModels
                : clusterModelKeys.length
            setCompareSelectedModels(clusterModelKeys.slice(0, maxModels))
            setCompareMode(true)
            setCompareContinuationModeForCluster(block.clusterId, "compare")
            setClusterCollapsed(false)
            notification.info({
              message: t(
                "playground:composer.compareResumeContract",
                "Compare mode resumed. Next turn will fan out to selected models."
              )
            })
          }

          const handleBulkSplit = async () => {
            if (!compareFeatureEnabled) {
              return
            }
            const createdIds: string[] = []
            const failedModels: string[] = []
            for (const modelKey of clusterSelection) {
              try {
                const newHistoryId = await createCompareBranch({
                  clusterId: block.clusterId,
                  modelId: modelKey,
                  open: false
                })
                if (newHistoryId && historyId) {
                  setCompareParentForHistory(newHistoryId, {
                    parentHistoryId: historyId,
                    clusterId: block.clusterId
                  })
                  setCompareSplitChat(block.clusterId, modelKey, newHistoryId)
                  createdIds.push(newHistoryId)
                } else {
                  failedModels.push(modelKey)
                }
              } catch (error) {
                console.error(`Failed to create branch for ${modelKey}:`, error)
                failedModels.push(modelKey)
              }
            }
            if (createdIds.length > 0) {
              void trackCompareMetric({
                type: "split_bulk",
                count: createdIds.length
              })
              notification.success({
                message: t(
                  "playground:composer.compareBulkSplitSuccess",
                  "Created {{count}} chats",
                  { count: createdIds.length }
                )
              })
            }
            if (failedModels.length > 0) {
              notification.warning({
                message: t(
                  "playground:composer.compareBulkSplitPartialFail",
                  "Failed to create {{count}} chats",
                  { count: failedModels.length }
                )
              })
            }
          }

          return (
            <div
              key={`c-${blockIndex}`}
              className="w-full max-w-5xl md:px-4 mb-4 space-y-2">
              <PlaygroundMessage
                isBot={userMessage.isBot}
                message={userMessage.message}
                name={userMessage.name}
                role={userMessage.role}
                images={userMessage.images || []}
                currentMessageIndex={block.userIndex}
                totalMessages={messages.length}
                onRegenerate={regenerateLastMessage}
                onRegenerateImage={(payload) => {
                  void handleRegenerateGeneratedImage(payload)
                }}
                onDeleteImage={handleDeleteGeneratedImage}
                onSelectImageVariant={handleSelectGeneratedImageVariant}
                onKeepImageVariant={handleKeepGeneratedImageVariant}
                onDeleteImageVariant={handleDeleteGeneratedImageVariant}
                onDeleteAllImageVariants={handleDeleteAllGeneratedImageVariants}
                isProcessing={isProcessing}
                isSearchingInternet={isSearchingInternet}
                sources={userMessage.sources}
                onEditFormSubmit={(value, isSend) => {
                  editMessage(
                    block.userIndex,
                    value,
                    !userMessage.isBot,
                    isSend
                  )
                }}
                onDeleteMessage={() => {
                  deleteMessage(block.userIndex)
                }}
                onTogglePinned={() => {
                  void toggleMessagePinned(block.userIndex)
                }}
                onNewBranch={() => {
                  createChatBranch(block.userIndex)
                }}
                isTTSEnabled={ttsEnabled}
                generationInfo={userMessage?.generationInfo}
                toolCalls={userMessage?.toolCalls}
                toolResults={userMessage?.toolResults}
                isStreaming={streaming}
                reasoningTimeTaken={userMessage?.reasoning_time_taken}
                openReasoning={openReasoning}
                modelImage={userMessage?.modelImage}
                modelName={userMessage?.modelName}
                createdAt={userMessage?.createdAt}
                temporaryChat={temporaryChat}
                onStopStreaming={stopStreamingRequest}
                onContinue={runContinue}
                onRunSteeredContinue={runSteeredContinue}
                documents={userMessage?.documents}
                actionInfo={actionInfo}
                serverChatId={serverChatId}
                serverMessageId={userMessage.serverMessageId}
                messageId={userMessage.id}
                pinned={Boolean(userMessage.pinned)}
                metadataExtra={userMessage.metadataExtra}
                onUseInChat={buildMessageUseInChatHandler(userMessage.metadataExtra)}
                discoSkillComment={userMessage.discoSkillComment}
                historyId={stableHistoryId ?? undefined}
                conversationInstanceId={conversationInstanceId}
                feedbackQuery={previousUserMessage?.message ?? null}
                isEmbedding={isEmbedding}
                characterIdentity={selectedCharacter}
                characterIdentityEnabled={characterIdentityEnabled}
                speakerCharacterId={userMessage.speakerCharacterId ?? null}
                speakerCharacterName={userMessage.speakerCharacterName}
                moodLabel={userMessage.moodLabel ?? null}
                moodConfidence={userMessage.moodConfidence ?? null}
                moodTopic={userMessage.moodTopic ?? null}
                searchQuery={normalizedSearchQuery || undefined}
                searchMatch={resolveSearchMatch(block.userIndex)}
                message_type={resolveMessageType(userMessage, block.userIndex)}
                variants={userMessage.variants}
                activeVariantIndex={userMessage.activeVariantIndex}
                onSwipePrev={() => handleVariantSwipe(userMessage.id, "prev")}
                onSwipeNext={() => handleVariantSwipe(userMessage.id, "next")}
                messageSteeringMode={messageSteeringMode}
                onMessageSteeringModeChange={setMessageSteeringMode}
                messageSteeringForceNarrate={messageSteeringForceNarrate}
                onMessageSteeringForceNarrateChange={setMessageSteeringForceNarrate}
                onClearMessageSteering={clearMessageSteering}
              />
              <div className="ml-10 space-y-2 border-l border-dashed border-border pl-4">
                <div className="mb-1 flex items-center justify-between text-[11px] text-text-muted">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-surface2 px-2 py-0.5 text-[10px] font-medium text-text">
                      {t(
                        "playground:composer.compareClusterLabel",
                        "Multi-model answers"
                      )}
                    </span>
                    <span className="text-[10px] text-text-subtle">
                      {t(
                        "playground:composer.compareClusterCount",
                        "{{count}} models",
                        { count: replyItems.length }
                      )}
                    </span>
                  </div>
                  {isChosenState && alternativeCount > 0 && (
                    <button
                      type="button"
                      onClick={() => setClusterCollapsed(!isCollapsed)}
                      title={
                        isCollapsed
                          ? (t(
                              "common:timeline.expandAllAlternatives",
                              "Expand all alternatives"
                            ) as string)
                          : (t(
                              "common:timeline.collapseAllAlternatives",
                              "Collapse all alternatives"
                            ) as string)
                      }
                      className="text-[10px] font-medium text-primary hover:underline">
                      {isCollapsed
                        ? t(
                            "common:timeline.expandAllAlternatives",
                            "Expand all alternatives"
                          )
                        : t(
                            "common:timeline.collapseAllAlternatives",
                            "Collapse all alternatives"
                        )}{" "}
                      ({alternativeCount})
                    </button>
                  )}
                </div>
                {clusterModelKeys.length > 1 && (
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
                    <span className="text-[10px] font-semibold uppercase tracking-wide">
                      {t(
                        "playground:composer.compareFilterLabel",
                        "Filter models"
                      )}
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {clusterModelKeys.map((modelKey) => {
                        const isHidden = hiddenModels.includes(modelKey)
                        const providerKey = getModelProvider(modelKey)
                        return (
                          <button
                            key={`filter-${block.clusterId}-${modelKey}`}
                            type="button"
                            onClick={() => toggleModelFilter(modelKey)}
                            title={getModelLabel(modelKey)}
                            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition ${
                              isHidden
                                ? "border-border bg-surface text-text-subtle"
                                : "border-primary bg-surface2 text-primaryStrong"
                            }`}
                          >
                            <ProviderIcons
                              provider={providerKey}
                              className="h-3 w-3"
                            />
                            <span className="max-w-[120px] truncate">
                              {getModelLabel(modelKey)}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                    {hiddenModels.length > 0 && (
                      <button
                        type="button"
                        onClick={clearModelFilter}
                        title={t(
                          "playground:composer.compareFilterClear",
                          "Show all"
                        ) as string}
                        className="text-[10px] font-medium text-primary hover:underline"
                      >
                        {t(
                          "playground:composer.compareFilterClear",
                          "Show all"
                        )}
                      </button>
                    )}
                    <span className="text-[10px] text-text-subtle">
                      {t(
                        "playground:composer.compareFilterCount",
                        "Showing {{visible}} / {{total}}",
                        {
                          visible: filteredReplyItems.length,
                          total: replyItems.length
                        }
                      )}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setNormalizedPreview(!normalizedPreviewEnabled)
                      }
                      title={
                        normalizedPreviewEnabled
                          ? (t(
                              "playground:composer.comparePreviewFullTitle",
                              "Switch to full responses"
                            ) as string)
                          : (t(
                              "playground:composer.comparePreviewNormalizedTitle",
                              "Switch to normalized previews"
                            ) as string)
                      }
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium transition ${
                        normalizedPreviewEnabled
                          ? "border-primary bg-primary/10 text-primaryStrong"
                          : "border-border bg-surface text-text-muted hover:bg-surface2 hover:text-text"
                      }`}
                    >
                      {normalizedPreviewEnabled
                        ? t(
                            "playground:composer.comparePreviewFull",
                            "Full responses"
                          )
                        : t(
                            "playground:composer.comparePreviewNormalized",
                            "Normalized previews"
                          )}
                    </button>
                    <button
                      type="button"
                      data-testid={`compare-diff-toggle-${block.clusterId}`}
                      onClick={() => setDiffPreview(!diffPreviewEnabled)}
                      title={
                        diffPreviewEnabled
                          ? (t(
                              "playground:composer.compareDiffHideTitle",
                              "Hide response differences"
                            ) as string)
                          : (t(
                              "playground:composer.compareDiffShowTitle",
                              "Show response differences"
                            ) as string)
                      }
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium transition ${
                        diffPreviewEnabled
                          ? "border-primary bg-primary/10 text-primaryStrong"
                          : "border-border bg-surface text-text-muted hover:bg-surface2 hover:text-text"
                      }`}
                    >
                      {diffPreviewEnabled
                        ? t(
                            "playground:composer.compareDiffHide",
                            "Hide differences"
                          )
                        : t(
                            "playground:composer.compareDiffShow",
                            "Diff highlights"
                          )}
                    </button>
                  </div>
                )}
                {compareFeatureEnabled && clusterSelection.length > 1 && (
                  <div className="mb-2 flex items-center justify-between text-[11px] text-text-muted">
                    <span>
                      {t(
                        "playground:composer.compareBulkSplitHint",
                        "Selected models: {{count}}",
                        { count: clusterSelection.length }
                      )}
                    </span>
                    <button
                      type="button"
                      onClick={handleBulkSplit}
                      disabled={!compareFeatureEnabled}
                      title={t(
                        "playground:composer.compareBulkSplit",
                        "Open each selected answer as its own chat"
                      ) as string}
                      className={`rounded border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-text hover:bg-surface2 ${
                        !compareFeatureEnabled
                          ? "cursor-not-allowed opacity-50"
                          : ""
                      }`}>
                      {t(
                        "playground:composer.compareBulkSplit",
                        "Open each selected answer as its own chat"
                      )}
                    </button>
                  </div>
                )}
                {visibleReplyItems.map(({ index, message, modelKey }) => {
                  const isSelected = clusterSelection.includes(modelKey)
                  const errorPayload = decodeChatErrorPayload(message.message)
                  const hasError = Boolean(errorPayload)
                  const isSelectable = compareFeatureEnabled && !hasError
                  const isChosenCard =
                    isChosenState && selectedModelKey === modelKey
                  const latencyLabel =
                    typeof message?.reasoning_time_taken === "number" &&
                    message.reasoning_time_taken > 0
                      ? humanizeMilliseconds(message.reasoning_time_taken)
                      : null
                  const providerKey = getModelProvider(modelKey)
                  const providerLabel = tldwModels.getProviderDisplayName(
                    providerKey
                  )
                  const tokenCount = getTokenCount(message?.generationInfo)
                  const tokenLabel =
                    tokenCount !== null
                      ? t(
                          "playground:composer.compareTokens",
                          "Tokens: {{count}}",
                          { count: tokenCount }
                        )
                      : null
                  const costUsd = resolveMessageCostUsd(message?.generationInfo)
                  const costLabel = costUsd != null ? formatCost(costUsd) : null
                  const splitMap = compareSplitChats[block.clusterId] || {}
                  const spawnedHistoryId = splitMap[modelKey]
                  const normalizedPreviewBudget =
                    normalizedPreviewEnabled
                      ? computeNormalizedPreviewBudget(
                          filteredReplyItems.map((item) =>
                            typeof item.message?.message === "string"
                              ? item.message.message
                              : ""
                          )
                        )
                      : 0
                  const normalizedPreviewText = normalizedPreviewEnabled
                    ? buildNormalizedPreview(
                        typeof message?.message === "string"
                          ? message.message
                          : "",
                        normalizedPreviewBudget
                      )
                    : ""
                  const isDiffBaselineCard =
                    Boolean(diffBaselineModelKey) &&
                    modelKey === diffBaselineModelKey
                  const diffPreview =
                    diffPreviewEnabled && diffBaselineItem
                      ? computeResponseDiffPreview({
                          baseline: diffBaselineText,
                          candidate:
                            typeof message?.message === "string"
                              ? message.message
                              : "",
                          maxHighlights: 2
                        })
                      : null

                  const handleToggle = () => {
                    if (!isSelectable) {
                      return
                    }
                    const next = isSelected
                      ? clusterSelection.filter((id) => id !== modelKey)
                      : [...clusterSelection, modelKey]

                    if (
                      !isSelected &&
                      compareMaxModels &&
                      clusterSelection.length >= compareMaxModels
                    ) {
                      notification.warning({
                        message: t(
                          "playground:composer.compareMaxModelsTitle",
                          "Compare limit reached"
                        ),
                        description: t(
                          "playground:composer.compareMaxModels",
                          "You can compare up to {{limit}} models per turn.",
                          { count: compareMaxModels, limit: compareMaxModels }
                        )
                      })
                      return
                    }
                    setCompareSelectionForCluster(block.clusterId, next)
                    setCompareActiveModelsForCluster(block.clusterId, next)
                    setCompareSelectedModels(next)
                    if (next.length > 1) {
                      setCompareContinuationModeForCluster(
                        block.clusterId,
                        "compare"
                      )
                    } else if (next.length === 1) {
                      setCompareContinuationModeForCluster(
                        block.clusterId,
                        "winner"
                      )
                    }
                    void trackCompareMetric({
                      type: "selection",
                      count: next.length
                    })
                  }

                  const displayName = message?.modelName || message.name

                  const clusterMessagesForModel = messages
                    .map((m: any, idx) => ({ m, idx }))
                    .filter(
                      ({ m }) =>
                        m.clusterId === block.clusterId &&
                        (m.messageType === "compare:user" ||
                          ((m as any).modelId || m.modelName || m.name) ===
                            modelKey)
                    )

                  const threadPreviewItems = clusterMessagesForModel.slice(-4)

                  const handleOpenFullChat = async () => {
                    if (!compareFeatureEnabled) {
                      return
                    }
                    const newHistoryId = await createCompareBranch({
                      clusterId: block.clusterId,
                      modelId: modelKey
                    })
                    if (newHistoryId && historyId) {
                      setCompareParentForHistory(newHistoryId, {
                        parentHistoryId: historyId,
                        clusterId: block.clusterId
                      })
                      setCompareSplitChat(
                        block.clusterId,
                        modelKey,
                        newHistoryId
                      )
                    }
                    if (modelKey) {
                      setCompareMode(false)
                      setSelectedModel(modelKey)
                      setCompareSelectedModels([modelKey])
                    }
                  }

                  const placeholder = t(
                    "playground:composer.perModelReplyPlaceholder",
                    "Reply only to {{model}}",
                    { model: displayName }
                  )
                  const perModelDisabledReason = !compareFeatureEnabled
                    ? t(
                        "playground:composer.compareDisabled",
                        "Compare mode is disabled in settings."
                      )
                    : null
                  const perModelDisabled =
                    isProcessing || streaming || Boolean(perModelDisabledReason)

                  const handlePerModelSend = async (text: string) => {
                    await sendPerModelReply({
                      clusterId: block.clusterId,
                      modelId: modelKey,
                      message: text
                    })
                  }
                  const previousUserMessage = getPreviousUserMessage(index)

                  return (
                    <div
                      key={`c-${blockIndex}-${index}`}
                      role="article"
                      aria-label={t(
                        "playground:composer.compareCardAria",
                        "{{model}} response from {{provider}}",
                        {
                          model: getModelLabel(modelKey),
                          provider:
                            providerLabel ||
                            t(
                              "playground:composer.compareProviderCustom",
                              "Custom provider"
                            )
                        } as any
                      )}
                      className={`rounded-md border border-border bg-surface p-2 shadow-sm ${
                        isChosenCard
                          ? "ring-1 ring-success"
                          : ""
                      }`}>
                      <div
                        data-testid={`compare-model-identity-${block.clusterId}-${modelKey}`}
                        className="mb-2 flex items-center justify-between gap-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px]"
                      >
                        <div className="flex min-w-0 items-center gap-1.5">
                          <ProviderIcons
                            provider={providerKey}
                            className="h-3.5 w-3.5 flex-shrink-0 text-text-subtle"
                          />
                          <span className="truncate font-semibold text-text">
                            {getModelLabel(modelKey)}
                          </span>
                          <span className="truncate text-[10px] text-text-subtle">
                            {providerLabel ||
                              t(
                                "playground:composer.compareProviderCustom",
                                "Custom provider"
                              )}
                          </span>
                        </div>
                        <span className="rounded-full border border-border bg-surface px-1.5 py-0.5 text-[9px] font-medium text-text-muted">
                          {t(
                            "playground:composer.compareModelIdentityTag",
                            "Model"
                          )}
                        </span>
                      </div>
                      {normalizedPreviewEnabled && (
                        <div
                          data-testid={`compare-normalized-preview-${block.clusterId}-${modelKey}`}
                          className="mb-2 rounded-md border border-primary/30 bg-primary/5 px-2 py-1.5 text-[11px] text-primaryStrong"
                        >
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wide">
                              {t(
                                "playground:composer.comparePreviewLabel",
                                "Normalized preview"
                              )}
                            </span>
                            <span className="text-[10px] text-primaryStrong/80">
                              {t(
                                "playground:composer.comparePreviewBudget",
                                "~{{count}} chars",
                                { count: normalizedPreviewBudget } as any
                              )}
                            </span>
                          </div>
                          <p className="whitespace-pre-wrap">
                            {normalizedPreviewText ||
                              t(
                                "playground:composer.comparePreviewEmpty",
                                "No preview text available."
                              )}
                          </p>
                        </div>
                      )}
                      {diffPreview && (
                        <div
                          data-testid={`compare-diff-preview-${block.clusterId}-${modelKey}`}
                          className="mb-2 rounded-md border border-accent/35 bg-accent/5 px-2 py-1.5 text-[11px] text-text"
                        >
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wide text-text">
                              {isDiffBaselineCard
                                ? t(
                                    "playground:composer.compareDiffBaselineLabel",
                                    "Diff baseline"
                                  )
                                : t(
                                    "playground:composer.compareDiffVsLabel",
                                    "Diff vs {{model}}",
                                    {
                                      model: getModelLabel(
                                        diffBaselineModelKey || modelKey
                                      )
                                    } as any
                                  )}
                            </span>
                            <span className="text-[10px] text-text-subtle">
                              {t(
                                "playground:composer.compareDiffOverlap",
                                "{{percent}}% overlap",
                                {
                                  percent: Math.round(diffPreview.overlapRatio * 100)
                                } as any
                              )}
                            </span>
                          </div>
                          {isDiffBaselineCard ? (
                            <p className="text-[10px] text-text-subtle">
                              {t(
                                "playground:composer.compareDiffBaselineHint",
                                "Other responses are compared against this card."
                              )}
                            </p>
                          ) : diffPreview.hasMeaningfulDifference ? (
                            <div className="space-y-1">
                              {diffPreview.addedHighlights.length > 0 && (
                                <div className="rounded border border-success/30 bg-success/10 px-2 py-1">
                                  <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-success">
                                    {t(
                                      "playground:composer.compareDiffAddedLabel",
                                      "Added"
                                    )}
                                  </div>
                                  {diffPreview.addedHighlights.map((entry) => (
                                    <p
                                      key={`diff-add-${block.clusterId}-${modelKey}-${entry}`}
                                      className="line-clamp-2 text-[11px] text-success"
                                    >
                                      + {entry}
                                    </p>
                                  ))}
                                </div>
                              )}
                              {diffPreview.removedHighlights.length > 0 && (
                                <div className="rounded border border-warn/30 bg-warn/10 px-2 py-1">
                                  <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-warn">
                                    {t(
                                      "playground:composer.compareDiffRemovedLabel",
                                      "Removed"
                                    )}
                                  </div>
                                  {diffPreview.removedHighlights.map((entry) => (
                                    <p
                                      key={`diff-remove-${block.clusterId}-${modelKey}-${entry}`}
                                      className="line-clamp-2 text-[11px] text-warn"
                                    >
                                      - {entry}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="text-[10px] text-text-subtle">
                              {t(
                                "playground:composer.compareDiffNoChanges",
                                "No meaningful differences in previewed segments."
                              )}
                            </p>
                          )}
                        </div>
                      )}
                      <PlaygroundMessage
                        isBot={message.isBot}
                        message={message.message}
                        name={message.name}
                        role={message.role}
                        images={message.images || []}
                        currentMessageIndex={index}
                        totalMessages={messages.length}
                        onRegenerate={regenerateLastMessage}
                        onRegenerateImage={(payload) => {
                          void handleRegenerateGeneratedImage(payload)
                        }}
                        onDeleteImage={handleDeleteGeneratedImage}
                        onSelectImageVariant={handleSelectGeneratedImageVariant}
                        onKeepImageVariant={handleKeepGeneratedImageVariant}
                        onDeleteImageVariant={handleDeleteGeneratedImageVariant}
                        onDeleteAllImageVariants={handleDeleteAllGeneratedImageVariants}
                        isProcessing={isProcessing}
                        isSearchingInternet={isSearchingInternet}
                        sources={message.sources}
                        onEditFormSubmit={(value, isSend) => {
                          editMessage(index, value, !message.isBot, isSend)
                        }}
                        onDeleteMessage={() => {
                          deleteMessage(index)
                        }}
                        onTogglePinned={() => {
                          void toggleMessagePinned(index)
                        }}
                        onNewBranch={() => {
                          createChatBranch(index)
                        }}
                        isTTSEnabled={ttsEnabled}
                        generationInfo={message?.generationInfo}
                        toolCalls={message?.toolCalls}
                        toolResults={message?.toolResults}
                        isStreaming={streaming}
                        reasoningTimeTaken={message?.reasoning_time_taken}
                        openReasoning={openReasoning}
                        modelImage={message?.modelImage}
                        modelName={message?.modelName}
                        createdAt={message?.createdAt}
                        temporaryChat={temporaryChat}
                        onStopStreaming={stopStreamingRequest}
                        onContinue={runContinue}
                        onRunSteeredContinue={runSteeredContinue}
                        documents={message?.documents}
                        actionInfo={actionInfo}
                        serverChatId={serverChatId}
                        serverMessageId={message.serverMessageId}
                        messageId={message.id}
                        pinned={Boolean(message.pinned)}
                        metadataExtra={message.metadataExtra}
                        onUseInChat={buildMessageUseInChatHandler(message.metadataExtra)}
                        discoSkillComment={message.discoSkillComment}
                        historyId={stableHistoryId ?? undefined}
                        conversationInstanceId={conversationInstanceId}
                        feedbackQuery={previousUserMessage?.message ?? null}
                        isEmbedding={isEmbedding}
                        characterIdentity={selectedCharacter}
                        characterIdentityEnabled={characterIdentityEnabled}
                        speakerCharacterId={message.speakerCharacterId ?? null}
                        speakerCharacterName={message.speakerCharacterName}
                        moodLabel={message.moodLabel ?? null}
                        moodConfidence={message.moodConfidence ?? null}
                        moodTopic={message.moodTopic ?? null}
                        searchQuery={normalizedSearchQuery || undefined}
                        searchMatch={resolveSearchMatch(index)}
                        message_type={resolveMessageType(message, index)}
                        compareSelectable={isSelectable}
                        compareSelected={isSelected}
                        onToggleCompareSelect={handleToggle}
                        compareError={hasError}
                        compareErrorModelLabel={hasError ? getModelLabel(modelKey) : undefined}
                        compareChosen={isChosenCard}
                        variants={message.variants}
                        activeVariantIndex={message.activeVariantIndex}
                        onSwipePrev={() => handleVariantSwipe(message.id, "prev")}
                        onSwipeNext={() => handleVariantSwipe(message.id, "next")}
                        messageSteeringMode={messageSteeringMode}
                        onMessageSteeringModeChange={setMessageSteeringMode}
                        messageSteeringForceNarrate={messageSteeringForceNarrate}
                        onMessageSteeringForceNarrateChange={setMessageSteeringForceNarrate}
                        onClearMessageSteering={clearMessageSteering}
                      />

                      {threadPreviewItems.length > 1 && (
                        <div className="mt-2 space-y-1 rounded-md bg-surface2 p-2 text-[11px] text-text">
                          <div className="mb-0.5 text-[11px] font-medium tracking-wide text-text-subtle">
                            {t(
                              "playground:composer.compareThreadLabel",
                              "Per-model thread"
                            )}
                          </div>
                          {threadPreviewItems.map(({ m, idx: threadIndex }) => (
                            <div
                              key={`thread-${block.clusterId}-${modelKey}-${threadIndex}`}
                              className="flex gap-1">
                              <span className="font-semibold">
                                {m.isBot
                                  ? m.modelName || m.name
                                  : m.messageType === "compare:user"
                                    ? t(
                                        "playground:composer.compareThreadShared",
                                        "You (shared)"
                                      )
                                    : t(
                                        "playground:composer.compareThreadYou",
                                        "You"
                                      )}
                                :
                              </span>
                              <span className="line-clamp-2">
                                {m.message}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      <PerModelMiniComposer
                        placeholder={placeholder}
                        disabled={perModelDisabled}
                        helperText={perModelDisabledReason}
                        onSend={handlePerModelSend}
                      />

                      <div className="mt-1 flex items-center justify-between text-[11px] text-text-muted">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={handleOpenFullChat}
                            disabled={!compareFeatureEnabled}
                            title={t(
                              "playground:composer.compareOpenFullChat",
                              "Open as full chat"
                            ) as string}
                            className={`text-primary hover:underline ${
                              !compareFeatureEnabled
                                ? "cursor-not-allowed opacity-50 no-underline"
                                : ""
                            }`}>
                            {t(
                              "playground:composer.compareOpenFullChat",
                              "Open as full chat"
                            )}
                          </button>
                          {tokenLabel && (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] text-text-subtle"
                              aria-label={tokenLabel}
                            >
                              <Hash className="h-3 w-3" aria-hidden="true" />
                              {tokenLabel}
                            </span>
                          )}
                          {costLabel && (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] text-text-subtle"
                              aria-label={t(
                                "playground:composer.compareCost",
                                "Cost: {{cost}}",
                                { cost: costLabel } as any
                              )}
                            >
                              <DollarSign className="h-3 w-3" aria-hidden="true" />
                              {costLabel}
                            </span>
                          )}
                          {latencyLabel && (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] text-text-subtle"
                              aria-label={t(
                                "playground:composer.compareLatency",
                                "Latency"
                              )}>
                              <Clock className="h-3 w-3" aria-hidden="true" />
                              {latencyLabel}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {spawnedHistoryId && (
                            <button
                              type="button"
                              onClick={() => {
                                window.dispatchEvent(
                                  new CustomEvent("tldw:open-history", {
                                    detail: { historyId: spawnedHistoryId }
                                  })
                                )
                              }}
                              title={t(
                                "playground:composer.compareSpawnedChat",
                                "Open split chat"
                              ) as string}
                              className="text-[10px] text-text-muted hover:text-text underline">
                              {t(
                                "playground:composer.compareSpawnedChat",
                                "Open split chat"
                              )}
                            </button>
                          )}
                          {message.id && (
                            <button
                              type="button"
                              onClick={() => {
                                const currentCanonical =
                                  compareCanonicalByCluster[block.clusterId] || null
                                const next =
                                  currentCanonical === message.id ? null : message.id
                                setCompareCanonicalForCluster(block.clusterId, next)
                              }}
                              title={
                                compareCanonicalByCluster[block.clusterId] === message.id
                                  ? (t(
                                      "playground:composer.compareCanonicalOn",
                                      "Chosen"
                                    ) as string)
                                  : (t(
                                      "playground:composer.compareCanonicalOff",
                                      "Choose as answer"
                                    ) as string)
                              }
                              className={`rounded px-2 py-0.5 text-[10px] font-medium border transition ${
                                compareCanonicalByCluster[block.clusterId] ===
                                message.id
                                  ? "border-success bg-success text-white"
                                  : "border-success/40 bg-success/10 text-success"
                              }`}>
                              {compareCanonicalByCluster[block.clusterId] ===
                              message.id
                                ? t(
                                    "playground:composer.compareCanonicalOn",
                                    "Chosen"
                                  )
                                : t(
                                    "playground:composer.compareCanonicalOff",
                                    "Choose as answer"
                                  )}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}

                {clusterSelection.length > 0 && (
                  <div className="mt-2 rounded-md border border-border bg-surface2 px-3 py-2 text-[11px] text-text-muted">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">
                        {t(
                          "playground:composer.compareSelectedLabel",
                          "Chosen answer:"
                        )}
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {clusterSelection.map((modelKey) => (
                          <span
                            key={`selected-${block.clusterId}-${modelKey}`}
                            className="rounded-full bg-surface px-2 py-0.5 text-[10px] font-medium text-text shadow-sm">
                            {getModelLabel(modelKey)}
                          </span>
                        ))}
                      </div>
                    </div>
                    {clusterActiveModels.length === 1 ? (
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="text-[10px] text-text-muted">
                          {compareModeActive
                            ? t(
                                "playground:composer.compareContinueHint",
                                "Continue this chat with the selected model."
                              )
                            : t(
                                "playground:composer.compareChosenHint",
                                "Continue with the selected answer or keep comparing."
                              )}
                        </span>
                        {compareModeActive ? (
                          <button
                            type="button"
                            onClick={() =>
                              handleContinueWithModel(clusterActiveModels[0])
                            }
                            title={t(
                              "playground:composer.compareContinueWinner",
                              "Continue with winner"
                            ) as string}
                            className="rounded border border-primary bg-primary px-2 py-0.5 text-[10px] font-medium text-white hover:bg-primaryStrong">
                            {t(
                              "playground:composer.compareContinueWinner",
                              "Continue with winner"
                            )}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={handleCompareAgain}
                            disabled={!compareFeatureEnabled}
                            title={t(
                              "playground:composer.compareKeepComparing",
                              "Keep comparing"
                            ) as string}
                            className={`rounded border border-primary px-2 py-0.5 text-[10px] font-medium ${
                              compareFeatureEnabled
                                ? "border-primary bg-surface text-primary hover:bg-surface2"
                                : "border-primary/40 bg-surface text-text-subtle cursor-not-allowed opacity-60"
                            }`}>
                            {t(
                              "playground:composer.compareKeepComparing",
                              "Keep comparing"
                            )}
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="mt-2 text-[10px] text-text-muted">
                        {t(
                          "playground:composer.compareActiveModelsHint",
                          "Your next message will be sent to each active model."
                        )}
                      </div>
                    )}
                    <div className="mt-2 flex items-center gap-2 text-[10px] text-text-subtle">
                      <span className="font-medium">
                        {t(
                          "playground:composer.compareContinuationLabel",
                          "Continuation mode:"
                        )}
                      </span>
                      <span className="rounded-full border border-border bg-surface px-2 py-0.5">
                        {continuationMode === "compare"
                          ? t(
                              "playground:composer.compareContinuationCompare",
                              "Keep comparing"
                            )
                          : t(
                              "playground:composer.compareContinuationWinner",
                              "Winner only"
                            )}
                      </span>
                    </div>
                  </div>
                )}

                {(() => {
                  const canonicalId =
                    compareCanonicalByCluster[block.clusterId] || null
                  if (!canonicalId) {
                    return null
                  }
                  const canonical = (messages as any[]).find(
                    (m) => m.id && m.id === canonicalId
                  )
                  if (!canonical) {
                    return null
                  }
                  return (
                    <div className="mt-3 rounded-md border border-success bg-success/10 px-3 py-2 text-[13px] text-success">
                      <div className="mb-1 flex items-center gap-2 text-[11px] font-medium">
                        <span className="uppercase tracking-wide">
                          {t(
                            "playground:composer.compareCanonicalLabel",
                            "Chosen answer"
                          )}
                        </span>
                        <span className="text-success/80">
                          {canonical.modelName || canonical.name}
                        </span>
                      </div>
                      <div className="whitespace-pre-wrap">
                        {canonical.message}
                      </div>
                    </div>
                  )
                })()}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
