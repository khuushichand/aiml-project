import React from "react"
import { useTranslation } from "react-i18next"
import { ChevronDown, FileText, Send, Loader2, MessageSquarePlus } from "lucide-react"
import { Tag, Tooltip, Input } from "antd"
import { useWorkspaceStore } from "@/store/workspace"
import { useStoreMessageOption } from "@/store/option"
import { useMessageOption } from "@/hooks/useMessageOption"
import { useSmartScroll } from "@/hooks/useSmartScroll"
import { PlaygroundMessage } from "@/components/Common/Playground/Message"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"

const { TextArea } = Input

/**
 * ChatContextIndicator - Shows sources as horizontally scrollable tags
 */
const ChatContextIndicator: React.FC = () => {
  const { t } = useTranslation(["playground"])
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const getSelectedSources = useWorkspaceStore((s) => s.getSelectedSources)
  const selectedSources = getSelectedSources()

  if (selectedSources.length === 0) return null

  return (
    <div className="shrink-0 border-b border-border bg-surface px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="shrink-0 text-xs font-medium text-text-muted">
          <FileText className="mr-1 inline h-3 w-3" />
          {t("playground:chat.usingSourcesLabel", "Sources:")}
        </span>
        {/* Horizontally scrollable source tags */}
        <div className="custom-scrollbar flex min-w-0 flex-1 gap-1.5 overflow-x-auto pb-0.5">
          {selectedSources.map((source) => (
            <Tooltip key={source.id} title={source.title}>
              <Tag
                color="blue"
                className="shrink-0 cursor-default !m-0 max-w-[150px] truncate"
              >
                {source.title}
              </Tag>
            </Tooltip>
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs text-text-muted">
        {t(
          "playground:chat.ragModeHint",
          "Answers will be grounded in your selected sources"
        )}
      </p>
    </div>
  )
}

/**
 * WorkspaceChatEmpty - Empty state for the workspace chat
 */
const WorkspaceChatEmpty: React.FC<{
  hasSelectedSources: boolean
  sourceCount: number
}> = ({ hasSelectedSources, sourceCount }) => {
  const { t } = useTranslation(["playground"])

  return (
    <div className="mx-auto mt-10 max-w-xl px-4">
      <FeatureEmptyState
        icon={MessageSquarePlus}
        title={t("playground:chat.emptyTitle", "Start your research")}
        description={
          hasSelectedSources
            ? t(
                "playground:chat.emptyWithSources",
                "Ask questions about your {{count}} selected source(s)",
                { count: sourceCount }
              )
            : t(
                "playground:chat.emptyNoSources",
                "Select sources from the left pane, then ask questions"
              )
        }
        examples={[
          t("playground:chat.example1", "Summarize the key points from these sources"),
          t("playground:chat.example2", "What are the main arguments presented?"),
          t("playground:chat.example3", "Compare and contrast the different perspectives")
        ]}
      />
    </div>
  )
}

/**
 * SimpleChatInput - A simple chat input component
 */
const SimpleChatInput: React.FC<{
  onSubmit: (message: string) => void
  isLoading: boolean
  placeholder?: string
}> = ({ onSubmit, isLoading, placeholder }) => {
  const { t } = useTranslation(["playground", "common"])
  const [value, setValue] = React.useState("")

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
    setValue("")
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2">
      <div className="relative flex-1">
        <TextArea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || t("playground:chat.inputPlaceholder", "Type a message...")}
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={isLoading}
          className="pr-10 text-sm"
        />
      </div>
      <button
        type="submit"
        disabled={!value.trim() || isLoading}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-white transition hover:bg-primaryStrong disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={t("common:send", "Send")}
      >
        {isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Send className="h-5 w-5" />
        )}
      </button>
    </form>
  )
}

// Generate a stable conversation instance ID for the workspace
const WORKSPACE_CONVERSATION_ID = "workspace-playground-conversation"

/**
 * ChatPane - Middle pane for RAG-powered conversation
 */
