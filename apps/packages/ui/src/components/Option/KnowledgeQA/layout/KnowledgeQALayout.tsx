import React, { useEffect, useMemo } from "react"
import { Download } from "lucide-react"
import { cn } from "@/lib/utils"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { isKnowledgeQaHistoryItem, sortHistoryNewestFirst } from "../historyUtils"
import { HistoryPane } from "../history/HistoryPane"
import { KnowledgeContextBar } from "../context/KnowledgeContextBar"
import { KnowledgeComposer } from "../composer/KnowledgeComposer"
import { KnowledgeReadyState } from "../empty/KnowledgeReadyState"
import { AnswerWorkspace } from "../panels/AnswerWorkspace"
import { NoResultsRecovery } from "../panels/NoResultsRecovery"
import { EvidenceRail } from "../evidence/EvidenceRail"

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

function normalizeIdentifierSet(values: Array<string | number | null | undefined>): string {
  return values
    .map((value) => {
      if (typeof value === "string") return value.trim()
      if (typeof value === "number" && Number.isFinite(value)) return String(Math.round(value))
      return ""
    })
    .filter(Boolean)
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
  const evidenceRailOpen = knowledgeQa.evidenceRailOpen ?? false
  const canControlEvidence = typeof knowledgeQa.setEvidenceRailOpen === "function"
  const setEvidenceRailOpen = knowledgeQa.setEvidenceRailOpen ?? (() => undefined)
  const evidenceRailTab = knowledgeQa.evidenceRailTab ?? "sources"
  const setEvidenceRailTab = knowledgeQa.setEvidenceRailTab ?? (() => undefined)
  const lastSearchScope = knowledgeQa.lastSearchScope ?? null
  const focusSource = knowledgeQa.focusSource ?? (() => undefined)
  const settingsPanelOpen = knowledgeQa.settingsPanelOpen ?? false

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
  const isEvidenceRailOpen = canControlEvidence
    ? evidenceRailOpen
    : hasVisibleResultsArea
  const readyStateSuggestions =
    settings.sources.length > 0
      ? READY_STATE_SUGGESTIONS
      : READY_STATE_ONBOARDING_SUGGESTIONS

  const contextChangedSinceLastRun = useMemo(() => {
    if (!lastSearchScope) return false
    return (
      lastSearchScope.preset !== preset ||
      lastSearchScope.webFallback !== settings.enable_web_fallback ||
      normalizeSourceSet(lastSearchScope.sources) !== normalizeSourceSet(settings.sources) ||
      normalizeIdentifierSet(
        Array.isArray(settings.include_media_ids) ? settings.include_media_ids : []
      ) !== "" ||
      normalizeIdentifierSet(
        Array.isArray(settings.include_note_ids) ? settings.include_note_ids : []
      ) !== ""
    )
  }, [
    lastSearchScope,
    preset,
    settings.enable_web_fallback,
    settings.include_media_ids,
    settings.include_note_ids,
    settings.sources,
  ])

  useEffect(() => {
    if (hasResults && !evidenceRailOpen) {
      setEvidenceRailOpen(true)
    }
  }, [hasResults, evidenceRailOpen, setEvidenceRailOpen])

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

      <aside aria-label="Search history">
        <HistoryPane />
      </aside>

      <main className="flex min-w-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          <div
            data-testid="knowledge-search-shell"
            className={cn(
              "px-4 transition-all duration-300 md:px-6",
              hasVisibleResultsArea
                ? "pt-6 pb-4"
                : "pt-6 pb-4"
            )}
          >
            <div className="mx-auto w-full max-w-4xl space-y-4">
              <KnowledgeContextBar
                preset={preset}
                onPresetChange={setPreset}
                sources={settings.sources}
                onSourcesChange={(sources) => updateSetting("sources", sources)}
                includeMediaIds={Array.isArray(settings.include_media_ids) ? settings.include_media_ids : []}
                onIncludeMediaIdsChange={(ids) => updateSetting("include_media_ids", ids)}
                includeNoteIds={
                  Array.isArray(settings.include_note_ids)
                    ? settings.include_note_ids.map((value) =>
                        typeof value === "string" ? value : String(value)
                      )
                    : []
                }
                onIncludeNoteIdsChange={(ids) =>
                  updateSetting(
                    "include_note_ids",
                    ids as unknown as typeof settings.include_note_ids
                  )
                }
                webEnabled={settings.enable_web_fallback}
                onToggleWeb={() =>
                  updateSetting("enable_web_fallback", !settings.enable_web_fallback)
                }
                contextChangedSinceLastRun={contextChangedSinceLastRun}
                onOpenSettings={() => setSettingsPanelOpen(true)}
              />

              {!hasVisibleResultsArea ? (
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
              className="flex-1 overflow-y-auto px-4 pb-24 md:px-6 md:pb-6 animate-in fade-in duration-200"
            >
              <div className="mx-auto max-w-4xl space-y-6">
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
                  <NoResultsRecovery
                    onBroadenScope={handleBroadenScope}
                    onEnableWeb={handleEnableWeb}
                    onShowNearestMatches={handleShowNearestMatches}
                    webEnabled={settings.enable_web_fallback}
                  />
                ) : null}

                <AnswerWorkspace queryStage={queryStage} />
              </div>
            </div>
          ) : null}
        </section>

        {hasVisibleResultsArea ? (
          <EvidenceRail
            open={isEvidenceRailOpen}
            tab={evidenceRailTab}
            onOpenChange={setEvidenceRailOpen}
            onTabChange={setEvidenceRailTab}
            resultsCount={results.length}
            citationsCount={citations.length}
            className="bg-surface/20"
          />
        ) : null}
      </main>
    </div>
  )
}
