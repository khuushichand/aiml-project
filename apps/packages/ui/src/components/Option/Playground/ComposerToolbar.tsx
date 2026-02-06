import React from "react"
import { useTranslation } from "react-i18next"
import { Popover, Tooltip } from "antd"
import {
  BookPlus,
  Globe,
  MicIcon,
  Search,
  FileText,
  FileIcon,
  Gauge,
  SlidersHorizontal
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
import type { MessageSteeringMode } from "@/types/message-steering"

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
  messageSteeringMode: MessageSteeringMode
  onMessageSteeringModeChange: (mode: MessageSteeringMode) => void
  messageSteeringForceNarrate: boolean
  onMessageSteeringForceNarrateChange: (enabled: boolean) => void
  onClearMessageSteering: () => void
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

/** Overflow menu item for toolbar actions */
const OverflowItem: React.FC<{
  icon: React.ReactNode
  label: string
  onClick?: () => void
  active?: boolean
  disabled?: boolean
}> = ({ icon, label, onClick, active, disabled }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs transition hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50 ${
      active ? "bg-primary/10 text-primaryStrong" : "text-text hover:text-text"
    }`}
  >
    <span className="flex h-4 w-4 items-center justify-center text-text-subtle">{icon}</span>
    <span>{label}</span>
  </button>
)

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
    messageSteeringMode,
    onMessageSteeringModeChange,
    messageSteeringForceNarrate,
    onMessageSteeringForceNarrateChange,
    onClearMessageSteering,
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
  const [overflowOpen, setOverflowOpen] = React.useState(false)

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

  const steeringActive =
    messageSteeringMode !== "none" || messageSteeringForceNarrate

  const toggleSteeringMode = (mode: MessageSteeringMode) => {
    if (messageSteeringMode === mode) {
      onMessageSteeringModeChange("none")
      return
    }
    onMessageSteeringModeChange(mode)
  }

  const steeringControls = (
    <div className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-surface px-1 py-1">
      <Tooltip
        title={
          t(
            "playground:composer.steering.continueHelp",
            "Single response: continue the user voice."
          ) as string
        }
      >
        <button
          type="button"
          onClick={() => toggleSteeringMode("continue_as_user")}
          aria-pressed={messageSteeringMode === "continue_as_user"}
          className={`rounded px-2 py-1 text-xs transition ${
            messageSteeringMode === "continue_as_user"
              ? "bg-primary/10 text-primaryStrong"
              : "text-text-muted hover:bg-surface2 hover:text-text"
          }`}
        >
          {t("playground:composer.steering.continue", "Continue as user")}
        </button>
      </Tooltip>
      <Tooltip
        title={
          t(
            "playground:composer.steering.impersonateHelp",
            "Single response: write as if authored by the user."
          ) as string
        }
      >
        <button
          type="button"
          onClick={() => toggleSteeringMode("impersonate_user")}
          aria-pressed={messageSteeringMode === "impersonate_user"}
          className={`rounded px-2 py-1 text-xs transition ${
            messageSteeringMode === "impersonate_user"
              ? "bg-primary/10 text-primaryStrong"
              : "text-text-muted hover:bg-surface2 hover:text-text"
          }`}
        >
          {t("playground:composer.steering.impersonate", "Impersonate user")}
        </button>
      </Tooltip>
      <Tooltip
        title={
          t(
            "playground:composer.steering.narrateHelp",
            "Single response: force narration style."
          ) as string
        }
      >
        <button
          type="button"
          onClick={() =>
            onMessageSteeringForceNarrateChange(!messageSteeringForceNarrate)
          }
          aria-pressed={messageSteeringForceNarrate}
          className={`rounded px-2 py-1 text-xs transition ${
            messageSteeringForceNarrate
              ? "bg-primary/10 text-primaryStrong"
              : "text-text-muted hover:bg-surface2 hover:text-text"
          }`}
        >
          {t("playground:composer.steering.narrate", "Force narrate")}
        </button>
      </Tooltip>
      {steeringActive && (
        <Tooltip title={t("common:clear", "Clear") as string}>
          <button
            type="button"
            onClick={onClearMessageSteering}
            className="rounded px-2 py-1 text-xs text-text-muted transition hover:bg-surface2 hover:text-text"
          >
            {t("common:clear", "Clear")}
          </button>
        </Tooltip>
      )}
    </div>
  )

  // --- Mobile overflow menu ---
  const overflowItems = React.useMemo(() => {
    const items: React.ReactNode[] = []
    items.push(
      <OverflowItem
        key="search"
        icon={<Search className="w-3.5 h-3.5" />}
        label={
          contextToolsOpen
            ? (t("playground:composer.contextKnowledgeClose", "Close Search & Context") as string)
            : (t("playground:composer.contextKnowledge", "Search & Context") as string)
        }
        onClick={() => onToggleKnowledgePanel("search")}
        active={contextToolsOpen}
      />
    )
    if (hasWebSearch) {
      items.push(
        <OverflowItem
          key="web"
          icon={<Globe className="w-3.5 h-3.5" />}
          label={t("playground:actions.webSearchOff", "Web search") as string}
          onClick={onToggleWebSearch}
          active={webSearch}
        />
      )
    }
    items.push(
      <OverflowItem
        key="insert"
        icon={<BookPlus className="w-3.5 h-3.5" />}
        label={t("option:promptInsert.useInChat", "Insert prompt") as string}
        onClick={onOpenPromptInsert}
      />
    )
    items.push(
      <OverflowItem
        key="steer-continue"
        icon={<span className="text-xs leading-none">C</span>}
        label={
          t("playground:composer.steering.continue", "Continue as user") as string
        }
        onClick={() =>
          onMessageSteeringModeChange(
            messageSteeringMode === "continue_as_user"
              ? "none"
              : "continue_as_user"
          )
        }
        active={messageSteeringMode === "continue_as_user"}
      />
    )
    items.push(
      <OverflowItem
        key="steer-impersonate"
        icon={<span className="text-xs leading-none">I</span>}
        label={
          t(
            "playground:composer.steering.impersonate",
            "Impersonate user"
          ) as string
        }
        onClick={() =>
          onMessageSteeringModeChange(
            messageSteeringMode === "impersonate_user"
              ? "none"
              : "impersonate_user"
          )
        }
        active={messageSteeringMode === "impersonate_user"}
      />
    )
    items.push(
      <OverflowItem
        key="steer-narrate"
        icon={<span className="text-xs leading-none">N</span>}
        label={
          t("playground:composer.steering.narrate", "Force narrate") as string
        }
        onClick={() =>
          onMessageSteeringForceNarrateChange(!messageSteeringForceNarrate)
        }
        active={messageSteeringForceNarrate}
      />
    )
    if (steeringActive) {
      items.push(
        <OverflowItem
          key="steer-clear"
          icon={<span className="text-xs leading-none">x</span>}
          label={t("common:clear", "Clear") as string}
          onClick={onClearMessageSteering}
        />
      )
    }
    if (hasDictation) {
      const isDictating = speechAvailable &&
        ((speechUsesServer && isServerDictating) ||
          (!speechUsesServer && isListening))
      items.push(
        <OverflowItem
          key="dictation"
          icon={<MicIcon className="w-3.5 h-3.5" />}
          label={
            isDictating
              ? (t("playground:actions.speechStop", "Stop dictation") as string)
              : (t("playground:actions.speechStart", "Start dictation") as string)
          }
          onClick={onDictationToggle}
          active={isDictating}
          disabled={!speechAvailable || voiceChatEnabled}
        />
      )
    }
    items.push(
      <OverflowItem
        key="settings"
        icon={<Gauge className="w-3.5 h-3.5" />}
        label={t("playground:composer.chatSettings", "Chat Settings") as string}
        onClick={onOpenModelSettings}
      />
    )
    if (isProMode && !temporaryChat && !isConnectionReady) {
      items.push(
        <OverflowItem
          key="connect"
          icon={<span className="w-3.5 h-3.5 text-primary">●</span>}
          label={t("playground:composer.persistence.connectToSave", "Connect your server to sync chats.") as string}
          onClick={onFocusConnectionCard}
        />
      )
    }
    return items
  }, [
    contextToolsOpen, onToggleKnowledgePanel, hasWebSearch, webSearch,
    onToggleWebSearch, onOpenPromptInsert, hasDictation, speechAvailable,
    messageSteeringMode,
    messageSteeringForceNarrate,
    onMessageSteeringModeChange,
    onMessageSteeringForceNarrateChange,
    onClearMessageSteering,
    steeringActive,
    speechUsesServer, isServerDictating, isListening, voiceChatEnabled,
    onDictationToggle, onOpenModelSettings, isProMode, temporaryChat,
    isConnectionReady, onFocusConnectionCard, t
  ])

  const mobileOverflowTrigger = isMobile && overflowItems.length > 0 ? (
    <Popover
      open={overflowOpen}
      onOpenChange={setOverflowOpen}
      trigger="click"
      placement="topRight"
      content={
        <div className="flex min-w-[200px] flex-col py-1" onClick={() => setOverflowOpen(false)}>
          {overflowItems}
        </div>
      }
    >
      <button
        type="button"
        aria-label={t("common:moreActions", "More options") as string}
        className="inline-flex h-9 w-9 items-center justify-center rounded-md text-text-muted transition hover:bg-surface2 hover:text-text"
      >
        <SlidersHorizontal className="h-4 w-4" />
      </button>
    </Popover>
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
            {!isMobile && steeringControls}
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
            {mobileOverflowTrigger}
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
