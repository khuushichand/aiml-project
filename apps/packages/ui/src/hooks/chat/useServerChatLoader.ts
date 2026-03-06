import React from "react"
import { shallow } from "zustand/shallow"
import type { TFunction } from "i18next"
import { useChatBaseState } from "@/hooks/chat/useChatBaseState"
import { useStoreMessageOption } from "@/store/option"
import type { Message } from "@/store/option"
import {
  tldwClient,
  type ServerChatMessage
} from "@/services/tldw/TldwApiClient"
import { getHistoriesWithMetadata, saveMessage } from "@/db/dexie/helpers"
import { syncChatSettingsForServerChat } from "@/services/chat-settings"
import { normalizeConversationState } from "@/utils/conversation-state"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import { updatePageTitle } from "@/utils/update-page-title"
import {
  IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE,
  parseImageGenerationEventMirrorContent
} from "@/utils/image-generation-chat"

type NotificationApi = {
  error: (payload: { message: string; description?: string }) => void
}

type UseServerChatLoaderOptions = {
  ensureServerChatHistoryId: (
    chatId: string,
    title?: string
  ) => Promise<string | null>
  notification: NotificationApi
  t: TFunction
}

type PreserveLocalMessagesArgs = {
  currentMessages: Message[]
  serverMessages: Message[]
  isStreaming: boolean
  isProcessing: boolean
}

type ShouldSkipLoadedServerChatReloadArgs = {
  activeServerChatId: string | null
  loadedChatId: string | null
  loaded: boolean
  currentMessages: Message[]
}

type FetchServerChatMessagesPageArgs = {
  limit: number
  offset: number
  signal?: AbortSignal
}

type FetchServerChatMessagesPage = (
  params: FetchServerChatMessagesPageArgs
) => Promise<ServerChatMessage[]>

const SERVER_CHAT_MESSAGES_FETCH_LIMIT = 200
const SERVER_CHAT_MESSAGES_FETCH_MAX_PAGES = 100

const toServerMessageId = (message: Message): string | null => {
  if (typeof message.serverMessageId !== "string") return null
  const trimmed = message.serverMessageId.trim()
  return trimmed.length > 0 ? trimmed : null
}

const toServerMessageCreatedAtMs = (message: ServerChatMessage): number | null => {
  if (typeof message?.created_at !== "string") return null
  const parsed = Date.parse(message.created_at)
  return Number.isNaN(parsed) ? null : parsed
}

const isSyntheticGreetingPlaceholder = (message: Message): boolean => {
  const messageType = message.messageType
  if (messageType !== "character:greeting" && messageType !== "greeting") {
    return false
  }
  return (
    !toServerMessageId(message) &&
    Boolean(message.isBot || message.role === "assistant") &&
    typeof message.message === "string" &&
    message.message.trim().length > 0
  )
}

export const shouldPreserveLocalMessagesForServerLoad = ({
  currentMessages,
  serverMessages,
  isStreaming,
  isProcessing
}: PreserveLocalMessagesArgs): boolean => {
  if (isStreaming || isProcessing) return true
  if (!Array.isArray(currentMessages) || currentMessages.length === 0) return false

  const hasUnsyncedMessages = currentMessages.some(
    (message) =>
      !toServerMessageId(message) &&
      !isSyntheticGreetingPlaceholder(message) &&
      typeof message.message === "string" &&
      message.message.trim().length > 0
  )
  if (hasUnsyncedMessages) return true

  const serverMessageIds = new Set(
    serverMessages.map((message) => toServerMessageId(message)).filter(Boolean)
  )

  return currentMessages.some((message) => {
    const serverMessageId = toServerMessageId(message)
    return Boolean(serverMessageId) && !serverMessageIds.has(serverMessageId)
  })
}

export const shouldSkipLoadedServerChatReload = ({
  activeServerChatId,
  loadedChatId,
  loaded,
  currentMessages
}: ShouldSkipLoadedServerChatReloadArgs): boolean => {
  if (!activeServerChatId || !loaded) return false
  if (loadedChatId !== activeServerChatId) return false
  return Array.isArray(currentMessages) && currentMessages.length > 0
}

