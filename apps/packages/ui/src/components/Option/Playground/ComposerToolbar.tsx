import React from "react"
import { useTranslation } from "react-i18next"
import { Tooltip } from "antd"
import {
  BookPlus,
  Globe,
  MicIcon,
  Search,
  FileText,
  FileIcon,
  Gauge
} from "lucide-react"
import { PromptSelect } from "@/components/Common/PromptSelect"
import { CharacterSelect } from "@/components/Common/CharacterSelect"
import { Button as TldwButton } from "@/components/Common/Button"
import { ConnectionStatus } from "@/components/Layouts/ConnectionStatus"
import {
  ParameterPresets,
  SystemPromptTemplatesButton,
  SessionCostEstimation,
  type PromptTemplate
} from "./playground-features"
import { ComposerToolbarOverflow } from "./ComposerToolbarOverflow"

export type ComposerToolbarProps = {
  isProMode: boolean
  isMobile: boolean
  isConnectionReady: boolean
  isSending: boolean
  // Row 1: primary selectors (pre-rendered by parent)
  modelSelectButton: React.ReactNode
  mcpControl: React.ReactNode
  // Row action controls (pre-rendered by parent)
  sendControl: React.ReactNode
  attachmentButton: React.ReactNode
  toolsButton: React.ReactNode
  voiceChatButton: React.ReactNode
  modelUsageBadge: React.ReactNode
  // Prompt select
  selectedSystemPrompt: string | undefined
  setSelectedSystemPrompt: (id: string | undefined) => void
  setSelectedQuickPrompt: (prompt: string | undefined) => void
  // Ephemeral toggle
  temporaryChat: boolean
  onToggleTemporaryChat: (next: boolean) => void
  privateChatLocked: boolean
  isFireFoxPrivateMode: boolean
  persistenceTooltip: React.ReactNode
  // Knowledge / context
  contextToolsOpen: boolean
  onToggleKnowledgePanel: (tab: string) => void
  // Web search
  webSearch: boolean
  onToggleWebSearch: () => void
  hasWebSearch: boolean
  // Insert prompt
  onOpenPromptInsert: () => void
  // Model settings
  onOpenModelSettings: () => void
  modelSummaryLabel: string
  promptSummaryLabel: string
  // Dictation
  hasDictation: boolean
  speechAvailable: boolean
  speechUsesServer: boolean
  isListening: boolean
  isServerDictating: boolean
  voiceChatEnabled: boolean
  speechTooltip: string
  onDictationToggle: () => void
  // Pro-only: parameter presets & templates
  onTemplateSelect: (template: PromptTemplate) => void
  // Pro-only: cost estimation
  selectedModel: string | null
  resolvedProviderKey: string
  messages: any[]
  // Pro-only: context counts
  selectedDocumentsCount: number
  uploadedFilesCount: number
  // Persistence hints
  serverChatId: string | null
  showServerPersistenceHint: boolean
  onDismissServerPersistenceHint: () => void
  onFocusConnectionCard: () => void
}

/**
 * Unified toolbar for the chat composer.
 * Renders all controls once and uses `isProMode` for layout differences.
 * On mobile, secondary controls collapse into an overflow popover.
 */
