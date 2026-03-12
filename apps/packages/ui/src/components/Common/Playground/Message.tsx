import React, { useEffect, useState, useRef } from "react"
import { Tag, Image, Tooltip, Avatar, Modal, message } from "antd"
import { LoadingStatus } from "./ActionInfo"
import {
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Smile,
  StopCircle as StopCircleIcon,
  Trash2
} from "lucide-react"
import { EditMessageForm } from "./EditMessageForm"
import { tagColors } from "@/utils/color"
import { removeModelSuffix } from "@/db/dexie/models"
import { parseReasoning } from "@/libs/reasoning"
import type { ChatErrorPayload } from "@/utils/chat-error-message"
import { PlaygroundUserMessageBubble } from "./PlaygroundUserMessage"
import { copyToClipboard } from "@/utils/clipboard"
import { highlightText } from "@/utils/text-highlight"
import { FeedbackModal } from "@/components/Sidepanel/Chat/FeedbackModal"
import { ToolCallBlock } from "@/components/Sidepanel/Chat/ToolCallBlock"
import type { ToolCall, ToolCallResult } from "@/types/tool-calls"
import { MessageActionsBar } from "./MessageActionsBar"
import { ReasoningBlock } from "./ReasoningBlock"
import { useStoreMessageOption } from "@/store/option"
import type { MessageVariant } from "@/store/option"
import { EDIT_MESSAGE_EVENT } from "@/utils/timeline-actions"
import type { Character } from "@/types/character"
import { DiscoSkillAnnotation } from "./DiscoSkillAnnotation"
import type { DiscoSkillComment } from "@/types/disco-skills"
import {
  attemptSkillTrigger,
  buildSkillPrompt,
  createSkillComment
} from "@/utils/disco-skill-check"
import { updateMessageDiscoSkillComment } from "@/db/dexie/helpers"
import type { MessageSteeringMode } from "@/types/message-steering"
import { formatCost } from "@/utils/model-pricing"
import { resolvePlaygroundMessageShortcutAction } from "./playground-message-shortcuts"
import {
  buildQuickMessageActionPrompt,
  type QuickMessageAction
} from "./quick-message-actions"
import type { PlaygroundMessageProps } from "./message-types"
import { MessageSourcesSection } from "./MessageSourcesSection"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useMessageState } from "./useMessageState"

const Markdown = React.lazy(() => import("../../Common/Markdown"))

