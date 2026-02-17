import React from "react"
import { shallow } from "zustand/shallow"
import type { TFunction } from "i18next"
import { useChatBaseState } from "@/hooks/chat/useChatBaseState"
import { useStoreMessageOption } from "@/store/option"
import type { Message } from "@/store/option"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { getHistoriesWithMetadata, saveMessage } from "@/db/dexie/helpers"
import { syncChatSettingsForServerChat } from "@/services/chat-settings"
import { normalizeConversationState } from "@/utils/conversation-state"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import { updatePageTitle } from "@/utils/update-page-title"

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

const toServerMessageId = (message: Message): string | null => {
  if (typeof message.serverMessageId !== "string") return null
  const trimmed = message.serverMessageId.trim()
  return trimmed.length > 0 ? trimmed : null
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
    messagesRef.current = messages
  }, [messages])

  React.useEffect(() => {
    streamingRef.current = streaming
  }, [streaming])

  React.useEffect(() => {
    processingRef.current = isProcessing
  }, [isProcessing])

  React.useEffect(() => {
    if (!serverChatId) return
    if (
      serverChatLoadRef.current.chatId === serverChatId &&
      serverChatLoadRef.current.loaded
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

          const list = await tldwClient.listChatMessages(
            serverChatId,
            { include_deleted: "false", include_metadata: "true" },
            { signal: controller.signal }
          )

          let encounteredUserMessage = false
          const mappedMessages = list.map((m) => {
            const meta = m as unknown as Record<string, unknown>
            const createdAt = Date.parse(m.created_at)
            const metadataExtraCandidate =
              (m as unknown as { metadata_extra?: unknown }).metadata_extra ??
              (meta?.metadata_extra as unknown)
            const metadataExtra =
              metadataExtraCandidate &&
              typeof metadataExtraCandidate === "object" &&
              !Array.isArray(metadataExtraCandidate)
                ? (metadataExtraCandidate as Record<string, unknown>)
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
              typeof moodConfidenceRaw === "number" &&
              Number.isFinite(moodConfidenceRaw)
                ? moodConfidenceRaw
                : typeof moodConfidenceRaw === "string" &&
                    moodConfidenceRaw.trim().length > 0 &&
                    Number.isFinite(Number(moodConfidenceRaw))
                  ? Number(moodConfidenceRaw)
                  : null
            const senderName =
              typeof (m as any).sender === "string"
                ? String((m as any).sender).trim()
                : ""
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
            if (m.role === "user") {
              encounteredUserMessage = true
            }
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
              message: m.content,
              sources: [],
              images: [],
              id: String(m.id),
              serverMessageId: String(m.id),
              serverMessageVersion: m.version,
              parentMessageId:
                (meta?.parent_message_id as string | null | undefined) ??
                (meta?.parentMessageId as string | null | undefined) ??
                null,
              messageType: explicitMessageType ?? inferredGreetingMessageType,
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
            }
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

          if (!shouldPreserveLocal) {
            setHistory(history)
            setMessages(mappedMessages)
          }
          if (!temporaryChat && !shouldPreserveLocal) {
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
                    list.map((m, index) => {
                      const meta = m as unknown as Record<string, unknown>
                      const parsedCreatedAt = Date.parse(m.created_at)
                      const resolvedCreatedAt = Number.isNaN(parsedCreatedAt)
                        ? now + index
                        : parsedCreatedAt
                      const role =
                        m.role === "assistant" ||
                        m.role === "system" ||
                        m.role === "user"
                          ? m.role
                          : "user"
                      const name =
                        role === "assistant"
                          ? assistantName
                          : role === "system"
                            ? "System"
                            : "You"
                      return saveMessage({
                        id: String(m.id),
                        history_id: localHistoryId,
                        name,
                        role,
                        content: m.content,
                        images: [],
                        source: [],
                        time: index,
                        message_type:
                          (meta?.message_type as string | undefined) ??
                          (meta?.messageType as string | undefined),
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
                        parent_message_id:
                          (meta?.parent_message_id as string | null | undefined) ??
                          (meta?.parentMessageId as string | null | undefined) ??
                          null,
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
    isProcessing,
    messages,
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
    streaming,
    t,
    temporaryChat
  ])
}