export const fetchAllServerChatMessages = async (
  fetchPage: FetchServerChatMessagesPage,
  options?: {
    limit?: number
    maxPages?: number
    signal?: AbortSignal
  }
): Promise<ServerChatMessage[]> => {
  const limit = Math.max(
    1,
    Math.min(200, options?.limit ?? SERVER_CHAT_MESSAGES_FETCH_LIMIT)
  )
  const maxPages = Math.max(
    1,
    options?.maxPages ?? SERVER_CHAT_MESSAGES_FETCH_MAX_PAGES
  )
  const messages: ServerChatMessage[] = []
  let offset = 0

  for (let page = 0; page < maxPages; page += 1) {
    const batch = await fetchPage({
      limit,
      offset,
      signal: options?.signal
    })
    if (!Array.isArray(batch) || batch.length === 0) {
      break
    }
    messages.push(...batch)
    offset += batch.length
    if (batch.length < limit) {
      break
    }
  }

  if (messages.length <= 1) {
    return messages
  }

  const deduped: ServerChatMessage[] = []
  const seenIds = new Set<string>()
  for (const message of messages) {
    const normalizedId = String(message?.id ?? "").trim()
    if (normalizedId.length > 0) {
      if (seenIds.has(normalizedId)) {
        continue
      }
      seenIds.add(normalizedId)
    }
    deduped.push(message)
  }

  return deduped
    .map((message, index) => ({
      index,
      message,
      createdAtMs: toServerMessageCreatedAtMs(message)
    }))
    .sort((left, right) => {
      const leftCreatedAt = left.createdAtMs
      const rightCreatedAt = right.createdAtMs
      if (leftCreatedAt != null && rightCreatedAt != null) {
        if (leftCreatedAt !== rightCreatedAt) {
          return leftCreatedAt - rightCreatedAt
        }
      } else if (leftCreatedAt != null) {
        return -1
      } else if (rightCreatedAt != null) {
        return 1
      }
      return left.index - right.index
    })
    .map((entry) => entry.message)
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

type MapServerMessagesArgs = {
  serverMessages: ServerChatMessage[]
  assistantName: string
  characterId: string | number | null
}

export const mapServerChatMessagesToPlaygroundMessages = ({
  serverMessages,
  assistantName,
  characterId
}: MapServerMessagesArgs): Message[] => {
  let encounteredUserMessage = false
  return serverMessages.map((m) => {
    const meta = m as unknown as Record<string, unknown>
    const createdAt = Date.parse(m.created_at)
    const metadataExtraCandidate =
      (m as unknown as { metadata_extra?: unknown }).metadata_extra ??
      (meta?.metadata_extra as unknown)
    const metadataExtra = isRecord(metadataExtraCandidate)
      ? metadataExtraCandidate
      : undefined
    const speakerCharacterIdRaw = metadataExtra?.speaker_character_id
    const speakerCharacterId =
      typeof speakerCharacterIdRaw === "number" &&
      Number.isFinite(speakerCharacterIdRaw)
        ? speakerCharacterIdRaw
        : typeof speakerCharacterIdRaw === "string" &&
            speakerCharacterIdRaw.trim().length > 0 &&
            Number.isFinite(Number(speakerCharacterIdRaw))
          ? Number(speakerCharacterIdRaw)
          : null
    const moodConfidenceRaw = metadataExtra?.mood_confidence
    const moodConfidence =
      typeof moodConfidenceRaw === "number" && Number.isFinite(moodConfidenceRaw)
        ? moodConfidenceRaw
        : typeof moodConfidenceRaw === "string" &&
            moodConfidenceRaw.trim().length > 0 &&
            Number.isFinite(Number(moodConfidenceRaw))
          ? Number(moodConfidenceRaw)
          : null
    const senderName =
      typeof (m as any).sender === "string" ? String((m as any).sender).trim() : ""
    const explicitMessageType =
      (meta?.message_type as string | undefined) ??
      (meta?.messageType as string | undefined)
    const inferredGreetingMessageType =
      !explicitMessageType &&
      characterId != null &&
      m.role === "assistant" &&
      !encounteredUserMessage
        ? "character:greeting"
        : undefined

    const mirroredImageEvent = parseImageGenerationEventMirrorContent(m.content)
    const normalizedMessageType = mirroredImageEvent
      ? IMAGE_GENERATION_ASSISTANT_MESSAGE_TYPE
      : explicitMessageType ?? inferredGreetingMessageType
    if (m.role === "user") {
      encounteredUserMessage = true
    }

    const mirroredImageDataUrl =
      typeof mirroredImageEvent?.imageDataUrl === "string" &&
      mirroredImageEvent.imageDataUrl.startsWith("data:image/")
        ? mirroredImageEvent.imageDataUrl
        : undefined
    const generationInfo = mirroredImageEvent
      ? {
          file_id: mirroredImageEvent.fileId,
          image_generation: {
            request: mirroredImageEvent.request,
            promptMode: mirroredImageEvent.promptMode,
            source: mirroredImageEvent.source,
            createdAt:
              mirroredImageEvent.createdAt ??
              (Number.isNaN(createdAt) ? Date.now() : createdAt),
            refine: mirroredImageEvent.refine,
            variant_count: mirroredImageEvent.variantCount,
            active_variant_index: mirroredImageEvent.activeVariantIndex,
            event_id: mirroredImageEvent.eventId,
            sync: {
              mode: "on",
              policy: "on",
              status: "synced",
              serverMessageId: String(m.id),
              mirroredAt: Number.isNaN(createdAt) ? Date.now() : createdAt,
              lastAttemptAt: Number.isNaN(createdAt) ? Date.now() : createdAt
            }
          }
        }
      : undefined

    return {
      createdAt: Number.isNaN(createdAt) ? undefined : createdAt,
      isBot: m.role === "assistant",
      role: normalizeChatRole(m.role),
      name:
        m.role === "assistant"
          ? senderName || assistantName
          : m.role === "system"
            ? "System"
            : "You",
      message: mirroredImageEvent ? "" : m.content,
      sources: [],
      images: mirroredImageDataUrl ? [mirroredImageDataUrl] : [],
      generationInfo,
      id: String(m.id),
      serverMessageId: String(m.id),
      serverMessageVersion: m.version,
      parentMessageId:
        (meta?.parent_message_id as string | null | undefined) ??
        (meta?.parentMessageId as string | null | undefined) ??
        null,
      messageType: normalizedMessageType,
      clusterId:
        (meta?.cluster_id as string | undefined) ??
        (meta?.clusterId as string | undefined),
      modelId:
        (meta?.model_id as string | undefined) ??
        (meta?.modelId as string | undefined),
      modelName:
        (meta?.model_name as string | undefined) ??
        (meta?.modelName as string | undefined) ??
        assistantName,
      modelImage:
        (meta?.model_image as string | undefined) ??
        (meta?.modelImage as string | undefined),
      metadataExtra,
      speakerCharacterId,
      speakerCharacterName:
        typeof metadataExtra?.speaker_character_name === "string"
          ? metadataExtra.speaker_character_name
          : undefined,
      moodLabel:
        typeof metadataExtra?.mood_label === "string"
          ? metadataExtra.mood_label
          : undefined,
      moodConfidence,
      moodTopic:
        typeof metadataExtra?.mood_topic === "string"
          ? metadataExtra.mood_topic
          : null,
      pinned: Boolean(
        (meta?.pinned as boolean | undefined) ??
          (metadataExtra?.pinned as boolean | undefined)
      )
    } satisfies Message
  })
}

export const useServerChatLoader = ({
  ensureServerChatHistoryId,
  notification,
  t
}: UseServerChatLoaderOptions) => {
  const {
    messages,
    streaming,
    isProcessing,
    setHistory,
    setMessages,
    setIsLoading
  } = useChatBaseState(useStoreMessageOption)
  const messagesRef = React.useRef(messages)
  const streamingRef = React.useRef(streaming)
  const processingRef = React.useRef(isProcessing)
  const {
    serverChatId,
    serverChatTitle,
    serverChatCharacterId,
    serverChatMetaLoaded,
    temporaryChat,
    setServerChatTitle,
    setServerChatCharacterId,
    setServerChatState,
    setServerChatVersion,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef,
    setServerChatMetaLoaded
  } = useStoreMessageOption(
    (state) => ({
      serverChatId: state.serverChatId,
      serverChatTitle: state.serverChatTitle,
      serverChatCharacterId: state.serverChatCharacterId,
      serverChatMetaLoaded: state.serverChatMetaLoaded,
      temporaryChat: state.temporaryChat,
      setServerChatTitle: state.setServerChatTitle,
      setServerChatCharacterId: state.setServerChatCharacterId,
      setServerChatState: state.setServerChatState,
      setServerChatVersion: state.setServerChatVersion,
      setServerChatTopic: state.setServerChatTopic,
      setServerChatClusterId: state.setServerChatClusterId,
      setServerChatSource: state.setServerChatSource,
      setServerChatExternalRef: state.setServerChatExternalRef,
      setServerChatMetaLoaded: state.setServerChatMetaLoaded
    }),
    shallow
  )

  const serverChatLoadRef = React.useRef<{
    chatId: string | null
    controller: AbortController | null
    inFlight: boolean
    loaded: boolean
  }>({ chatId: null, controller: null, inFlight: false, loaded: false })
  const serverChatDebounceRef = React.useRef<{
    chatId: string | null
    timer: ReturnType<typeof setTimeout> | null
  }>({ chatId: null, timer: null })

  messagesRef.current = messages
  streamingRef.current = streaming
  processingRef.current = isProcessing

  React.useEffect(() => {
    return () => {
      if (serverChatDebounceRef.current.timer) {
        clearTimeout(serverChatDebounceRef.current.timer)
      }
      if (serverChatLoadRef.current.controller) {
        serverChatLoadRef.current.controller.abort()
      }
    }
  }, [])

  React.useEffect(() => {
    if (!serverChatId) return
    if (
      shouldSkipLoadedServerChatReload({
        activeServerChatId: serverChatId,
        loadedChatId: serverChatLoadRef.current.chatId,
        loaded: serverChatLoadRef.current.loaded,
        currentMessages: messagesRef.current
      })
    ) {
      return
    }
    if (serverChatLoadRef.current.inFlight) {
      if (serverChatLoadRef.current.chatId === serverChatId) {
        return
      }
      if (serverChatLoadRef.current.controller) {
        serverChatLoadRef.current.controller.abort()
      }
      serverChatLoadRef.current.inFlight = false
    }

    if (serverChatDebounceRef.current.timer) {
      clearTimeout(serverChatDebounceRef.current.timer)
    }

    serverChatDebounceRef.current.chatId = serverChatId
    serverChatDebounceRef.current.timer = setTimeout(() => {
      const controller = new AbortController()
      serverChatLoadRef.current = {
        chatId: serverChatId,
        controller,
        inFlight: true,
        loaded: false
      }

      const loadServerChat = async () => {
        try {
          setIsLoading(true)
          await tldwClient.initialize().catch(() => null)

          let assistantName = "Assistant"
          let chatTitle = serverChatTitle || ""
          let characterId = serverChatCharacterId ?? null

          if (!serverChatMetaLoaded) {
            try {
              const chat = await tldwClient.getChat(serverChatId)
              const meta = chat as unknown as Record<string, unknown>
              chatTitle = String(meta?.title || chatTitle || "")
              const resolvedCharacterId =
                (meta?.character_id as string | number | null | undefined) ??
                (meta?.characterId as string | number | null | undefined) ??
                null
              if (resolvedCharacterId != null) {
                characterId = resolvedCharacterId
              }
              setServerChatTitle(chatTitle || "")
              setServerChatCharacterId(resolvedCharacterId ?? null)
              setServerChatState(
                normalizeConversationState(
                  (meta?.state as string | null | undefined) ??
                    (meta?.conversation_state as string | null | undefined)
                )
              )
              setServerChatVersion(
                typeof meta?.version === "number" ? meta.version : null
              )
              setServerChatTopic(
                typeof meta?.topic_label === "string"
                  ? meta.topic_label
                  : null
              )
              setServerChatClusterId(
                typeof meta?.cluster_id === "string" ? meta.cluster_id : null
              )
              setServerChatSource(
                typeof meta?.source === "string" ? meta.source : null
              )
              setServerChatExternalRef(
                typeof meta?.external_ref === "string"
                  ? meta.external_ref
                  : null
              )
              setServerChatMetaLoaded(true)
            } catch {
              // ignore metadata failures; still try to load messages
            }
          }

          if (characterId != null) {
            try {
              const character = await tldwClient.getCharacter(characterId)
              if (character) {
                assistantName = character.name || character.title || assistantName
              }
            } catch {
              // ignore character lookup failures
            }
          }

          const list = await fetchAllServerChatMessages(
            ({ limit, offset, signal }) =>
              tldwClient.listChatMessages(
                serverChatId,
                {
                  include_deleted: "false",
                  include_metadata: "true",
                  limit,
                  offset
                },
                { signal }
              ),
            {
              signal: controller.signal
            }
          )

          const mappedMessages = mapServerChatMessagesToPlaygroundMessages({
            serverMessages: list,
            assistantName,
            characterId
          })
          const history = mappedMessages.map((message) => ({
            role: message.role,
            content: message.message,
            messageType: message.messageType
          }))

          const currentMessages = messagesRef.current
          const shouldPreserveLocal = shouldPreserveLocalMessagesForServerLoad({
            currentMessages,
            serverMessages: mappedMessages,
            isStreaming: streamingRef.current,
            isProcessing: processingRef.current
          })

          const shouldPreserveAtCommit = shouldPreserveLocalMessagesForServerLoad({
            currentMessages: messagesRef.current,
            serverMessages: mappedMessages,
            isStreaming: streamingRef.current,
            isProcessing: processingRef.current
          })

          if (!shouldPreserveLocal && !shouldPreserveAtCommit) {
            setHistory(history)
            setMessages(mappedMessages)
          }
          if (!temporaryChat && !shouldPreserveLocal && !shouldPreserveAtCommit) {
            try {
              const localHistoryId = await ensureServerChatHistoryId(
                serverChatId,
                chatTitle || undefined
              )
              if (localHistoryId) {
                try {
                  await syncChatSettingsForServerChat({
                    historyId: localHistoryId,
                    serverChatId
                  })
                } catch {
                  // Best-effort settings sync.
                }
                const metadataMap = await getHistoriesWithMetadata([
                  localHistoryId
                ])
                const existingMeta = metadataMap.get(localHistoryId)
                if (!existingMeta || existingMeta.messageCount === 0) {
                  const now = Date.now()
                  await Promise.all(
                    mappedMessages.map((m, index) => {
                      const parsedCreatedAt =
                        typeof m.createdAt === "number"
                          ? m.createdAt
                          : Number.NaN
                      const resolvedCreatedAt = Number.isNaN(parsedCreatedAt)
                        ? now + index
                        : parsedCreatedAt
                      const role = m.role ?? (m.isBot ? "assistant" : "user")
                      const name = m.name || (role === "assistant" ? assistantName : "You")
                      return saveMessage({
                        id: String(m.id || ""),
                        history_id: localHistoryId,
                        name,
                        role,
                        content: m.message,
                        images: Array.isArray(m.images) ? m.images : [],
                        source: [],
                        generationInfo:
                          m.generationInfo &&
                          typeof m.generationInfo === "object" &&
                          !Array.isArray(m.generationInfo)
                            ? m.generationInfo
                            : undefined,
                        time: index,
                        message_type: m.messageType,
                        clusterId: m.clusterId,
                        modelId: m.modelId,
                        modelName: m.modelName || assistantName,
                        modelImage: m.modelImage,
                        parent_message_id: m.parentMessageId ?? null,
                        createdAt: resolvedCreatedAt
                      })
                    })
                  )
                }
              }
            } catch {
              // Local mirror is best-effort for server chats.
            }
          }
          if (chatTitle) {
            updatePageTitle(chatTitle)
          }
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : String(e || "")
          const isAbort =
            e instanceof Error && e.name === "AbortError"
              ? true
              : message.toLowerCase().includes("abort")
          if (!isAbort) {
            notification.error({
              message: t("error", { defaultValue: "Error" }),
              description:
                message ||
                t("common:serverChatLoadError", {
                  defaultValue:
                    "Failed to load server chat. Check your connection and try again."
                })
            })
          }
        } finally {
          if (serverChatLoadRef.current.controller === controller) {
            serverChatLoadRef.current = {
              chatId: serverChatId,
              controller: null,
              inFlight: false,
              loaded: true
            }
          }
          setIsLoading(false)
        }
      }

      void loadServerChat()
    }, 200)

    return () => {
      if (serverChatDebounceRef.current.timer) {
        clearTimeout(serverChatDebounceRef.current.timer)
        serverChatDebounceRef.current.timer = null
      }
    }
  }, [
    ensureServerChatHistoryId,
    notification,
    serverChatCharacterId,
    serverChatId,
    serverChatMetaLoaded,
    serverChatTitle,
    setHistory,
    setIsLoading,
    setMessages,
    setServerChatCharacterId,
    setServerChatClusterId,
    setServerChatExternalRef,
    setServerChatMetaLoaded,
    setServerChatSource,
    setServerChatState,
    setServerChatTitle,
    setServerChatTopic,
    setServerChatVersion,
    t,
    temporaryChat
  ])
}