const ErrorBubble: React.FC<{
  payload: ChatErrorPayload
  toggleLabels: { show: string; hide: string }
  recoveryActions?: Array<{
    id: string
    label: string
    onClick: () => void
  }>
}> = ({ payload, toggleLabels, recoveryActions = [] }) => {
  const [showDetails, setShowDetails] = React.useState(false)

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
      <p className="font-semibold">{payload.summary}</p>
      {payload.hint && (
        <p className="mt-1 text-xs text-danger">
          {payload.hint}
        </p>
      )}
      {payload.detail && (
        <button
          type="button"
          onClick={() => setShowDetails((prev) => !prev)}
          title={showDetails ? toggleLabels.hide : toggleLabels.show}
          className="mt-2 text-xs font-medium text-danger underline hover:text-danger">
          {showDetails ? toggleLabels.hide : toggleLabels.show}
        </button>
      )}
      {showDetails && payload.detail && (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-danger/10 p-2 text-xs text-danger">
          {payload.detail}
        </pre>
      )}
      {recoveryActions.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="sr-only">
            Recommended next actions:{" "}
            {recoveryActions.map((action) => action.label).join(", ")}
          </span>
          {recoveryActions.map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={action.onClick}
              className="rounded border border-danger/40 bg-surface px-2 py-1 text-[11px] font-medium text-danger transition hover:bg-danger/10"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

type Props = PlaygroundMessageProps & {
  sources?: any[]
}

export const PlaygroundMessage = React.memo(function PlaygroundMessage(props: Props) {
  const articleRef = useRef<HTMLElement | null>(null)

  const {
    t,
    checkWideMode,
    isUserChatBubble,
    autoCopyResponseToClipboard,
    autoPlayTTS,
    copyAsFormattedText,
    userTextColor,
    assistantTextColor,
    userTextFont,
    assistantTextFont,
    userTextSize,
    assistantTextSize,
    userDisplayName,
    showCharacterPortraits,
    showMoodBadge,
    showMoodConfidence,
    userPersonaImage,
    ttsProvider,
    capabilities,
    uiMode,
    isProMode,
    cancel,
    isSpeaking,
    speak,
    ttsActionDisabled,
    ttsDisabledReason,
    audioHealthState,
    voicesAvailable,
    thumb,
    detail,
    sourceFeedback,
    canSubmit,
    isFeedbackSubmitting,
    showThanks,
    submitThumb,
    submitDetail,
    submitSourceThumb,
    feedbackExplicitAvailable,
    feedbackImplicitAvailable,
    trackCopy,
    trackSourcesExpanded,
    trackSourceClick,
    trackCitationUsed,
    trackDwellTime,
    errorPayload,
    errorFriendlyText,
    messageUsage,
    messageCostUsd,
    showUsageMetadata,
    interruptedGeneration,
    interruptionReason,
    streamTransportInterrupted,
    partialResponseSaved,
    streamTransportInterruptionReason,
    showPartialSaveMarker,
    messageTimestamp,
    fallbackAudit,
    fallbackAuditPolicyLabel,
    fallbackAuditPathLabel,
    imageGenerationMetadata,
    canRegenerateImage,
    showInlineImageActions,
    isImageGenerationAssistantEvent,
    imageGenerationEventSummary,
    variantCount,
    resolvedVariantIndex,
    imageVariantEntries,
    activeVariantPreview,
    showVariantPager,
    canSwipePrev,
    canSwipeNext,
    shouldUseCharacterIdentity,
    resolvedMoodLabel,
    moodBadgeLabel,
    characterAvatar,
    resolvedModelImage,
    resolvedModelName,
    resolvedUserPersonaImage,
    portraitImage,
    messageRenderSide,
    shouldShowPortrait,
    shouldShowAvatarColumn,
    avatarColumnAlignmentClass,
    shouldPreviewAvatar,
    userTextClass,
    assistantTextClass,
    chatTextClass,
    renderGreetingMarkdown,
    shouldRenderStreamingPlainText,
    shouldShowLoadingStatus,
    isActiveResponse,
    feedbackDisabled,
    showFeedbackControls,
    feedbackDisabledReason,
    ttsClipMeta,
    messageKey,
    isLastMessage,
    resolvedRole,
    isSystemMessage,
    canSaveKnowledge,
    canSaveToNotes,
    canSaveToFlashcards,
    canSaveToWorkspaceNotes,
    canGenerateDocument,
    replyId,
    canReply,
    discoSkillsEnabled,
    discoSkillsStats,
    discoTriggerProbability,
    discoPersistComments,
    selectedModel,
    setReplyTarget,
    ragPinnedResults,
    setMessages,
    apiProviderOverride,
    updateChatModelSetting,
  } = useMessageState(props)

  const [isBtnPressed, setIsBtnPressed] = React.useState(false)
  const [editMode, setEditMode] = React.useState(false)
  const [isFeedbackOpen, setIsFeedbackOpen] = React.useState(false)
  const [isAvatarPreviewOpen, setIsAvatarPreviewOpen] = React.useState(false)
  const [compareVariantIndex, setCompareVariantIndex] = React.useState<
    number | null
  >(null)
  const [savingKnowledge, setSavingKnowledge] = React.useState<
    "note" | "flashcard" | null
  >(null)
  const responseDwellSentKeyRef = useRef<string | null>(null)

  const persistedSkillComment = discoPersistComments
    ? props.discoSkillComment ?? null
    : null
  const [skillComment, setSkillComment] = useState<DiscoSkillComment | null>(
    persistedSkillComment
  )
  const [isGeneratingSkillComment, setIsGeneratingSkillComment] = useState(false)
  const skillCommentGeneratedRef = useRef(false)
  const previousMessageRef = useRef<string | null>(null)
  const previousMessageIdRef = useRef<string | null>(null)

  // Internal adapters: bind index/messageId so sub-components receive arg-free callbacks
  const internalEditFormSubmit = React.useCallback(
    (value: string, isSend: boolean) => {
      props.onEditFormSubmit(props.currentMessageIndex, value, !props.isBot, isSend)
    },
    [props.onEditFormSubmit, props.currentMessageIndex, props.isBot]
  )
  const internalTogglePinned = React.useCallback(() => {
    props.onTogglePinned?.(props.currentMessageIndex)
  }, [props.onTogglePinned, props.currentMessageIndex])
  const internalNewBranch = React.useCallback(() => {
    props.onNewBranch?.(props.currentMessageIndex)
  }, [props.onNewBranch, props.currentMessageIndex])
  const internalSwipePrev = React.useCallback(() => {
    props.onSwipePrev?.(props.messageId ?? "")
  }, [props.onSwipePrev, props.messageId])
  const internalSwipeNext = React.useCallback(() => {
    props.onSwipeNext?.(props.messageId ?? "")
  }, [props.onSwipeNext, props.messageId])

  // Track streaming completion for aria-live announcement
  const wasStreamingRef = useRef(false)
  const [streamingComplete, setStreamingComplete] = useState(false)
  useEffect(() => {
    if (!props.isBot || !isLastMessage) {
      wasStreamingRef.current = false
      setStreamingComplete(false)
      return
    }

    if (wasStreamingRef.current && !props.isStreaming && !props.isProcessing) {
      setStreamingComplete(true)
      const timer = setTimeout(() => setStreamingComplete(false), 2000)
      return () => clearTimeout(timer)
    }
    wasStreamingRef.current = props.isStreaming || props.isProcessing
  }, [props.isBot, isLastMessage, props.isStreaming, props.isProcessing])

  const compareVariantPreview = React.useMemo(() => {
    if (compareVariantIndex == null) return null
    return (
      imageVariantEntries.find((entry) => entry.index === compareVariantIndex) || null
    )
  }, [compareVariantIndex, imageVariantEntries])
  React.useEffect(() => {
    if (compareVariantIndex == null) return
    const compareStillValid = imageVariantEntries.some(
      (entry) => entry.index === compareVariantIndex
    )
    if (!compareStillValid || compareVariantIndex === resolvedVariantIndex) {
      setCompareVariantIndex(null)
    }
  }, [compareVariantIndex, imageVariantEntries, resolvedVariantIndex])

  const hasMessageKeyboardShortcuts =
    (canSwipePrev || canSwipeNext) ||
    Boolean(props.onNewBranch) ||
    Boolean(props.isBot && props.onRegenerate)
  const handleMessageShortcut = React.useCallback(
    (event: React.KeyboardEvent<HTMLElement>) => {
      const action = resolvePlaygroundMessageShortcutAction(event.nativeEvent)
      if (!action) return

      if (action === "variant_prev") {
        if (!canSwipePrev || !internalSwipePrev) return
        event.preventDefault()
        internalSwipePrev()
        articleRef.current?.focus()
        return
      }
      if (action === "variant_next") {
        if (!canSwipeNext || !internalSwipeNext) return
        event.preventDefault()
        internalSwipeNext()
        articleRef.current?.focus()
        return
      }
      if (action === "new_branch") {
        if (!internalNewBranch) return
        event.preventDefault()
        internalNewBranch()
        articleRef.current?.focus()
        return
      }
      if (action === "regenerate") {
        if (!props.isBot || !props.onRegenerate) return
        event.preventDefault()
        props.onRegenerate()
        articleRef.current?.focus()
      }
    },
    [
      canSwipeNext,
      canSwipePrev,
      props.isBot,
      internalNewBranch,
      props.onRegenerate,
      internalSwipeNext,
      internalSwipePrev
    ]
  )

  const portraitSide: "left" | "right" = messageRenderSide

  const userAvatarNode = props.userAvatar ? (
    props.userAvatar
  ) : resolvedUserPersonaImage ? (
    <Avatar
      src={resolvedUserPersonaImage}
      alt={userDisplayName.trim() || t("common:you", "You")}
      className="size-8"
    />
  ) : null

  useEffect(() => {
    if (typeof window === "undefined") return
    if (!props.isBot && isUserChatBubble) return

    const handleEditMessage = (event: Event) => {
      const detail = (event as CustomEvent<{ messageId?: string }>).detail
      if (!detail?.messageId) return
      if (props.isBot) return
      const matches =
        detail.messageId === props.messageId ||
        detail.messageId === props.serverMessageId
      if (matches) {
        setEditMode(true)
      }
    }

    window.addEventListener(EDIT_MESSAGE_EVENT, handleEditMessage)
    return () => {
      window.removeEventListener(EDIT_MESSAGE_EVENT, handleEditMessage)
    }
  }, [isUserChatBubble, props.isBot, props.messageId, props.serverMessageId])

  useEffect(() => {
    const dwellMessageKey = props.serverMessageId ?? null
    if (!dwellMessageKey) return
    if (!props.isBot || !isLastMessage) return
    if (props.isStreaming || props.isProcessing) return
    if (!feedbackImplicitAvailable) return
    if (responseDwellSentKeyRef.current === dwellMessageKey) return

    const timeout = window.setTimeout(() => {
      trackDwellTime(3000)
      responseDwellSentKeyRef.current = dwellMessageKey
    }, 3000)

    return () => {
      window.clearTimeout(timeout)
    }
  }, [
    feedbackImplicitAvailable,
    isLastMessage,
    props.isBot,
    props.isProcessing,
    props.isStreaming,
    props.serverMessageId,
    trackDwellTime
  ])

  const buildReplyPreview = React.useCallback(
    (value: string) => {
      const collapsed = value.replace(/\s+/g, " ").trim()
      if (!collapsed) {
        return t("common:replyTargetFallback", "Message")
      }
      if (collapsed.length > 140) {
        return `${collapsed.slice(0, 137)}...`
      }
      return collapsed
    },
    [t]
  )

  const handleReply = React.useCallback(() => {
    if (!replyId) return
    setReplyTarget({
      id: replyId,
      preview: buildReplyPreview(errorFriendlyText || props.message),
      name: props.name,
      isBot: props.isBot
    })
  }, [
    replyId,
    setReplyTarget,
    buildReplyPreview,
    errorFriendlyText,
    props.message,
    props.name,
    props.isBot
  ])

  const handleCopy = React.useCallback(async () => {
    await copyToClipboard({
      text: errorFriendlyText || props.message,
      formatted: copyAsFormattedText
    })
    trackCopy()
    setIsBtnPressed(true)
    setTimeout(() => {
      setIsBtnPressed(false)
    }, 2000)
  }, [copyAsFormattedText, errorFriendlyText, props.message, trackCopy])

  const handleGenerateDocument = React.useCallback(() => {
    if (!props.serverChatId || typeof window === "undefined") return
    window.dispatchEvent(
      new CustomEvent("tldw:open-document-generator", {
        detail: {
          conversationId: props.serverChatId,
          message: errorFriendlyText || props.message,
          messageId: props.serverMessageId
        }
      })
    )
  }, [errorFriendlyText, props.message, props.serverChatId, props.serverMessageId])

  const handleSaveToWorkspaceNotes = React.useCallback(() => {
    const snippet = (errorFriendlyText || props.message || "").trim()
    if (!snippet || !props.onSaveToWorkspaceNotes) return
    props.onSaveToWorkspaceNotes({
      message: snippet,
      isBot: props.isBot,
      name: props.name,
      messageId: props.messageId || props.serverMessageId || undefined,
      createdAt:
        typeof props.createdAt === "number" || typeof props.createdAt === "string"
          ? props.createdAt
          : undefined
    })
  }, [
    errorFriendlyText,
    props.createdAt,
    props.isBot,
    props.message,
    props.messageId,
    props.name,
    props.onSaveToWorkspaceNotes,
    props.serverMessageId
  ])

  const handleSaveKnowledge = async (makeFlashcard: boolean) => {
    if (!props.serverChatId || !props.serverMessageId) return
    const snippet = (errorFriendlyText || props.message || "").trim()
    if (!snippet) {
      message.error(t("saveToNotesEmpty", "Nothing to save yet."))
      return
    }
    setSavingKnowledge(makeFlashcard ? "flashcard" : "note")
    try {
      await tldwClient.initialize().catch(() => null)
      await tldwClient.saveChatKnowledge({
        conversation_id: props.serverChatId,
        message_id: props.serverMessageId,
        snippet,
        make_flashcard: makeFlashcard
      })
      message.success(
        makeFlashcard
          ? t("savedToFlashcards", "Saved to Flashcards")
          : t("savedToNotes", "Saved to Notes")
      )
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : t("somethingWentWrong")
      message.error(errorMessage)
    } finally {
      setSavingKnowledge(null)
    }
  }

  const autoCopyToClipboard = async () => {
    if (
      autoCopyResponseToClipboard &&
      props.isBot &&
      isLastMessage &&
      !props.isStreaming &&
      !props.isProcessing &&
      props.message.trim().length > 0 &&
      !errorPayload &&
      !ttsActionDisabled
    ) {
      await copyToClipboard({
        text: props.message,
        formatted: copyAsFormattedText
      })
      trackCopy()
      setIsBtnPressed(true)
      setTimeout(() => {
        setIsBtnPressed(false)
      }, 2000)
    }
  }

  useEffect(() => {
    autoCopyToClipboard()
  }, [
    autoCopyResponseToClipboard,
    props.isBot,
    props.currentMessageIndex,
    props.totalMessages,
    props.isStreaming,
    props.isProcessing,
    props.message
  ])

  const actionRowVisibility = isProMode
    ? "flex"
    : "hidden group-hover:flex group-focus-within:flex"
  const overflowChipVisibility = isProMode
    ? "hidden"
    : "inline-flex group-hover:hidden"
  const showInlineActions = !props.isProcessing && !editMode

  const handleThumbUp = React.useCallback(() => {
    void submitThumb("up")
  }, [submitThumb])

  const handleThumbDown = React.useCallback(() => {
    setIsFeedbackOpen(true)
    void submitThumb("down")
  }, [submitThumb])

  const handleOpenDetails = React.useCallback(() => {
    setIsFeedbackOpen(true)
  }, [])

  useEffect(() => {
    if (
      autoPlayTTS &&
      props.isTTSEnabled &&
      props.isBot &&
      isLastMessage &&
      !props.isStreaming &&
      !props.isProcessing &&
      props.message.trim().length > 0 &&
      !errorPayload
    ) {
      let messageToSpeak = props.message

      speak({
        utterance: messageToSpeak,
        saveClip: true,
        clipMeta: ttsClipMeta
      })
    }
  }, [
    autoPlayTTS,
    props.isTTSEnabled,
    props.isBot,
    props.currentMessageIndex,
    props.totalMessages,
    props.isStreaming,
    props.isProcessing,
    props.message,
    errorPayload,
    ttsActionDisabled,
    ttsClipMeta
  ])

  useEffect(() => {
    if (!discoPersistComments) return
    if (persistedSkillComment) {
      setSkillComment(persistedSkillComment)
      skillCommentGeneratedRef.current = true
    }
  }, [discoPersistComments, persistedSkillComment])

  useEffect(() => {
    const currentMessageId = props.messageId ?? null
    const messageIdChanged =
      previousMessageIdRef.current !== null &&
      previousMessageIdRef.current !== currentMessageId
    const messageChanged =
      previousMessageRef.current !== null &&
      previousMessageRef.current !== props.message
    if (messageIdChanged || messageChanged) {
      skillCommentGeneratedRef.current = false
      setSkillComment(null)
      if (discoPersistComments && props.messageId) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === props.messageId
              ? { ...msg, discoSkillComment: undefined }
              : msg
          )
        )
        void updateMessageDiscoSkillComment(props.messageId, null).catch(
          () => null
        )
      }
    }
    previousMessageRef.current = props.message
    previousMessageIdRef.current = currentMessageId
  }, [
    props.message,
    props.messageId,
    props.activeVariantIndex,
    discoPersistComments,
    setMessages
  ])

  // Disco Skills comment generation effect
  useEffect(() => {
    // Only trigger for bot messages that are complete
    if (
      !discoSkillsEnabled ||
      !props.isBot ||
      !isLastMessage ||
      props.isStreaming ||
      props.isProcessing ||
      !props.message?.trim() ||
      errorPayload ||
      (discoPersistComments && persistedSkillComment) ||
      skillCommentGeneratedRef.current ||
      isGeneratingSkillComment ||
      skillComment
    ) {
      return
    }

    // Check if a skill should trigger
    const triggerResult = attemptSkillTrigger(
      props.message,
      discoSkillsStats,
      discoTriggerProbability
    )

    if (!triggerResult) {
      skillCommentGeneratedRef.current = true
      return
    }

    const { skill, passed } = triggerResult

    // Prevent re-generation
    skillCommentGeneratedRef.current = true
    setIsGeneratingSkillComment(true)

    // Generate the skill comment via LLM
    const generateComment = async () => {
      try {
        const model = selectedModel || "gpt-4o-mini"
        const prompt = buildSkillPrompt(skill, props.message, passed)

        await tldwClient.initialize().catch(() => null)
        const response = await tldwClient.createChatCompletion({
          model,
          messages: [
            {
              role: "system",
              content:
                "You are a skill voice from Disco Elysium. Stay in character. Be concise (1-3 sentences max). Do not use quotation marks."
            },
            { role: "user", content: prompt }
          ],
          temperature: 0.9,
          max_tokens: 150
        })

        const data = await response.json()
        const commentText =
          data?.choices?.[0]?.message?.content?.trim() ||
          data?.content?.trim() ||
          ""

        if (commentText) {
          const comment = createSkillComment(
            skill,
            commentText,
            passed,
            props.messageId
          )
          setSkillComment(comment)
          if (discoPersistComments && props.messageId) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === props.messageId
                  ? { ...msg, discoSkillComment: comment }
                  : msg
              )
            )
            void updateMessageDiscoSkillComment(props.messageId, comment).catch(
              () => null
            )
          }
        }
      } catch (err) {
        console.error("Failed to generate disco skill comment:", err)
      } finally {
        setIsGeneratingSkillComment(false)
      }
    }

    generateComment()
  }, [
    discoSkillsEnabled,
    discoSkillsStats,
    discoTriggerProbability,
    props.isBot,
    isLastMessage,
    props.isStreaming,
    props.isProcessing,
    props.message,
    props.messageId,
    errorPayload,
    selectedModel,
    isGeneratingSkillComment,
    discoPersistComments,
    persistedSkillComment,
    skillComment,
    setMessages
  ])

  const handleToggleTts = React.useCallback(() => {
    if (ttsActionDisabled) return
    if (isSpeaking) {
      cancel()
      return
    }
    speak({
      utterance: errorFriendlyText || props.message,
      saveClip: props.isBot,
      clipMeta: props.isBot ? ttsClipMeta : undefined
    })
  }, [
    ttsActionDisabled,
    isSpeaking,
    cancel,
    speak,
    errorFriendlyText,
    props.message,
    props.isBot,
    ttsClipMeta
  ])

  const handleDelete = React.useCallback(() => {
    if (!props.onDeleteMessage) return

    Modal.confirm({
      title: t("common:confirmTitle", "Please confirm"),
      content: t("common:deleteMessageConfirm", "Delete this message?"),
      okText: t("common:delete", "Delete"),
      cancelText: t("common:cancel", "Cancel"),
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await props.onDeleteMessage?.(props.currentMessageIndex)
          if (!props.suppressDeleteSuccessToast) {
            message.success(t("common:deleted", "Deleted"))
          }
        } catch (err) {
          console.error("Failed to delete message:", err)
          const fallback = t("common:deleteFailed", "Delete failed")
          const errorMessage = err instanceof Error ? err.message : ""
          message.error(errorMessage || fallback)
        }
      }
    })
  }, [props.onDeleteMessage, props.currentMessageIndex, props.suppressDeleteSuccessToast, t])
  const handleOpenModelSettings = React.useCallback(() => {
    if (typeof window === "undefined") return
    window.dispatchEvent(new CustomEvent("tldw:open-model-settings"))
  }, [])
  const handleOpenKnowledgePanel = React.useCallback(() => {
    if (typeof window === "undefined") return
    window.dispatchEvent(
      new CustomEvent("tldw:open-knowledge-panel", {
        detail: { tab: "search" }
      })
    )
  }, [])
  const pinnedSourceKeySet = React.useMemo(() => {
    const set = new Set<string>()
    for (const entry of ragPinnedResults || []) {
      const parts = [
        entry?.url,
        entry?.source,
        entry?.title
      ]
        .map((value) =>
          typeof value === "string" ? value.trim().toLowerCase() : ""
        )
        .filter((value) => value.length > 0)
      for (const value of parts) {
        set.add(value)
      }
    }
    return set
  }, [ragPinnedResults])
  const resolveSourcePinnedState = React.useCallback(
    (source: any): "active" | "inactive" | null => {
      if (!pinnedSourceKeySet.size) return null
      const sourceKeys = [
        source?.url,
        source?.name,
        source?.metadata?.source,
        source?.metadata?.title
      ]
        .map((value) =>
          typeof value === "string" ? value.trim().toLowerCase() : ""
        )
        .filter((value) => value.length > 0)
      if (sourceKeys.length === 0) return "inactive"
      const matches = sourceKeys.some((value) => pinnedSourceKeySet.has(value))
      return matches ? "active" : "inactive"
    },
    [pinnedSourceKeySet]
  )
  const buildSourceReference = React.useCallback(
    (source: any, index: number): string => {
      const sourceLabel =
        source?.name ||
        source?.metadata?.title ||
        source?.metadata?.source ||
        source?.url ||
        t("common:sourceLabel", "Source")
      return `[${index + 1}] ${String(sourceLabel).trim()}`
    },
    [t]
  )
  const buildFollowUpPrompt = React.useCallback(
    (sources: any[]) => {
      const references = sources
        .map((source, index) => buildSourceReference(source, index))
        .join("\n")
      return [
        t(
          "playground:sources.askWithTemplateHeader",
          "Use these sources in your next answer:"
        ),
        references,
        "",
        t(
          "playground:sources.askWithTemplateQuestion",
          "Question:"
        )
      ]
        .filter(Boolean)
        .join("\n")
    },
    [buildSourceReference, t]
  )
  const handleAskWithSources = React.useCallback(
    (sources: any[]) => {
      if (typeof window === "undefined" || !Array.isArray(sources) || sources.length === 0) {
        return
      }
      const prompt = buildFollowUpPrompt(sources)
      window.dispatchEvent(
        new CustomEvent("tldw:set-composer-message", {
          detail: { message: prompt }
        })
      )
      window.dispatchEvent(new CustomEvent("tldw:open-knowledge-panel", {
        detail: { tab: "search" }
      }))
      window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
    },
    [buildFollowUpPrompt]
  )
  const handleQuickMessageAction = React.useCallback(
    (action: QuickMessageAction) => {
      if (typeof window === "undefined") return
      const content = (errorFriendlyText || props.message || "").trim()
      if (!content) return

      const lineage =
        props.serverMessageId ||
        props.messageId ||
        `index:${props.currentMessageIndex + 1}`
      const sourceReferences = (props.sources || []).map((source, index) =>
        buildSourceReference(source, index)
      )
      const prompt = buildQuickMessageActionPrompt({
        action,
        message: content,
        lineage,
        sourceReferences
      })

      window.dispatchEvent(
        new CustomEvent("tldw:set-composer-message", {
          detail: { message: prompt }
        })
      )
      window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
    },
    [
      buildSourceReference,
      errorFriendlyText,
      props.currentMessageIndex,
      props.message,
      props.messageId,
      props.serverMessageId,
      props.sources
    ]
  )
  const handleEnableProviderFallback = React.useCallback(() => {
    updateChatModelSetting("apiProvider", undefined)
    message.info(
      apiProviderOverride
        ? t(
            "playground:errorRecovery.fallbackClearedProvider",
            "Provider override cleared. Retrying with fallback routing."
          )
        : t(
            "playground:errorRecovery.fallbackRetrying",
            "Retrying with provider fallback policy."
          )
    )
    props.onRegenerate()
  }, [apiProviderOverride, props.onRegenerate, t, updateChatModelSetting])
  const errorRecoveryActions = React.useMemo(() => {
    if (!errorPayload) return []
    const actions: Array<{ id: string; label: string; onClick: () => void }> = [
      {
        id: "retry",
        label: t(
          "playground:errorRecovery.retrySameModel",
          "Retry same model"
        ),
        onClick: () => props.onRegenerate()
      },
      {
        id: "switch",
        label: t(
          "playground:errorRecovery.switchModel",
          "Switch model"
        ),
        onClick: handleOpenModelSettings
      },
      {
        id: "fallback",
        label: t(
          "playground:errorRecovery.tryProviderFallback",
          "Try provider fallback"
        ),
        onClick: handleEnableProviderFallback
      }
    ]
    if (props.onContinue && !props.hideContinue) {
      actions.push({
        id: "continue",
        label: t(
          "playground:errorRecovery.continueFromPartial",
          "Continue from partial"
        ),
        onClick: props.onContinue
      })
    }
    return actions
  }, [
    errorPayload,
    handleEnableProviderFallback,
    handleOpenModelSettings,
    props.hideContinue,
    props.onContinue,
    props.onRegenerate,
    t
  ])
  const interruptionRecoveryActions = React.useMemo(() => {
    if (!interruptedGeneration || errorPayload) return []
    const actions: Array<{ id: string; label: string; onClick: () => void }> = [
      {
        id: "retry",
        label: t(
          "playground:errorRecovery.retrySameModel",
          "Retry same model"
        ),
        onClick: () => props.onRegenerate()
      },
      {
        id: "switch",
        label: t(
          "playground:errorRecovery.switchModel",
          "Switch model"
        ),
        onClick: handleOpenModelSettings
      },
      {
        id: "fallback",
        label: t(
          "playground:errorRecovery.tryProviderFallback",
          "Try provider fallback"
        ),
        onClick: handleEnableProviderFallback
      }
    ]
    if (props.onContinue && !props.hideContinue) {
      actions.push({
        id: "continue",
        label: t(
          "playground:errorRecovery.continueFromPartial",
          "Continue from partial"
        ),
        onClick: props.onContinue
      })
    }
    return actions
  }, [
    errorPayload,
    handleEnableProviderFallback,
    handleOpenModelSettings,
    interruptedGeneration,
    props.hideContinue,
    props.onContinue,
    props.onRegenerate,
    t
  ])

  const compareLabel = t("playground:composer.compareTag", "Compare")
  const compareSelectedLabel = t(
    "playground:composer.compareSelectedTag",
    "Compared"
  )
  const compareErrorLabel = t("playground:composer.error.label", "Error")
  const systemLabel = t("playground:systemPrompt", "System prompt")
  const messageRole = isSystemMessage
    ? "system"
    : props.isBot
      ? "assistant"
      : "user"
  const messageRoleLabel =
    messageRole === "system"
      ? t("message.role.system", "System")
      : messageRole === "assistant"
        ? t("message.role.assistant", "Assistant")
        : t("message.role.user", "User")
  const messageAriaLabel = t("message.ariaLabel", {
    defaultValue: "{{role}} message {{current}} of {{total}}",
    role: messageRoleLabel,
    current: props.currentMessageIndex + 1,
    total: props.totalMessages
  }) as string

  if (
    isUserChatBubble &&
    !props.isBot &&
    !isSystemMessage &&
    !showCharacterPortraits
  ) {
    return (
      <PlaygroundUserMessageBubble
        {...props}
        onEditFormSubmit={internalEditFormSubmit}
        role={resolvedRole}
        onDelete={props.onDeleteMessage ? handleDelete : undefined}
      />
    )
  }

  const MARKDOWN_BASE_CLASSES =
    "prose break-words text-message dark:prose-invert prose-p:leading-relaxed prose-pre:p-0 dark:prose-dark max-w-none"
  const hasSources = props.isBot && Boolean(props?.sources?.length)
  const messageSpacing = isProMode
    ? `gap-2 px-4 pt-3 ${hasSources ? "pb-4" : "pb-2.5"}`
    : `gap-1.5 px-3 pt-2 ${hasSources ? "pb-3" : "pb-2"}`
  const messageCardClass = isSystemMessage
    ? `flex max-w-[calc(100%-1.75rem)] flex-col rounded-2xl border border-dashed border-warn/30 bg-warn/10 shadow-sm ${messageSpacing}`
    : props.isBot
      ? `flex max-w-[calc(100%-1.75rem)] flex-col rounded-2xl border border-border/50 bg-surface/60 shadow-sm border-l-2 border-l-primary/20 ${messageSpacing}`
      : `flex max-w-[calc(100%-1.75rem)] flex-col rounded-2xl border border-border/50 bg-surface2/60 shadow-sm ${messageSpacing}`
  const portraitPanel = shouldShowPortrait ? (
    <button
      type="button"
      onClick={() => setIsAvatarPreviewOpen(true)}
      className="relative hidden h-40 w-28 shrink-0 overflow-hidden rounded-2xl border border-border/60 bg-surface/30 shadow-sm transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-focus sm:block md:h-52 md:w-36"
      aria-label={t("playground:previewCharacterAvatar", {
        defaultValue: "Preview character avatar"
      }) as string}
    >
      <img
        src={portraitImage}
        alt={
          props.isBot
            ? resolvedModelName || props.name
            : userDisplayName.trim() || t("common:you", "You")
        }
        className="h-full w-full object-cover"
        loading="lazy"
      />
      <span className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-transparent" />
    </button>
  ) : null
  const avatarColumn = shouldShowAvatarColumn ? (
    <div className={`w-8 flex flex-col relative ${avatarColumnAlignmentClass}`}>
      {props.isBot ? (
        !resolvedModelImage ? (
          <div className="relative h-7 w-7 p-1 rounded-sm text-white flex items-center justify-center  text-opacity-100">
            <div className="absolute h-8 w-8 rounded-full bg-gradient-to-r from-green-300 to-purple-400"></div>
          </div>
        ) : shouldPreviewAvatar ? (
          <button
            type="button"
            onClick={() => setIsAvatarPreviewOpen(true)}
            className="rounded-full focus:outline-none focus:ring-2 focus:ring-focus"
            aria-label={t("playground:previewCharacterAvatar", {
              defaultValue: "Preview character avatar"
            }) as string}
          >
            <Avatar
              src={resolvedModelImage}
              alt={resolvedModelName || props.name}
              className="size-8"
            />
          </button>
        ) : (
          <Avatar
            src={resolvedModelImage}
            alt={resolvedModelName || props.name}
            className="size-8"
          />
        )
      ) : isSystemMessage ? (
        <div className="relative h-7 w-7 p-1 rounded-sm text-warn flex items-center justify-center text-opacity-100">
          <div className="absolute h-8 w-8 rounded-full border border-warn/40 bg-warn/10"></div>
        </div>
      ) : !userAvatarNode ? (
        <div className="relative h-7 w-7 p-1 rounded-sm text-white flex items-center justify-center  text-opacity-100">
          <div className="absolute h-8 w-8 rounded-full from-primary/60 to-primary bg-gradient-to-r"></div>
        </div>
      ) : (
        userAvatarNode
      )}
    </div>
  ) : null
  return (
    <article
      ref={articleRef}
      data-testid="chat-message"
      data-role={messageRole}
      data-message-type={props.message_type}
      data-index={props.currentMessageIndex}
      data-message-id={props.messageId}
      data-server-message-id={props.serverMessageId}
      data-search-match={props.searchMatch || undefined}
      aria-label={messageAriaLabel}
      aria-busy={props.isStreaming && isLastMessage ? true : undefined}
      tabIndex={hasMessageKeyboardShortcuts ? 0 : undefined}
      onKeyDown={hasMessageKeyboardShortcuts ? handleMessageShortcut : undefined}
      className={`group relative flex w-full max-w-5xl flex-col items-end justify-center text-text ${
        isProMode ? "pb-3 md:px-5" : "pb-2 md:px-4"
      } ${checkWideMode ? "max-w-none" : ""} ${
        props.searchMatch === "active"
          ? "rounded-lg ring-2 ring-primary/60 ring-offset-2 ring-offset-bg"
          : props.searchMatch === "match"
            ? "rounded-lg ring-1 ring-primary/35 ring-offset-1 ring-offset-bg"
            : ""
      }`}>
      {/* Inline stop button while streaming on the latest assistant message */}
      {props.isBot && (props.isStreaming || props.isProcessing) && isLastMessage && props.onStopStreaming && (
        <div className="absolute right-2 top-0 z-10">
          <Tooltip title={t("playground:tooltip.stopStreaming") as string}>
            <button
              type="button"
              onClick={props.onStopStreaming}
              data-testid="chat-message-stop-streaming"
              title={t("playground:composer.stopStreaming") as string}
              className="rounded-md border border-border bg-surface/70 p-1 text-text backdrop-blur hover:bg-surface">
              <StopCircleIcon className="w-5 h-5" />
              <span className="sr-only">{t("playground:composer.stopStreaming")}</span>
            </button>
          </Tooltip>
        </div>
      )}
      {/* <div className="text-base md:max-w-2xl lg:max-w-xl xl:max-w-3xl flex lg:px-0 m-auto w-full"> */}
      <div
        className={`flex flex-row m-auto w-full ${
          isProMode ? "gap-4 md:gap-6 my-2" : "gap-3 md:gap-4 my-1.5"
        }`}>
        {portraitSide === "left" ? portraitPanel : null}
        {portraitSide === "left" ? avatarColumn : null}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className={messageCardClass}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {isSystemMessage ? (
                  <span className="inline-flex items-center rounded-full border border-warn/40 bg-warn/10 px-2 py-0.5 text-xs font-medium text-warn">
                    {systemLabel}
                  </span>
                ) : (
                  <span className="text-caption font-semibold text-text">
                    {props.isBot
                      ? removeModelSuffix(
                          `${resolvedModelName || props?.name}`?.replaceAll(
                            /accounts\/[^\/]+\/models\//g,
                            ""
                          )
                        )
                      : userDisplayName.trim() || t("common:you", "You")}
                  </span>
                )}
                {messageTimestamp && (
                  <span className="text-xs text-text-muted">
                    • {messageTimestamp}
                  </span>
                )}
                {props.isBot && !isSystemMessage && showMoodBadge && moodBadgeLabel && (
                  <span
                    data-testid="message-mood-indicator"
                    className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
                  >
                    <Smile className="h-3 w-3" aria-hidden="true" />
                    <span>{moodBadgeLabel}</span>
                  </span>
                )}
                {props?.message_type && (
                  <Tag
                    className="!m-0"
                    color={tagColors[props?.message_type] || "default"}>
                    {t(`copilot.${props?.message_type}`)}
                  </Tag>
                )}
                {props.isBot && props.message_type === "compare:reply" && (
                  <div className="flex items-center gap-2">
                    {props.compareSelectable && props.onToggleCompareSelect ? (
                      <button
                        type="button"
                        onClick={props.onToggleCompareSelect}
                        aria-label={
                          props.compareSelected
                            ? compareSelectedLabel
                            : compareLabel
                        }
                        aria-pressed={props.compareSelected}
                        title={
                          props.compareSelected
                            ? compareSelectedLabel
                            : compareLabel
                        }
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium border transition ${
                          props.compareSelected
                            ? "bg-primary text-white border-primary"
                            : "bg-primary/10 text-primary border-primary/30"
                        }`}
                      >
                        {props.compareSelected && (
                          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        )}
                        {props.compareSelected
                          ? compareSelectedLabel
                          : compareLabel}
                      </button>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        {compareLabel}
                      </span>
                    )}
                    {props.compareError && (
                      <div
                        aria-label={compareErrorLabel}
                        className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2">
                        <AlertTriangle className="h-4 w-4 flex-shrink-0 text-danger" aria-hidden="true" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-danger">
                            {t("playground:compareErrorTitle", "Response failed")}
                          </p>
                          {props.compareErrorModelLabel && (
                            <p className="text-[10px] text-text-muted">
                              {props.compareErrorModelLabel}
                            </p>
                          )}
                        </div>
                        {props.onCompareRetry && (
                          <button
                            type="button"
                            onClick={props.onCompareRetry}
                            className="rounded border border-danger/30 px-2 py-0.5 text-[10px] text-danger hover:bg-danger/10"
                          >
                            {t("playground:compareRetry", "Retry")}
                          </button>
                        )}
                      </div>
                    )}
                    {props.compareChosen && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-1 text-xs font-medium text-success">
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        {t(
                          "playground:composer.compareChosenLabel",
                          "Chosen"
                        )}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>

          {/* Unified loading status indicator */}
          {shouldShowLoadingStatus && (
            <LoadingStatus
              isProcessing={props.isProcessing}
              isStreaming={props.isStreaming}
              isSearchingInternet={props.isSearchingInternet}
              isEmbedding={props.isEmbedding}
              actionInfo={props.actionInfo}
            />
          )}
          {showUsageMetadata && (
            <div className="text-xs text-text-muted tabular-nums">
              {messageUsage.promptTokens}{" "}
              {t("playground:tokens.prompt", "prompt")} +{" "}
              {messageUsage.completionTokens}{" "}
              {t("playground:tokens.completion", "completion")} ={" "}
              {messageUsage.totalTokens}{" "}
              {t("playground:tokens.total", "tokens")}
              {messageCostUsd != null && (
                <>
                  {" "}
                  • {formatCost(messageCostUsd)}
                </>
              )}
            </div>
          )}
          {props.isBot && !isSystemMessage && fallbackAudit && (
            <div
              data-testid="message-fallback-audit"
              className="text-[11px] text-text-muted"
            >
              {fallbackAuditPolicyLabel}
              {fallbackAuditPathLabel ? ` • ${fallbackAuditPathLabel}` : ""}
              {typeof fallbackAudit.attempts === "number" &&
              fallbackAudit.attempts > 1
                ? ` • ${t("playground:routing.attempts", "{{count}} attempts", {
                    count: fallbackAudit.attempts
                  } as any)}`
                : ""}
              {fallbackAudit.reason ? ` • ${fallbackAudit.reason}` : ""}
            </div>
          )}
          {isImageGenerationAssistantEvent && imageGenerationEventSummary && (
            <div
              data-testid="playground-image-event-card"
              className="rounded-md border border-primary/25 bg-primary/5 px-3 py-2 text-xs text-text"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-primaryStrong">
                  {t(
                    "playground:imageGeneration.eventTitle",
                    "Image artifact event"
                  )}
                </span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {imageGenerationEventSummary.sourceLabel && (
                    <span className="rounded-full border border-primary/30 bg-surface px-2 py-0.5 text-[11px] text-primaryStrong">
                      {imageGenerationEventSummary.sourceLabel}
                    </span>
                  )}
                  {imageGenerationEventSummary.syncLabel && (
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[11px] ${
                        imageGenerationEventSummary.syncStatus === "failed"
                          ? "border-danger/40 bg-danger/10 text-danger"
                          : imageGenerationEventSummary.syncStatus === "synced"
                            ? "border-success/40 bg-success/10 text-success"
                            : "border-primary/30 bg-surface text-primaryStrong"
                      }`}
                    >
                      {imageGenerationEventSummary.syncLabel}
                    </span>
                  )}
                </div>
              </div>
              <p
                data-testid="playground-image-event-prompt"
                className="mt-2 whitespace-pre-wrap text-sm text-text"
              >
                {imageGenerationEventSummary.prompt}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {imageGenerationEventSummary.chips.map((chip, index) => (
                  <span
                    key={`img-event-chip-${index}-${chip}`}
                    className="rounded-full border border-border/70 bg-surface px-2 py-0.5 text-[11px] text-text-muted"
                  >
                    {chip}
                  </span>
                ))}
              </div>
              {imageGenerationEventSummary.refineLabel && (
                <div className="mt-2 text-[11px] text-text-muted">
                  {imageGenerationEventSummary.refineLabel}
                </div>
              )}
              {imageVariantEntries.length > 1 && (
                <div
                  data-testid="playground-image-variant-strip"
                  className="mt-3 rounded-md border border-border/70 bg-surface/50 p-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="font-medium text-text-muted">
                      {String(
                        t(
                          "playground:imageGeneration.eventVariants",
                          "Variants {{current}}/{{total}}",
                          {
                            current: resolvedVariantIndex + 1,
                            total: imageVariantEntries.length
                          } as any
                        )
                      )}
                    </span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {props.onKeepImageVariant && (
                        <button
                          type="button"
                          data-testid="playground-image-variant-keep-active"
                          className="rounded border border-success/35 bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success hover:bg-success/15"
                          onClick={() =>
                            props.onKeepImageVariant?.({
                              messageId: props.messageId,
                              variantIndex: resolvedVariantIndex
                            })
                          }
                        >
                          {t(
                            "playground:imageGeneration.keepActiveVariant",
                            "Keep active"
                          )}
                        </button>
                      )}
                      {props.onDeleteAllImageVariants && (
                        <button
                          type="button"
                          data-testid="playground-image-variant-delete-all"
                          className="rounded border border-danger/35 bg-danger/10 px-2 py-0.5 text-[11px] font-medium text-danger hover:bg-danger/15"
                          onClick={() =>
                            props.onDeleteAllImageVariants?.({
                              messageId: props.messageId
                            })
                          }
                        >
                          {t("playground:imageGeneration.deleteAllVariants", "Delete all")}
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="mt-2 flex flex-wrap items-start gap-2">
                    {imageVariantEntries.map((entry) => {
                      const isActive = entry.index === resolvedVariantIndex
                      const isCompared = compareVariantIndex === entry.index
                      return (
                        <div
                          key={`image-variant-${entry.index}`}
                          className={`rounded border p-1 ${
                            isActive
                              ? "border-primary/60 bg-primary/10"
                              : "border-border/70 bg-surface"
                          }`}
                        >
                          <button
                            type="button"
                            data-testid={`playground-image-variant-select-${entry.index}`}
                            className="flex flex-col items-center gap-1"
                            onClick={() =>
                              props.onSelectImageVariant?.({
                                messageId: props.messageId,
                                variantIndex: entry.index
                              })
                            }
                          >
                            <img
                              src={entry.preview}
                              alt={t(
                                "playground:imageGeneration.variantPreview",
                                "Variant {{index}} preview",
                                { index: entry.index + 1 } as any
                              ) as string}
                              className="h-12 w-12 rounded object-cover"
                              loading="lazy"
                            />
                            <span className="text-[10px] text-text-muted">
                              {String(
                                t("playground:imageGeneration.variantLabel", "V{{index}}", {
                                  index: entry.index + 1
                                } as any)
                              )}
                            </span>
                          </button>
                          <div className="mt-1 flex flex-wrap items-center justify-center gap-1">
                            {!isActive && (
                              <button
                                type="button"
                                data-testid={`playground-image-variant-compare-${entry.index}`}
                                className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-muted hover:bg-surface2"
                                onClick={() =>
                                  setCompareVariantIndex((prev) =>
                                    prev === entry.index ? null : entry.index
                                  )
                                }
                              >
                                {isCompared
                                  ? t(
                                      "playground:imageGeneration.hideCompareVariant",
                                      "Hide compare"
                                    )
                                  : t(
                                      "playground:imageGeneration.compareVariant",
                                      "Compare"
                                    )}
                              </button>
                            )}
                            {props.onDeleteImageVariant && (
                              <button
                                type="button"
                                data-testid={`playground-image-variant-delete-${entry.index}`}
                                className="rounded border border-danger/35 px-1.5 py-0.5 text-[10px] text-danger hover:bg-danger/10"
                                onClick={() =>
                                  props.onDeleteImageVariant?.({
                                    messageId: props.messageId,
                                    variantIndex: entry.index
                                  })
                                }
                              >
                                {t("common:delete", "Delete")}
                              </button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {activeVariantPreview && compareVariantPreview && (
                    <div
                      data-testid="playground-image-variant-compare-preview"
                      className="mt-2 grid gap-2 sm:grid-cols-2"
                    >
                      <div className="rounded border border-border/70 bg-surface p-2">
                        <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-muted">
                          {t("playground:imageGeneration.activeVariant", "Active")}
                        </p>
                        <img
                          src={activeVariantPreview.preview}
                          alt={t(
                            "playground:imageGeneration.activeVariant",
                            "Active"
                          ) as string}
                          className="h-28 w-full rounded object-cover"
                          loading="lazy"
                        />
                      </div>
                      <div className="rounded border border-border/70 bg-surface p-2">
                        <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-muted">
                          {t("playground:imageGeneration.compareVariant", "Compare")}
                        </p>
                        <img
                          src={compareVariantPreview.preview}
                          alt={t(
                            "playground:imageGeneration.compareVariant",
                            "Compare"
                          ) as string}
                          className="h-28 w-full rounded object-cover"
                          loading="lazy"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          {showPartialSaveMarker && (
            <div
              role="status"
              aria-live="polite"
              title={streamTransportInterruptionReason || undefined}
              className="inline-flex items-center rounded-md border border-border/60 bg-surface px-2 py-1 text-[11px] font-medium text-text-muted"
            >
              {t(
                "playground:errorRecovery.partialSavedMarker",
                "Connection dropped. Partial response saved."
              )}
            </div>
          )}
          {interruptedGeneration && !errorPayload && (
            <div
              role="status"
              aria-live="polite"
              className="rounded-md border border-warn/30 bg-warn/10 p-2 text-xs text-warn">
              <p className="font-medium">
                {t(
                  "playground:errorRecovery.interruptedSummary",
                  "Generation was interrupted. You can retry, switch model, or continue from the partial response."
                )}
              </p>
              {interruptionReason && (
                <p className="mt-1 opacity-90">{interruptionReason}</p>
              )}
              {interruptionRecoveryActions.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="sr-only">
                    Recommended next actions:{" "}
                    {interruptionRecoveryActions
                      .map((action) => action.label)
                      .join(", ")}
                  </span>
                  {interruptionRecoveryActions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={action.onClick}
                      className="rounded border border-warn/40 bg-surface px-2 py-1 text-[11px] font-medium text-warn transition hover:bg-warn/10"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="flex flex-grow flex-col">
            {!editMode ? (
              props.isBot ? (
                errorPayload ? (
                  <ErrorBubble
                    payload={errorPayload}
                    toggleLabels={{
                      show: t(
                        "error.showDetails",
                        "Show technical details"
                      ) as string,
                      hide: t(
                        "error.hideDetails",
                        "Hide technical details"
                      ) as string
                    }}
                    recoveryActions={errorRecoveryActions}
                  />
                ) : shouldRenderStreamingPlainText ? (
                  <p
                    data-testid="playground-streaming-plain-text"
                    className={`text-body text-text-muted whitespace-pre-wrap ${assistantTextClass}`}
                  >
                    {props.message}
                  </p>
                ) : renderGreetingMarkdown ? (
                  <React.Suspense
                    fallback={
                      <p
                        className={`text-body text-text-muted ${assistantTextClass}`}>
                        {t("loading.content")}
                      </p>
                    }>
                    <Markdown
                      message={props.message}
                      className={`${MARKDOWN_BASE_CLASSES} ${assistantTextClass}`}
                      searchQuery={props.searchQuery}
                      codeBlockVariant="compact"
                    />
                  </React.Suspense>
                ) : (
                  <>
                    {parseReasoning(props.message).map((e, i) => {
                      if (e.type === "reasoning") {
                        return (
                          <ReasoningBlock
                            key={`reasoning-${i}`}
                            content={e.content}
                            isStreaming={props.isStreaming}
                            reasoningRunning={e.reasoning_running}
                            openReasoning={props.openReasoning}
                            reasoningTimeTaken={props.reasoningTimeTaken}
                            assistantTextClass={assistantTextClass}
                            markdownBaseClasses={MARKDOWN_BASE_CLASSES}
                            searchQuery={props.searchQuery}
                            t={t}
                          />
                        )
                      }

                      return (
                        <React.Suspense
                          key={`message-${i}`}
                          fallback={
                            <p
                              className={`text-body text-text-muted ${assistantTextClass}`}>
                              {t("loading.content")}
                            </p>
                          }>
                          <Markdown
                            message={e.content}
                            className={`${MARKDOWN_BASE_CLASSES} ${assistantTextClass}`}
                            searchQuery={props.searchQuery}
                            codeBlockVariant="github"
                          />
                        </React.Suspense>
                      )
                    })}
                  </>
                )
              ) : (
                <p
                  className={`prose max-w-none dark:prose-invert whitespace-pre-line prose-p:leading-relaxed prose-pre:p-0 dark:prose-dark ${chatTextClass} ${
                    props.message_type &&
                    "italic text-text-muted text-body"
                  }
                  `}>
                  {props.searchQuery
                    ? highlightText(props.message, props.searchQuery)
                    : props.message}
                </p>
              )
            ) : (
              <EditMessageForm
                value={props.message}
                onSumbit={internalEditFormSubmit}
                onClose={() => setEditMode(false)}
                isBot={props.isBot}
              />
            )}
          </div>
          {/* images if available */}
          {props.images &&
            props.images.filter((img) => img.length > 0).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-3">
                {props.images
                  .filter((image) => image.length > 0)
                  .map((image, index) => (
                    <div key={index} className="group relative">
                      <Image
                        src={image}
                        alt="Uploaded Image"
                        width={180}
                        className="rounded-md relative"
                      />
                      {showInlineImageActions && (
                        <div className="pointer-events-none absolute right-2 top-2 flex items-center gap-1 rounded-full border border-border/70 bg-surface/90 px-1 py-1 opacity-0 shadow-sm transition group-hover:opacity-100 group-focus-within:opacity-100">
                          {canRegenerateImage && (
                            <button
                              type="button"
                              className="pointer-events-auto inline-flex h-7 w-7 items-center justify-center rounded-full text-text-muted transition hover:bg-surface2 hover:text-text"
                              aria-label={t(
                                "playground:imageGeneration.regenerateImage",
                                "Regenerate image"
                              ) as string}
                              title={t(
                                "playground:imageGeneration.regenerateImage",
                                "Regenerate image"
                              ) as string}
                              onClick={() => {
                                void props.onRegenerateImage?.({
                                  messageId: props.messageId,
                                  imageIndex: index,
                                  imageUrl: image,
                                  request: imageGenerationMetadata?.request ?? null
                                })
                              }}
                            >
                              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          )}
                          {props.onDeleteImage && (
                            <button
                              type="button"
                              className="pointer-events-auto inline-flex h-7 w-7 items-center justify-center rounded-full text-text-muted transition hover:bg-danger/10 hover:text-danger"
                              aria-label={t(
                                "playground:imageGeneration.deleteImage",
                                "Delete image"
                              ) as string}
                              title={t(
                                "playground:imageGeneration.deleteImage",
                                "Delete image"
                              ) as string}
                              onClick={() => {
                                props.onDeleteImage?.({
                                  messageId: props.messageId,
                                  imageIndex: index,
                                  imageUrl: image
                                })
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}

          {showInlineActions && (
            <MessageActionsBar
              t={t}
              isProMode={isProMode}
              isBot={props.isBot}
              showVariantPager={showVariantPager}
              resolvedVariantIndex={resolvedVariantIndex}
              variantCount={variantCount}
              canSwipePrev={canSwipePrev}
              canSwipeNext={canSwipeNext}
              onSwipePrev={internalSwipePrev}
              onSwipeNext={internalSwipeNext}
              overflowChipVisibility={overflowChipVisibility}
              actionRowVisibility={actionRowVisibility}
              isTtsEnabled={props.isTTSEnabled}
              ttsDisabledReason={ttsDisabledReason}
              ttsActionDisabled={ttsActionDisabled}
              isSpeaking={isSpeaking}
              onToggleTts={handleToggleTts}
              hideCopy={props.hideCopy}
              copyPressed={isBtnPressed}
              onCopy={handleCopy}
              canReply={canReply}
              onReply={handleReply}
              canSaveToWorkspaceNotes={canSaveToWorkspaceNotes}
              onSaveToWorkspaceNotes={handleSaveToWorkspaceNotes}
              canSaveToNotes={canSaveToNotes}
              canSaveToFlashcards={canSaveToFlashcards}
              canGenerateDocument={canGenerateDocument}
              onGenerateDocument={handleGenerateDocument}
              onSaveKnowledge={handleSaveKnowledge}
              savingKnowledge={savingKnowledge}
              generationInfo={props.generationInfo}
              isLastMessage={isLastMessage}
              hideEditAndRegenerate={props.hideEditAndRegenerate}
              onRegenerate={props.onRegenerate}
              onNewBranch={internalNewBranch}
              temporaryChat={props.temporaryChat}
              hideContinue={props.hideContinue}
              onContinue={props.onContinue}
              onRunSteeredContinue={props.onRunSteeredContinue}
              messageSteeringMode={props.messageSteeringMode}
              onMessageSteeringModeChange={props.onMessageSteeringModeChange}
              messageSteeringForceNarrate={props.messageSteeringForceNarrate}
              onMessageSteeringForceNarrateChange={
                props.onMessageSteeringForceNarrateChange
              }
              onClearMessageSteering={props.onClearMessageSteering}
              onEdit={() => setEditMode(true)}
              editMode={editMode}
              showFeedbackControls={showFeedbackControls}
              feedbackSelected={thumb}
              feedbackDisabled={feedbackDisabled}
              feedbackDisabledReason={feedbackDisabledReason}
              isFeedbackSubmitting={isFeedbackSubmitting}
              showThanks={showThanks}
              onThumbUp={handleThumbUp}
              onThumbDown={handleThumbDown}
              onOpenDetails={handleOpenDetails}
              onDelete={props.onDeleteMessage ? handleDelete : undefined}
              canPin={Boolean(props.serverMessageId)}
              isPinned={Boolean(props.pinned)}
              onTogglePinned={internalTogglePinned}
              onQuickMessageAction={
                props.isBot ? handleQuickMessageAction : undefined
              }
            />
          )}

          {/* uploaded documents if available */}
          {/* {props.documents && props.documents.length > 0 && (
            <div className="mt-3">
              <div className="flex flex-wrap gap-2">
                {props.documents.map((doc, index) => (
                  <div
                    key={index}
                    className="inline-flex items-center gap-2 px-3 py-2 bg-primary/10 text-primary rounded-lg text-sm border border-primary/30">
                    <FileIcon className="h-4 w-4" />
                    <div className="flex flex-col">
                      <span className="font-medium">{doc.filename || "Unknown file"}</span>
                      {doc.fileSize && (
                        <span className="text-xs opacity-70">
                          {(doc.fileSize / 1024).toFixed(1)} KB
                          {doc.processed !== undefined && (
                            <span className="ml-2">
                              {doc.processed ? "✓ Processed" : "⚠ Processing..."}
                            </span>
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )} */}

          {/* Tool calls (for assistant messages with function calls) */}
          {props.isBot && props.toolCalls && props.toolCalls.length > 0 && (
            <ToolCallBlock
              toolCalls={props.toolCalls}
              results={props.toolResults}
            />
          )}

          {/* Disco Skills annotation */}
          {props.isBot && skillComment && (
            <DiscoSkillAnnotation
              comment={skillComment}
              onDismiss={() => setSkillComment(null)}
            />
          )}

          {props.isBot && props?.sources && props?.sources.length > 0 && (
            <MessageSourcesSection
              sources={props.sources}
              t={t}
              feedbackDisabled={feedbackDisabled}
              isFeedbackSubmitting={isFeedbackSubmitting}
              sourceFeedback={sourceFeedback}
              submitSourceThumb={submitSourceThumb}
              trackSourcesExpanded={trackSourcesExpanded}
              trackSourceClick={trackSourceClick}
              trackCitationUsed={trackCitationUsed}
              trackDwellTime={trackDwellTime}
              pinnedSourceKeySet={pinnedSourceKeySet}
              resolveSourcePinnedState={resolveSourcePinnedState}
              onAskWithSources={handleAskWithSources}
              onOpenKnowledgePanel={handleOpenKnowledgePanel}
              onSourceClick={props.onSourceClick}
            />
          )}
          </div>
        </div>
        {portraitSide === "right" ? avatarColumn : null}
        {portraitSide === "right" ? portraitPanel : null}
      </div>
      {isAvatarPreviewOpen && portraitImage && (
        <Modal
          open
          onCancel={() => setIsAvatarPreviewOpen(false)}
          footer={null}
          centered
        >
          <Image
            src={portraitImage}
            alt={
              props.isBot
                ? resolvedModelName || props.name
                : userDisplayName.trim() || t("common:you", "You")
            }
            preview={false}
            className="w-full"
          />
        </Modal>
      )}
      {/* </div> */}
      {showFeedbackControls && (
        <FeedbackModal
          open={isFeedbackOpen}
          onClose={() => setIsFeedbackOpen(false)}
          onSubmit={submitDetail}
          isSubmitting={isFeedbackSubmitting}
          initialRating={detail?.rating ?? null}
          initialIssues={detail?.issues ?? []}
          initialNotes={detail?.notes ?? ""}
        />
      )}
      {streamingComplete && (
        <span aria-live="polite" className="sr-only">
          {t("playground:message.responseComplete", { defaultValue: "Response complete" })}
        </span>
      )}
    </article>
  )
})
