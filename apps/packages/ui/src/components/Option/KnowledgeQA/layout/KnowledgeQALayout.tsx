import React, { useEffect, useMemo, useRef } from "react"
import { Download, PanelLeftOpen, PanelLeftClose } from "lucide-react"
import { cn } from "@/libs/utils"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { isKnowledgeQaHistoryItem, sortHistoryNewestFirst } from "../historyUtils"
import { KnowledgeContextBar } from "../context/KnowledgeContextBar"
import { CompactToolbar } from "../context/CompactToolbar"
import { KnowledgeComposer } from "../composer/KnowledgeComposer"
import { KnowledgeReadyState } from "../empty/KnowledgeReadyState"
import { AnswerWorkspace } from "../panels/AnswerWorkspace"
import { useLayoutMode } from "../hooks/useLayoutMode"
import { useMobile } from "@/hooks/useMediaQuery"

const LazyHistoryPane = React.lazy(() =>
  import("../history/HistoryPane").then((module) => ({ default: module.HistoryPane })),
)
const LazyInlineRecentSessions = React.lazy(() =>
  import("../empty/InlineRecentSessions").then((module) => ({
    default: module.InlineRecentSessions,
  })),
)
const LazyNoResultsRecovery = React.lazy(() =>
  import("../panels/NoResultsRecovery").then((module) => ({
    default: module.NoResultsRecovery,
  })),
)
const LazyEvidenceRail = React.lazy(() =>
  import("../evidence/EvidenceRail").then((module) => ({ default: module.EvidenceRail })),
)

type KnowledgeQALayoutProps = {
  onExportClick: () => void
}

const READY_STATE_SUGGESTIONS = [
  "Explain the methodology used in this study",
  "Summarize the key findings in my latest sources",
  "What claims have direct citations?",
  "Compare conclusions across my documents",
]

const READY_STATE_ONBOARDING_SUGGESTIONS = [
  "How do I add my first source?",
  "What file types can I search here?",
  "Try a web-first search about this topic",
  "Show me an example of a cited answer",
]

function normalizeSourceSet(values: string[]): string {
  return [...values].sort((left, right) => left.localeCompare(right)).join("|")
}

function normalizeNumberSet(values: Array<number | null | undefined>): string {
  return values
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    .map((value) => Math.round(value))
    .sort((left, right) => left - right)
    .join("|")
}

function normalizeStringSet(values: Array<string | null | undefined>): string {
  return values
    .filter((value): value is string => typeof value === "string" && value.trim().length > 0)
    .map((value) => value.trim())
    .sort((left, right) => left.localeCompare(right))
    .join("|")
}

function hasConversationId(item: { conversationId?: string }): boolean {
  return (
    typeof item.conversationId === "string" &&
    item.conversationId.trim().length > 0
  )
}

function hasQueryText(item: { query?: string }): boolean {
  return typeof item.query === "string" && item.query.trim().length > 0
}

function getLatestUserTurnKey(
  messages: Array<{ id?: string; role?: string; content?: string }>
): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.role !== "user") continue
    if (typeof message.id === "string" && message.id.trim().length > 0) {
      return `id:${message.id.trim()}`
    }
    if (typeof message.content === "string" && message.content.trim().length > 0) {
      return `content:${message.content.trim()}`
    }
    return `index:${index}`
  }
  return null
}