export const ComposerToolbar = React.memo(function ComposerToolbar(
  props: ComposerToolbarProps
) {
  const { t } = useTranslation(["playground", "common", "option", "sidepanel", "settings"])
  const {
    isProMode,
    isMobile,
    isConnectionReady,
    modelSelectButton,
    mcpControl,
    sendControl,
    attachmentButton,
    toolsButton,
    voiceChatButton,
    modelUsageBadge,
    selectedSystemPrompt,
    setSelectedSystemPrompt,
    setSelectedQuickPrompt,
    temporaryChat,
    onToggleTemporaryChat,
    privateChatLocked,
    isFireFoxPrivateMode,
    persistenceTooltip,
    contextToolsOpen,
    onToggleKnowledgePanel,
    webSearch,
    onToggleWebSearch,
    hasWebSearch,
    onOpenPromptInsert,
    onOpenModelSettings,
    modelSummaryLabel,
    promptSummaryLabel,
    hasDictation,
    speechAvailable,
    speechUsesServer,
    isListening,
    isServerDictating,
    voiceChatEnabled,
    speechTooltip,
    onDictationToggle,
    onTemplateSelect,
    selectedModel,
    resolvedProviderKey,
    messages,
    selectedDocumentsCount,
    uploadedFilesCount,
    serverChatId,
    showServerPersistenceHint,
    onDismissServerPersistenceHint,
    onFocusConnectionCard
  } = props

  const ephemeralDisabled = privateChatLocked || isFireFoxPrivateMode

  // --- Shared sub-elements ---
  const ephemeralToggle = (
    <Tooltip title={persistenceTooltip}>
      <span>
        <button
          type="button"
          onClick={() => onToggleTemporaryChat(!temporaryChat)}
          disabled={ephemeralDisabled}
          aria-pressed={temporaryChat}
          aria-label={
            temporaryChat
              ? (t("playground:composer.ephemeralLabel", "Ephemeral") as string)
              : (t("playground:composer.savedLabel", "Saved") as string)
          }
          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${
            temporaryChat
              ? "bg-primary/10 text-primaryStrong"
              : "text-text-muted"
          } ${ephemeralDisabled ? "cursor-not-allowed opacity-50" : ""}`}
        >
          {temporaryChat
            ? t("playground:composer.ephemeralLabel", "Ephemeral")
            : t("playground:composer.savedLabel", "Saved")}
        </button>
      </span>
    </Tooltip>
  )

  const searchContextButton = (
    <button
      type="button"
      onClick={() => onToggleKnowledgePanel("search")}
      title={
        contextToolsOpen
          ? (t("playground:composer.contextKnowledgeClose", "Close Search & Context") as string)
          : (t("playground:composer.contextKnowledge", "Search & Context") as string)
      }
      aria-pressed={contextToolsOpen}
      aria-expanded={contextToolsOpen}
      aria-label={
        contextToolsOpen
          ? (t("playground:composer.contextKnowledgeClose", "Close Search & Context") as string)
          : (t("playground:composer.contextKnowledge", "Search & Context") as string)
      }
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${
        contextToolsOpen
          ? "bg-primary/10 text-primaryStrong"
          : "text-text-muted"
      }`}
    >
      <Search className="h-3 w-3" />
      <span className={isProMode ? "" : "truncate"}>
        {contextToolsOpen
          ? t("playground:composer.contextKnowledgeClose", "Close Search & Context")
          : t("playground:composer.contextKnowledge", "Search & Context")}
      </span>
    </button>
  )

  const webSearchButton = hasWebSearch ? (
    <button
      type="button"
      onClick={onToggleWebSearch}
      aria-pressed={webSearch}
      aria-label={
        webSearch
          ? (t("playground:actions.webSearchOn", "Web search on") as string)
          : (t("playground:actions.webSearchOff", "Web search off") as string)
      }
      title={t("playground:actions.webSearchOff", "Web search") as string}
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${
        webSearch
          ? "bg-primary/10 text-primaryStrong"
          : "text-text-muted"
      }`}
    >
      <Globe className="h-3 w-3" />
      <span>{t("playground:actions.webSearchOff", "Web")}</span>
    </button>
  ) : null

  const insertPromptButton = (
    <Tooltip title={t("option:promptInsert.useInChat", "Insert prompt") as string}>
      <button
        type="button"
        onClick={onOpenPromptInsert}
        aria-label={t("option:promptInsert.useInChat", "Insert prompt") as string}
        className={`inline-flex items-center justify-center rounded-md text-xs text-text-muted transition hover:bg-surface2 hover:text-text ${
          isProMode ? "gap-1 px-2 py-1" : "h-9 w-9"
        }`}
      >
        <BookPlus className="h-4 w-4" />
        {isProMode && (
          <span className="hidden text-xs font-medium sm:inline">
            {t("option:promptInsert.useInChat", "Insert prompt")}
          </span>
        )}
      </button>
    </Tooltip>
  )

  const dictationButton = hasDictation ? (
    <Tooltip title={speechTooltip}>
      <button
        type="button"
        onClick={onDictationToggle}
        disabled={!speechAvailable || voiceChatEnabled}
        className={`inline-flex items-center justify-center rounded-md text-xs transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50 ${
          speechAvailable &&
          ((speechUsesServer && isServerDictating) ||
            (!speechUsesServer && isListening))
            ? "text-primaryStrong"
            : "text-text-muted"
        } ${isProMode ? "px-2 py-1" : "h-9 w-9 p-0"}`}
        aria-label={
          !speechAvailable
            ? (t("playground:actions.speechUnavailableTitle", "Dictation unavailable") as string)
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
  ) : null

  const chatSettingsButton = isProMode ? (
    <Tooltip title={t("common:currentChatModelSettings") as string}>
      <button
        type="button"
        onClick={onOpenModelSettings}
        aria-label={t("common:currentChatModelSettings") as string}
        className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs text-text transition hover:bg-surface2"
      >
        <Gauge className="h-4 w-4" aria-hidden="true" />
        <span className="flex flex-col items-start text-left">
          <span className="font-medium">
            {t("playground:composer.chatSettings", "Chat Settings")}
          </span>
          <span className="text-xs text-text-muted">
            {modelSummaryLabel} • {promptSummaryLabel}
          </span>
        </span>
      </button>
    </Tooltip>
  ) : (
    <Tooltip title={t("common:currentChatModelSettings") as string}>
      <TldwButton
        variant="outline"
        shape="pill"
        iconOnly
        onClick={onOpenModelSettings}
        ariaLabel={t("common:currentChatModelSettings") as string}
        className="text-text-muted"
      >
        <Gauge className="h-4 w-4" aria-hidden="true" />
        <span className="sr-only">
          {t("playground:composer.chatSettings", "Chat Settings")}
        </span>
      </TldwButton>
    </Tooltip>
  )

  const tabsCountBadge =
    isProMode && selectedDocumentsCount > 0 ? (
      <button
        type="button"
        onClick={() => {
          const chips = document.querySelector<HTMLElement>(
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
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
      >
        <FileText className="h-3 w-3 text-text-subtle" />
        <span>
          {t("playground:composer.contextTabs", {
            defaultValue: "{{count}} tabs",
            count: selectedDocumentsCount
          } as any) as string}
        </span>
      </button>
    ) : null

  const filesCountBadge =
    isProMode && uploadedFilesCount > 0 ? (
      <button
        type="button"
        onClick={() => {
          const files = document.querySelector<HTMLElement>(
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
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
      >
        <FileIcon className="h-3 w-3 text-text-subtle" />
        <span>
          {t("playground:composer.contextFiles", {
            defaultValue: "{{count}} files",
            count: uploadedFilesCount
          } as any) as string}
        </span>
      </button>
    ) : null

  return (
    <div className="mt-2 flex flex-col gap-1">
      {/* Row 1: Primary selectors - always present */}
      <div className={`flex flex-col gap-2 ${isProMode ? "mt-1" : ""}`}>
        <div className="flex flex-wrap items-center gap-2">
          <PromptSelect
            selectedSystemPrompt={selectedSystemPrompt}
            setSelectedSystemPrompt={setSelectedSystemPrompt}
            setSelectedQuickPrompt={setSelectedQuickPrompt}
            iconClassName="h-4 w-4"
            className="text-text-muted hover:text-text"
          />
          {modelSelectButton}
          <CharacterSelect
            showLabel={isProMode ? undefined : false}
            iconClassName="h-4 w-4"
            className="text-text-muted hover:text-text"
          />
          {!isMobile && mcpControl}
        </div>

        {/* Row 2 (Pro-only): Enhanced features */}
        {isProMode && !isMobile && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 pt-2">
            <div className="flex flex-wrap items-center gap-2">
              <ParameterPresets compact />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <SystemPromptTemplatesButton onSelect={onTemplateSelect} />
              {messages.length > 0 && (
                <SessionCostEstimation
                  modelId={selectedModel}
                  provider={resolvedProviderKey}
                  messages={messages}
                />
              )}
            </div>
          </div>
        )}

        {/* Row 3: Toggles + action controls */}
        <div className={`flex ${isProMode ? "flex-col gap-2 md:flex-row md:items-center md:justify-between" : "items-center justify-between gap-2"}`}>
          <div className={`flex items-center gap-2 ${isProMode ? "flex-wrap text-text-muted" : "flex-nowrap"}`}>
            <ConnectionStatus showLabel={false} className="px-1 py-0.5" />
            {ephemeralToggle}
            {/* Desktop: show inline; Mobile: hidden (in overflow) */}
            {!isMobile && searchContextButton}
            {!isMobile && webSearchButton}
            {!isMobile && tabsCountBadge}
            {!isMobile && filesCountBadge}
          </div>
          <div className={`flex items-center gap-3 ${isProMode ? "flex-wrap justify-end" : "gap-2 flex-nowrap"}`}>
            {/* Desktop: show inline; Mobile: hidden (in overflow) */}
            {!isMobile && insertPromptButton}
            {!isMobile && dictationButton}
            {!isMobile && modelUsageBadge}
            {!isMobile && chatSettingsButton}
            {isMobile && (
              <ComposerToolbarOverflow
                isProMode={isProMode}
                isConnectionReady={isConnectionReady}
                contextToolsOpen={contextToolsOpen}
                onToggleKnowledgePanel={onToggleKnowledgePanel}
                webSearch={webSearch}
                onToggleWebSearch={onToggleWebSearch}
                hasWebSearch={hasWebSearch}
                onOpenPromptInsert={onOpenPromptInsert}
                onOpenModelSettings={onOpenModelSettings}
                hasDictation={hasDictation}
                speechAvailable={speechAvailable}
                speechUsesServer={speechUsesServer}
                isListening={isListening}
                isServerDictating={isServerDictating}
                voiceChatEnabled={voiceChatEnabled}
                onDictationToggle={onDictationToggle}
                temporaryChat={temporaryChat}
                onFocusConnectionCard={onFocusConnectionCard}
              />
            )}
            {voiceChatButton}
            {attachmentButton}
            {toolsButton}
            {sendControl}
          </div>
        </div>

        {/* Pro-only: persistence hints (desktop only) */}
        {!isMobile && isProMode && !temporaryChat && !isConnectionReady && (
          <button
            type="button"
            onClick={onFocusConnectionCard}
            title={
              t(
                "playground:composer.persistence.connectToSave",
                "Connect your server to sync chats."
              ) as string
            }
            className="inline-flex w-fit items-center gap-1 text-xs font-medium text-primary hover:text-primaryStrong"
          >
            {t(
              "playground:composer.persistence.connectToSave",
              "Connect your server to sync chats."
            )}
          </button>
        )}
        {isProMode && !temporaryChat && serverChatId && showServerPersistenceHint && (
          <p className="max-w-md text-xs text-text-muted">
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
              onClick={onDismissServerPersistenceHint}
              title={t("common:dismiss", "Dismiss") as string}
              className="ml-1 text-xs font-medium text-primary hover:text-primaryStrong"
            >
              {t("common:dismiss", "Dismiss")}
            </button>
          </p>
        )}
      </div>
    </div>
  )
})