export const ChatPane: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])

  // Workspace store
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const getSelectedSources = useWorkspaceStore((s) => s.getSelectedSources)
  const getSelectedMediaIds = useWorkspaceStore((s) => s.getSelectedMediaIds)
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)

  // Message option hook
  const {
    messages,
    streaming,
    isProcessing,
    onSubmit,
    regenerateLastMessage,
    deleteMessage,
    editMessage,
    historyId,
    serverChatId
  } = useMessageOption({})

  // RAG state from store
  const setRagMediaIds = useStoreMessageOption((s) => s.setRagMediaIds)
  const setChatMode = useStoreMessageOption((s) => s.setChatMode)

  // Smart scroll for chat messages
  const { containerRef, isAutoScrollToBottom, autoScrollToBottom } =
    useSmartScroll(messages, streaming, 120)

  // Sync selected sources with RAG context
  React.useEffect(() => {
    const mediaIds = getSelectedMediaIds()
    if (mediaIds.length > 0) {
      setRagMediaIds(mediaIds)
      setChatMode("rag")
    } else {
      setRagMediaIds(null)
      setChatMode("normal")
    }
  }, [selectedSourceIds, getSelectedMediaIds, setRagMediaIds, setChatMode])

  const selectedSources = getSelectedSources()
  const hasMessages = messages.length > 0
  const hasSelectedSources = selectedSources.length > 0

  const handleSubmit = (message: string) => {
    onSubmit({ message, image: "" })
  }

  // Conversation instance ID (use workspace ID or fallback)
  const conversationInstanceId = workspaceId || WORKSPACE_CONVERSATION_ID

  return (
    <div className="flex h-full flex-col">
      {/* Context indicator */}
      <ChatContextIndicator />

      {/* Chat messages area */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          ref={containerRef}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
          aria-label={t("playground:aria.chatTranscript", "Chat messages")}
          className="custom-scrollbar min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-4"
        >
          <div className="mx-auto w-full max-w-3xl pb-6">
            {hasMessages ? (
              <div className="space-y-4 py-4">
                {messages.map((msg, idx) => (
                  <PlaygroundMessage
                    key={msg.id || `msg-${idx}`}
                    isBot={msg.isBot}
                    message={msg.message}
                    name={msg.name}
                    images={msg.images}
                    generationInfo={msg.generationInfo}
                    sources={msg.sources}
                    toolCalls={msg.toolCalls}
                    toolResults={msg.toolResults}
                    reasoningTimeTaken={msg.reasoning_time_taken}
                    currentMessageIndex={idx}
                    totalMessages={messages.length}
                    isProcessing={isProcessing}
                    isStreaming={streaming && idx === messages.length - 1}
                    conversationInstanceId={conversationInstanceId}
                    historyId={historyId || undefined}
                    serverChatId={serverChatId}
                    serverMessageId={msg.serverMessageId}
                    messageId={msg.id}
                    createdAt={msg.createdAt}
                    variants={msg.variants}
                    activeVariantIndex={msg.activeVariantIndex}
                    modelName={msg.modelName}
                    modelImage={msg.modelImage}
                    onRegenerate={
                      msg.isBot && idx === messages.length - 1
                        ? () => regenerateLastMessage()
                        : () => {}
                    }
                    onDeleteMessage={() => deleteMessage(idx)}
                    onEditFormSubmit={(value, isSend) => {
                      editMessage(idx, value, !msg.isBot, isSend)
                    }}
                    hideEditAndRegenerate={!msg.isBot && idx !== messages.length - 1}
                    hideContinue={true}
                    temporaryChat={false}
                  />
                ))}
              </div>
            ) : (
              <WorkspaceChatEmpty
                hasSelectedSources={hasSelectedSources}
                sourceCount={selectedSources.length}
              />
            )}
          </div>
        </div>

        {/* Scroll to bottom button */}
        {!isAutoScrollToBottom && hasMessages && (
          <div className="pointer-events-none absolute bottom-24 left-0 right-0 flex justify-center">
            <button
              onClick={() => autoScrollToBottom()}
              aria-label={t(
                "playground:composer.scrollToLatest",
                "Scroll to latest messages"
              )}
              title={
                t(
                  "playground:composer.scrollToLatest",
                  "Scroll to latest messages"
                ) as string
              }
              className="pointer-events-auto rounded-full border border-border bg-surface p-2 text-text-subtle shadow-card transition-colors hover:bg-surface2 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <ChevronDown className="size-4 text-text-subtle" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      {/* Chat input */}
      <div className="sticky bottom-0 border-t border-border bg-surface">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <SimpleChatInput
            onSubmit={handleSubmit}
            isLoading={streaming}
            placeholder={
              hasSelectedSources
                ? t(
                    "playground:chat.inputPlaceholderWithSources",
                    "Ask about your sources..."
                  )
                : t(
                    "playground:chat.inputPlaceholder",
                    "Type a message..."
                  )
            }
          />
        </div>
      </div>
    </div>
  )
}

export default ChatPane