export function KnowledgeQALayout({ onExportClick }: KnowledgeQALayoutProps) {
  const knowledgeQa = useKnowledgeQA()
  const results = knowledgeQa.results ?? []
  const answer = knowledgeQa.answer ?? null
  const citations = knowledgeQa.citations ?? []
  const hasSearched = knowledgeQa.hasSearched ?? false
  const isSearching = knowledgeQa.isSearching ?? false
  const error = knowledgeQa.error ?? null
  const queryStage = knowledgeQa.queryStage ?? "idle"
  const preset = knowledgeQa.preset ?? "balanced"
  const setPreset = knowledgeQa.setPreset ?? (() => undefined)
  const settings = knowledgeQa.settings ?? {
    sources: [],
    enable_web_fallback: true,
    top_k: 10,
    include_media_ids: [],
    include_note_ids: [],
  }
  const updateSetting =
    knowledgeQa.updateSetting ??
    (() => undefined as unknown as void)
  const setSettingsPanelOpen = knowledgeQa.setSettingsPanelOpen ?? (() => undefined)
  const setQuery = knowledgeQa.setQuery ?? (() => undefined)
  const restoreFromHistory =
    knowledgeQa.restoreFromHistory ?? (async () => undefined)
  const searchHistory = knowledgeQa.searchHistory ?? []
  const messages = knowledgeQa.messages ?? []
  const evidenceRailOpen = knowledgeQa.evidenceRailOpen ?? false
  const canControlEvidence = typeof knowledgeQa.setEvidenceRailOpen === "function"
  const setEvidenceRailOpen = knowledgeQa.setEvidenceRailOpen ?? (() => undefined)
  const evidenceRailTab = knowledgeQa.evidenceRailTab ?? "sources"
  const setEvidenceRailTab = knowledgeQa.setEvidenceRailTab ?? (() => undefined)
  const lastSearchScope = knowledgeQa.lastSearchScope ?? null
  const pinnedSourceFilters = knowledgeQa.pinnedSourceFilters ?? {
    mediaIds: [],
    noteIds: [],
  }
  const focusSource = knowledgeQa.focusSource ?? (() => undefined)
  const settingsPanelOpen = knowledgeQa.settingsPanelOpen ?? false

  const isMobile = useMobile()
  const { mode, setLayoutMode, isSimple, isResearch, showPromotionToast, dismissPromotion, acceptPromotion } =
    useLayoutMode({ messageCount: messages.length })

  // Mobile always forces simple mode layout (no sidebars)
  const effectiveSimple = isMobile || isSimple

  // Track whether user manually closed the evidence rail for this search
  const userClosedRailRef = useRef(false)
  const latestUserTurnKeyRef = useRef<string | null>(null)

  const hasResults = results.length > 0 || Boolean(answer)
  const showNoResultsState =
    hasSearched && !isSearching && !error && results.length === 0 && !answer
  const hasVisibleResultsArea =
    hasResults || showNoResultsState || Boolean(error) || isSearching
  const recentHistoryItem = useMemo(() => {
    const sortedHistory = sortHistoryNewestFirst(searchHistory)
    const recentKnowledgeThreadItem = sortedHistory.find(
      (item) => isKnowledgeQaHistoryItem(item) && hasConversationId(item)
    )
    const recentKnowledgeQueryItem = sortedHistory.find(
      (item) => isKnowledgeQaHistoryItem(item) && hasQueryText(item)
    )
    return (
      recentKnowledgeThreadItem ||
      recentKnowledgeQueryItem ||
      sortedHistory.find(hasConversationId) ||
      sortedHistory.find(hasQueryText) ||
      null
    )
  }, [searchHistory])

  const recentSessions = useMemo(() => {
    return sortHistoryNewestFirst(searchHistory)
      .filter((item) => isKnowledgeQaHistoryItem(item) && hasQueryText(item))
      .slice(0, 5)
  }, [searchHistory])

  const isEvidenceRailOpen = canControlEvidence
    ? evidenceRailOpen
    : hasVisibleResultsArea
  const readyStateSuggestions =
    settings.sources.length > 0
      ? READY_STATE_SUGGESTIONS
      : READY_STATE_ONBOARDING_SUGGESTIONS

  const contextChangedSinceLastRun = useMemo(() => {
    if (!lastSearchScope) return false
    const currentMediaScope = [
      ...(Array.isArray(settings.include_media_ids) ? settings.include_media_ids : []),
      ...pinnedSourceFilters.mediaIds,
    ]
    const currentNoteScope = [
      ...(Array.isArray(settings.include_note_ids) ? settings.include_note_ids : []),
      ...pinnedSourceFilters.noteIds,
    ]
    return (
      lastSearchScope.preset !== preset ||
      lastSearchScope.webFallback !== settings.enable_web_fallback ||
      normalizeSourceSet(lastSearchScope.sources) !== normalizeSourceSet(settings.sources) ||
      normalizeNumberSet(lastSearchScope.includeMediaIds ?? []) !==
        normalizeNumberSet(currentMediaScope) ||
      normalizeStringSet(lastSearchScope.includeNoteIds ?? []) !==
        normalizeStringSet(currentNoteScope)
    )
  }, [
    lastSearchScope,
    pinnedSourceFilters.mediaIds,
    pinnedSourceFilters.noteIds,
    preset,
    settings.enable_web_fallback,
    settings.include_media_ids,
    settings.include_note_ids,
    settings.sources,
  ])
  const latestUserTurnKey = useMemo(() => getLatestUserTurnKey(messages), [messages])

  useEffect(() => {
    if (latestUserTurnKeyRef.current === latestUserTurnKey) {
      return
    }
    latestUserTurnKeyRef.current = latestUserTurnKey
    if (latestUserTurnKey) {
      userClosedRailRef.current = false
    }
  }, [latestUserTurnKey])

  useEffect(() => {
    if (
      hasResults &&
      queryStage !== "searching" &&
      !settingsPanelOpen &&
      !evidenceRailOpen &&
      !userClosedRailRef.current
    ) {
      setEvidenceRailOpen(true)
    }
    if (!hasResults) {
      userClosedRailRef.current = false
      return
    }
  }, [
    evidenceRailOpen,
    hasResults,
    queryStage,
    setEvidenceRailOpen,
    settingsPanelOpen,
  ])

  useEffect(() => {
    if (settingsPanelOpen && evidenceRailOpen) {
      setEvidenceRailOpen(false)
    }
  }, [settingsPanelOpen, evidenceRailOpen, setEvidenceRailOpen])

  const focusSearchInput = () => {
    const input = document.getElementById(
      "knowledge-search-input"
    ) as HTMLInputElement | null
    if (!input) return
    input.focus()
    input.setSelectionRange(input.value.length, input.value.length)
  }

  const handleSuggestedPrompt = (prompt: string) => {
    setQuery(prompt)
    focusSearchInput()
  }

  const handleBroadenScope = () => {
    updateSetting("top_k", Math.min(50, Math.max(settings.top_k + 5, 10)))
    setSettingsPanelOpen(true)
  }

  const handleEnableWeb = () => {
    if (!settings.enable_web_fallback) {
      updateSetting("enable_web_fallback", true)
    }
  }

  const handleShowNearestMatches = () => {
    setEvidenceRailOpen(true)
    setEvidenceRailTab("sources")
    if (results.length > 0) {
      focusSource(0)
    }
  }

  const handleOpenSourceSelector = () => {
    // In simple mode, open settings panel instead of inline source toggle
    if (effectiveSimple) {
      setSettingsPanelOpen(true)
      return
    }
    const sourceSelectorButton = document.getElementById(
      "knowledge-source-selector-toggle"
    ) as HTMLButtonElement | null
    if (sourceSelectorButton) {
      sourceSelectorButton.focus()
      sourceSelectorButton.click()
      return
    }
    setSettingsPanelOpen(true)
  }

  return (
    <div className="relative flex h-full min-h-0">
      <a
        href="#knowledge-search-input"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm text-text focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:ring-2 focus:ring-primary"
      >
        Skip to search
      </a>

      {/* History sidebar - only in Research mode (desktop) */}
      {!effectiveSimple && (
        <aside
          aria-label="Search history"
          className="transition-all duration-300"
        >
          <React.Suspense fallback={null}>
            <LazyHistoryPane />
          </React.Suspense>
        </aside>
      )}

      <main className="flex min-w-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          <div
            data-testid="knowledge-search-shell"
            className={cn(
              "transition-all duration-300",
              effectiveSimple && !hasVisibleResultsArea
                ? "mx-auto flex flex-1 w-full max-w-3xl items-center justify-center px-4 py-10 md:px-6"
                : effectiveSimple
                  ? "mx-auto w-full max-w-3xl px-4 pt-6 pb-4 md:px-6"
                  : "px-4 pt-6 pb-4 md:px-6"
            )}
          >
            <div className={cn(
              "w-full space-y-4",
              effectiveSimple ? "" : "mx-auto max-w-4xl"
            )}>
              {/* Compact toolbar in Simple mode, full context bar in Research mode */}
              {effectiveSimple ? (
                <CompactToolbar
                  sources={settings.sources}
                  preset={preset}
                  webEnabled={settings.enable_web_fallback}
                  onToggleWeb={() =>
                    updateSetting("enable_web_fallback", !settings.enable_web_fallback)
                  }
                  onOpenSourceSelector={handleOpenSourceSelector}
                  onOpenSettings={() => setSettingsPanelOpen(true)}
                  contextChangedSinceLastRun={contextChangedSinceLastRun}
                />
              ) : (
                <KnowledgeContextBar
                  preset={preset}
                  onPresetChange={setPreset}
                  sources={settings.sources}
                  onSourcesChange={(sources) => updateSetting("sources", sources)}
                  includeMediaIds={Array.isArray(settings.include_media_ids) ? settings.include_media_ids : []}
                  onIncludeMediaIdsChange={(ids) => updateSetting("include_media_ids", ids)}
                  includeNoteIds={
                    Array.isArray(settings.include_note_ids) ? settings.include_note_ids : []
                  }
                  onIncludeNoteIdsChange={(ids) => updateSetting("include_note_ids", ids)}
                  webEnabled={settings.enable_web_fallback}
                  onToggleWeb={() =>
                    updateSetting("enable_web_fallback", !settings.enable_web_fallback)
                  }
                  contextChangedSinceLastRun={contextChangedSinceLastRun}
                  onOpenSettings={() => setSettingsPanelOpen(true)}
                />
              )}

              {!hasVisibleResultsArea ? (
                <>
                  <KnowledgeReadyState
                    suggestedPrompts={readyStateSuggestions}
                    onPromptClick={handleSuggestedPrompt}
                    onContinueRecent={() => {
                      if (recentHistoryItem) {
                        void restoreFromHistory(recentHistoryItem)
                      }
                    }}
                    onSelectSources={handleOpenSourceSelector}
                    hasSources={settings.sources.length > 0}
                    hasRecentSession={Boolean(recentHistoryItem)}
                  />
                  {/* Inline recent sessions for returning users in Simple mode */}
                  {effectiveSimple && recentSessions.length > 0 && (
                    <React.Suspense fallback={null}>
                      <LazyInlineRecentSessions
                        items={recentSessions}
                        onRestore={(item) => void restoreFromHistory(item)}
                      />
                    </React.Suspense>
                  )}
                </>
              ) : null}

              <KnowledgeComposer
                autoFocus={!hasVisibleResultsArea}
                showWebToggle={false}
              />
            </div>
          </div>

          {hasVisibleResultsArea ? (
            <div
              data-testid="knowledge-results-shell"
              className={cn(
                "flex-1 overflow-y-auto pb-24 md:pb-6 animate-in fade-in duration-200",
                effectiveSimple
                  ? "mx-auto w-full max-w-3xl px-4 md:px-6"
                  : "px-4 md:px-6"
              )}
            >
              <div className={cn(
                "w-full space-y-6",
                effectiveSimple ? "" : "mx-auto max-w-4xl"
              )}>
                {hasResults ? (
                  <div className="flex justify-end">
                    <button
                      onClick={onExportClick}
                      className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-subtle hover:bg-hover hover:text-text transition-colors"
                    >
                      <Download className="h-4 w-4" />
                      Export
                    </button>
                  </div>
                ) : null}

                {showNoResultsState ? (
                  <React.Suspense fallback={null}>
                    <LazyNoResultsRecovery
                      onBroadenScope={handleBroadenScope}
                      onEnableWeb={handleEnableWeb}
                      onShowNearestMatches={handleShowNearestMatches}
                      webEnabled={settings.enable_web_fallback}
                    />
                  </React.Suspense>
                ) : null}

                <AnswerWorkspace queryStage={queryStage} />
              </div>
            </div>
          ) : null}
        </section>

        {hasVisibleResultsArea ? (
          <React.Suspense fallback={null}>
            <LazyEvidenceRail
              open={isEvidenceRailOpen}
              tab={evidenceRailTab}
              onOpenChange={(open) => {
                if (!open && hasResults) {
                  userClosedRailRef.current = true
                }
                setEvidenceRailOpen(open)
              }}
              onTabChange={setEvidenceRailTab}
              resultsCount={results.length}
              citationsCount={citations.length}
              className="bg-surface/20"
            />
          </React.Suspense>
        ) : null}
      </main>

      {/* Mode toggle + promotion toast */}
      <div className="fixed bottom-4 right-4 z-20 flex flex-col items-end gap-2">
        {showPromotionToast && !isMobile && (
          <div className="rounded-lg border border-border bg-surface px-4 py-3 shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-300">
            <p className="text-sm font-medium text-text">Switch to workspace view?</p>
            <p className="mt-0.5 text-xs text-text-muted">
              Get a full research layout with history sidebar and evidence panel.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={acceptPromotion}
                className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-white hover:bg-primaryStrong transition-colors"
              >
                Open workspace
              </button>
              <button
                type="button"
                onClick={dismissPromotion}
                className="rounded-md border border-border px-3 py-1 text-xs text-text-muted hover:bg-hover transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {!isMobile && (
          <button
            type="button"
            onClick={() => setLayoutMode(isSimple ? "research" : "simple")}
            className="rounded-lg border border-border bg-surface p-2 shadow-sm hover:bg-hover transition-colors"
            title={isSimple ? "Open workspace view" : "Simplify view"}
            aria-label={isSimple ? "Open workspace view" : "Simplify view"}
          >
            {isSimple ? (
              <PanelLeftOpen className="h-4 w-4 text-text-muted" />
            ) : (
              <PanelLeftClose className="h-4 w-4 text-text-muted" />
            )}
          </button>
        )}
      </div>
    </div>
  )
}
