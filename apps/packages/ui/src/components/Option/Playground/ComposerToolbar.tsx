import React from "react"
import { useTranslation } from "react-i18next"
import { Tooltip } from "antd"
import { useStorage } from "@plasmohq/storage/hook"
import {
  Globe,
  MicIcon,
  Search,
  FileText,
  FileIcon,
  Gauge,
  ChevronDown
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
import {
  PLAYGROUND_APPEND_FORMATTING_GUIDE_PROMPT_STORAGE_KEY
} from "@/utils/output-formatting-guide"

export type ComposerToolbarProps = {
  isProMode: boolean
  isMobile: boolean
  isConnectionReady: boolean
  isSending: boolean
  modeLauncherButton?: React.ReactNode
  compareControl?: React.ReactNode
  // Row 1: primary selectors (pre-rendered by parent)
  modelSelectButton: React.ReactNode
  mcpControl: React.ReactNode
  // Row action controls (pre-rendered by parent)
  sendControl: React.ReactNode
  attachmentButton: React.ReactNode
  generateButton?: React.ReactNode
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
  contextItems?: ComposerContextItem[]
}

export type ComposerContextItem = {
  id: string
  label: string
  value?: string
  tone?: "neutral" | "active" | "warning"
  onClick?: () => void
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
    modeLauncherButton,
    compareControl,
    modelSelectButton,
    mcpControl,
    sendControl,
    attachmentButton,
    generateButton,
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
    onFocusConnectionCard,
    contextItems = []
  } = props

  const ephemeralDisabled = privateChatLocked || isFireFoxPrivateMode
  const [advancedControlsOpen, setAdvancedControlsOpen] = useStorage(
    "playgroundComposerAdvancedControlsOpen",
    false
  )
  const [casualAdvancedControlsOpen, setCasualAdvancedControlsOpen] =
    useStorage("playgroundComposerCasualAdvancedControlsOpen", false)
  const [appendFormattingGuidePrompt, setAppendFormattingGuidePrompt] =
    useStorage(PLAYGROUND_APPEND_FORMATTING_GUIDE_PROMPT_STORAGE_KEY, false)

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
              ? (t("playground:composer.ephemeralLabel", "Temporary") as string)
              : (t("playground:composer.savedLabel", "Saved") as string)
          }
          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${
            temporaryChat
              ? "bg-primary/10 text-primaryStrong"
              : "text-text-muted"
          } ${ephemeralDisabled ? "cursor-not-allowed opacity-50" : ""}`}
        >
          {temporaryChat
            ? t("playground:composer.ephemeralLabel", "Temporary")
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
      data-testid="knowledge-search-toggle"
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
      aria-label={t("playground:tools.webSearch", "Web search") as string}
      title={t("playground:tools.webSearch", "Web search") as string}
      data-testid="web-search-toggle"
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${
        webSearch
          ? "bg-primary/10 text-primaryStrong"
          : "text-text-muted"
      }`}
    >
      <Globe className="h-3 w-3" />
      <span>{t("playground:actions.webSearchShort", "Web")}</span>
    </button>
  ) : null

  const dictationButton = hasDictation ? (
    <Tooltip title={speechTooltip}>
      <button
        type="button"
        onClick={onDictationToggle}
        disabled={!speechAvailable || voiceChatEnabled}
        data-testid="dictation-button"
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

  const promptSelectControl = (
    <PromptSelect
      selectedSystemPrompt={selectedSystemPrompt}
      setSelectedSystemPrompt={setSelectedSystemPrompt}
      setSelectedQuickPrompt={setSelectedQuickPrompt}
      iconClassName="h-4 w-4"
      className="text-text-muted hover:text-text"
    />
  )

  const characterSelectControl = (
    <CharacterSelect
      showLabel={isProMode ? undefined : false}
      iconClassName="h-4 w-4"
      className="text-text-muted hover:text-text"
    />
  )

  const providerStatusItem = contextItems.find(
    (item) => item.id === "providerStatus"
  )
  const routingPolicyItem = contextItems.find((item) => item.id === "routingPolicy")
  const runtimeSummary = [providerStatusItem?.value, routingPolicyItem?.value]
    .filter((value): value is string => Boolean(value))
    .join(" + ")
  const runtimeTone =
    providerStatusItem?.tone === "warning" || routingPolicyItem?.tone === "warning"
      ? "warning"
      : "active"
  const handleRuntimeChipClick = () => {
    if (providerStatusItem?.onClick) {
      providerStatusItem.onClick()
      return
    }
    if (routingPolicyItem?.onClick) {
      routingPolicyItem.onClick()
      return
    }
    onOpenModelSettings()
  }

  const renderContextItem = (
    item: ComposerContextItem,
    dataTestId?: string
  ) => {
    const baseClasses =
      item.tone === "warning"
        ? "border-warn/40 bg-warn/10 text-warn"
        : item.tone === "active"
          ? "border-primary/40 bg-primary/10 text-primaryStrong"
          : "border-border bg-surface2 text-text-muted"
    const content = (
      <>
        <span className="font-medium">
          {item.label}
        </span>
        {item.value ? (
          <span className="max-w-[150px] truncate text-text">
            {item.value}
          </span>
        ) : null}
      </>
    )

    if (item.onClick) {
      return (
        <button
          key={item.id}
          type="button"
          onClick={item.onClick}
          data-testid={dataTestId}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition hover:bg-surface2 ${baseClasses}`}
          title={
            item.value
              ? `${item.label}: ${item.value}`
              : item.label
          }
        >
          {content}
        </button>
      )
    }

    return (
      <span
        key={item.id}
        data-testid={dataTestId}
        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${baseClasses}`}
        title={
          item.value
            ? `${item.label}: ${item.value}`
            : item.label
        }
      >
        {content}
      </span>
    )
  }

  const modelContextItem = contextItems.find((item) => item.id === "model")
  const casualContextItems = contextItems.filter(
    (item) =>
      item.id !== "model" &&
      item.id !== "providerStatus" &&
      item.id !== "routingPolicy" &&
      item.id !== "temporary"
  )
  const casualModelItem: ComposerContextItem = modelContextItem
    ? {
        ...modelContextItem,
        onClick: modelContextItem.onClick ?? onOpenModelSettings
      }
    : {
        id: "model",
        label: t("playground:composer.context.model", "Model"),
        value: selectedModel ? modelSummaryLabel : t("common:none", "None"),
        tone: selectedModel ? "active" : "warning",
        onClick: onOpenModelSettings
      }
  const casualRuntimeItem: ComposerContextItem | null = runtimeSummary
    ? {
        id: "runtimeStatus",
        label: t("playground:composer.runtime", "Runtime"),
        value: runtimeSummary,
        tone: runtimeTone,
        onClick: handleRuntimeChipClick
      }
    : null

  const persistenceChipClass = temporaryChat
    ? "border-warn/40 bg-warn/10 text-warn"
    : "border-border bg-surface2 text-text-muted"
  const persistenceChipLabel = temporaryChat
    ? (t("playground:composer.ephemeralLabel", "Temporary") as string)
    : (t("playground:composer.savedLabel", "Saved") as string)
  const advancedChipClass = casualAdvancedControlsOpen
    ? "border-primary/40 bg-primary/10 text-primaryStrong"
    : "border-border bg-surface2 text-text-muted"
  const formattingGuideToggleClass = appendFormattingGuidePrompt
    ? "bg-primary/10 text-primaryStrong"
    : "text-text-muted"
  const formattingGuideControl = (
    <button
      type="button"
      onClick={() => setAppendFormattingGuidePrompt(!appendFormattingGuidePrompt)}
      aria-pressed={appendFormattingGuidePrompt}
      data-testid="composer-formatting-guide-toggle"
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition hover:bg-surface2 hover:text-text ${formattingGuideToggleClass}`}
      title={
        t(
          "playground:composer.outputFormattingGuideHint",
          "Append a formatting style guide to the system prompt."
        ) as string
      }
    >
      <FileText className="h-3.5 w-3.5" aria-hidden="true" />
      <span>
        {t("playground:composer.outputFormattingGuide", "Formatting guide")}
      </span>
    </button>
  )

  const casualContextStrip = (
    <div
      data-testid="composer-context-strip"
      aria-label={t("playground:composer.activeContext", "Active context") as string}
      className="flex flex-wrap items-center gap-1.5 border-t border-border/50 pt-2"
    >
      {modelSelectButton ? (
        <span
          data-testid="composer-casual-model-selector-chip"
          className="inline-flex items-center"
        >
          {modelSelectButton}
        </span>
      ) : (
        renderContextItem(casualModelItem)
      )}
      {casualRuntimeItem
        ? renderContextItem(casualRuntimeItem, "composer-casual-runtime-context-chip")
        : null}
      {casualContextItems.map((item) => renderContextItem(item))}
      {modelUsageBadge ? (
        <span
          data-testid="composer-casual-token-chip"
          className="inline-flex items-center gap-1 rounded-full border border-border bg-surface2 px-2 py-0.5 text-[11px] text-text-muted"
        >
          {modelUsageBadge}
        </span>
      ) : null}
      <button
        type="button"
        onClick={() => setCasualAdvancedControlsOpen(!casualAdvancedControlsOpen)}
        aria-expanded={casualAdvancedControlsOpen}
        aria-pressed={casualAdvancedControlsOpen}
        data-testid="composer-casual-advanced-chip"
        className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition hover:bg-surface2 ${advancedChipClass}`}
      >
        <span>{t("playground:composer.advancedControls", "Advanced controls")}</span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${
            casualAdvancedControlsOpen ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        />
      </button>
      <Tooltip title={persistenceTooltip}>
        <span>
          <button
            type="button"
            onClick={() => onToggleTemporaryChat(!temporaryChat)}
            disabled={ephemeralDisabled}
            data-testid="composer-casual-persistence-chip"
            aria-pressed={temporaryChat}
            aria-label={
              temporaryChat
                ? (t("playground:composer.ephemeralLabel", "Temporary") as string)
                : (t("playground:composer.savedLabel", "Saved") as string)
            }
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition hover:bg-surface2 ${persistenceChipClass} ${ephemeralDisabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <span>{persistenceChipLabel}</span>
          </button>
        </span>
      </Tooltip>
    </div>
  )

  const contextStrip =
    contextItems.length > 0 ? (
      <div
        data-testid="composer-context-strip"
        aria-label={t("playground:composer.activeContext", "Active context") as string}
        className="flex flex-wrap items-center gap-1.5 border-t border-border/50 pt-2"
      >
        {contextItems.map((item) => renderContextItem(item))}
      </div>
    ) : null

  const proAdvancedControls =
    isProMode && !isMobile ? (
      <div className="border-t border-border/50 pt-2">
        <button
          type="button"
          onClick={() => setAdvancedControlsOpen(!advancedControlsOpen)}
          aria-expanded={advancedControlsOpen}
          data-testid="composer-advanced-toggle"
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs font-medium text-text-muted transition hover:bg-surface2 hover:text-text"
        >
          <span>
            {t(
              "playground:composer.advancedControls",
              "Advanced controls"
            )}
          </span>
          <ChevronDown
            className={`h-3.5 w-3.5 transition-transform ${
              advancedControlsOpen ? "rotate-180" : ""
            }`}
            aria-hidden="true"
          />
        </button>
        {advancedControlsOpen && (
          <div
            data-playground-toolbar-row="advanced"
            className="mt-2 flex flex-wrap items-center justify-between gap-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <ParameterPresets compact />
              {formattingGuideControl}
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
      </div>
    ) : null

  const mobileToolbarLayout = (
    <div className="flex flex-col gap-2">
      <div
        data-playground-toolbar-row="primary"
        className="flex flex-wrap items-center gap-2"
      >
        {modeLauncherButton}
        <ConnectionStatus showLabel={false} className="px-1 py-0.5" />
        {modelSelectButton}
        {promptSelectControl}
        {characterSelectControl}
        {compareControl}
      </div>
      <div
        data-playground-toolbar-row="actions"
        className="flex items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2">
          {ephemeralToggle}
          {searchContextButton}
          {webSearchButton}
        </div>
        <div className="flex items-center gap-2">
          {modelUsageBadge}
          <ComposerToolbarOverflow
            isProMode={isProMode}
            isConnectionReady={isConnectionReady}
            contextToolsOpen={contextToolsOpen}
            onToggleKnowledgePanel={onToggleKnowledgePanel}
            webSearch={webSearch}
            onToggleWebSearch={onToggleWebSearch}
            hasWebSearch={hasWebSearch}
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
          {voiceChatButton}
          {attachmentButton}
          {generateButton}
          {toolsButton}
          {sendControl}
        </div>
      </div>
    </div>
  )

  const casualToolbarLayout = (
    <div data-playground-toolbar-layout="casual" className="flex flex-col gap-2">
      <div
        data-playground-toolbar-row="actions"
        className="flex flex-nowrap items-center gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <div className="flex flex-nowrap items-center gap-2 text-text-muted">
          {modeLauncherButton}
          {searchContextButton}
          {promptSelectControl}
          {characterSelectControl}
        </div>
        <div className="ml-auto flex flex-nowrap items-center gap-2">
          {compareControl}
          {dictationButton}
          {voiceChatButton}
          {attachmentButton}
          {generateButton}
          {toolsButton}
          {chatSettingsButton}
          {sendControl}
        </div>
      </div>
      {casualAdvancedControlsOpen && (
        <div
          data-playground-toolbar-row="advanced"
          className="rounded-md border border-border/60 bg-surface2/60 p-2"
        >
          <div
            data-testid="composer-casual-advanced-controls-row"
            className="flex flex-nowrap items-center gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <ConnectionStatus showLabel={false} className="px-1 py-0.5" />
            {mcpControl}
            {tabsCountBadge}
            {filesCountBadge}
            <ParameterPresets compact />
            <SystemPromptTemplatesButton onSelect={onTemplateSelect} />
            {formattingGuideControl}
          </div>
        </div>
      )}
    </div>
  )

  const proSplitToolbarLayout = (
    <div data-playground-toolbar-layout="pro-split" className="flex flex-col gap-2">
      <div className="grid gap-2 lg:grid-cols-2">
        <section
          data-testid="composer-pro-context-panel"
          className="rounded-md border border-border/60 bg-surface2/60 p-2"
        >
          <div
            data-playground-toolbar-row="primary"
            className="flex flex-wrap items-center gap-2"
          >
            {modeLauncherButton}
            {compareControl}
            {ephemeralToggle}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-text-muted">
            {searchContextButton}
            {webSearchButton}
            {tabsCountBadge}
            {filesCountBadge}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {promptSelectControl}
            {characterSelectControl}
          </div>
        </section>
        <section
          data-testid="composer-pro-generation-panel"
          className="rounded-md border border-border/60 bg-surface2/60 p-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <ConnectionStatus showLabel={false} className="px-1 py-0.5" />
            {mcpControl}
            {modelSelectButton}
          </div>
          <div
            data-playground-toolbar-row="actions"
            className="mt-2 flex flex-wrap items-center justify-between gap-2"
          >
            <div className="flex flex-wrap items-center gap-2 text-text-muted">
              {dictationButton}
              {modelUsageBadge}
              {chatSettingsButton}
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {voiceChatButton}
              {attachmentButton}
              {generateButton}
              {toolsButton}
              {sendControl}
            </div>
          </div>
        </section>
      </div>
      {proAdvancedControls}
    </div>
  )

  return (
    <div className="mt-2 flex flex-col gap-1">
      {isMobile
        ? mobileToolbarLayout
        : isProMode
          ? proSplitToolbarLayout
          : casualToolbarLayout}

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
      {!isMobile && !isProMode ? casualContextStrip : contextStrip}
    </div>
  )
})
