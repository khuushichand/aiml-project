import React, { useEffect, useMemo } from "react"
import { Download } from "lucide-react"
import { cn } from "@/lib/utils"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
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

function normalizeSourceSet(values: string[]): string {
  return [...values].sort((left, right) => left.localeCompare(right)).join("|")
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

  const hasResults = results.length > 0 || Boolean(answer)
  const showNoResultsState =
    hasSearched && !isSearching && !error && results.length === 0 && !answer
  const hasVisibleResultsArea =
    hasResults || showNoResultsState || Boolean(error) || isSearching
  const recentHistoryItem = searchHistory[0] || null
  const isEvidenceRailOpen = canControlEvidence
    ? evidenceRailOpen
    : hasVisibleResultsArea

  const contextChangedSinceLastRun = useMemo(() => {
    if (!lastSearchScope) return false
    return (
      lastSearchScope.preset !== preset ||
      lastSearchScope.webFallback !== settings.enable_web_fallback ||
      normalizeSourceSet(lastSearchScope.sources) !== normalizeSourceSet(settings.sources)
    )
  }, [lastSearchScope, preset, settings.enable_web_fallback, settings.sources])

  useEffect(() => {
    if (hasResults && !evidenceRailOpen) {
      setEvidenceRailOpen(true)
    }
  }, [hasResults, evidenceRailOpen, setEvidenceRailOpen])

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
                : "flex flex-1 items-center justify-center py-6"
            )}
          >
            <div className="mx-auto w-full max-w-4xl space-y-4">
              <KnowledgeContextBar
                preset={preset}
                onPresetChange={setPreset}
                sources={settings.sources}
                onOpenSources={() => setSettingsPanelOpen(true)}
                webEnabled={settings.enable_web_fallback}
                onToggleWeb={() =>
                  updateSetting("enable_web_fallback", !settings.enable_web_fallback)
                }
                contextChangedSinceLastRun={contextChangedSinceLastRun}
                onOpenSettings={() => setSettingsPanelOpen(true)}
              />

              {!hasVisibleResultsArea ? (
                <KnowledgeReadyState
                  suggestedPrompts={READY_STATE_SUGGESTIONS}
                  onPromptClick={handleSuggestedPrompt}
                  onContinueRecent={() => {
                    if (recentHistoryItem) {
                      void restoreFromHistory(recentHistoryItem)
                    }
                  }}
                  onSelectSources={() => setSettingsPanelOpen(true)}
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
                      className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
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
