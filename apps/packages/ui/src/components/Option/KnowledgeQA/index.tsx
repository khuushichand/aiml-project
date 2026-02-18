/**
 * KnowledgeQA - Research-grade question-answering interface
 *
 * A Perplexity-style Q&A experience combining discoverability with
 * the full power of the RAG pipeline.
 */

import React, { useEffect, useMemo, useState } from "react"
import { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
import { SearchBar } from "./SearchBar"
import { AnswerPanel } from "./AnswerPanel"
import { SearchDetailsPanel } from "./SearchDetailsPanel"
import { SourceList } from "./SourceList"
import { FollowUpInput } from "./FollowUpInput"
import { ConversationThread } from "./ConversationThread"
import { HistorySidebar } from "./HistorySidebar"
import { SettingsPanel } from "./SettingsPanel"
import { ExportDialog } from "./ExportDialog"
import { cn } from "@/lib/utils"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useConnectionActions, useConnectionState } from "@/hooks/useConnectionState"
import { WifiOff, AlertCircle, BookOpen, Download } from "lucide-react"
import {
  getRetryCountdownSeconds,
  KNOWLEDGE_QA_RETRY_INTERVAL_MS,
  KNOWLEDGE_QA_RETRY_TICK_MS,
} from "./retryScheduler"

// Main page component (inner, uses context)
function KnowledgeQAContent() {
  const {
    settingsPanelOpen,
    setSettingsPanelOpen,
    results,
    answer,
    hasSearched,
    isSearching,
    error,
  } = useKnowledgeQA()
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [retryNowMs, setRetryNowMs] = useState(() => Date.now())
  const online = useServerOnline(KNOWLEDGE_QA_RETRY_INTERVAL_MS)
  const { capabilities, loading: capabilitiesLoading, refresh: refreshCapabilities } =
    useServerCapabilities()
  const { checkOnce } = useConnectionActions()
  const { isChecking, lastCheckedAt } = useConnectionState()

  // Check if RAG is supported
  const hasRag = capabilities?.hasRag ?? true
  const retryCountdownSeconds = useMemo(
    () =>
      getRetryCountdownSeconds({
        lastAttemptAt: lastCheckedAt,
        now: retryNowMs,
        retryIntervalMs: KNOWLEDGE_QA_RETRY_INTERVAL_MS,
      }),
    [lastCheckedAt, retryNowMs]
  )

  useEffect(() => {
    if (online) {
      return
    }
    setRetryNowMs(Date.now())
    const interval = window.setInterval(
      () => setRetryNowMs(Date.now()),
      KNOWLEDGE_QA_RETRY_TICK_MS
    )
    return () => window.clearInterval(interval)
  }, [online])

  const handleRetryConnection = () => {
    void checkOnce()
  }

  const handleRetryCapabilities = () => {
    void refreshCapabilities()
  }

  // Offline state
  if (!online) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <WifiOff className="w-16 h-16 mx-auto mb-4 text-text-muted" />
          <h2 className="text-xl font-semibold mb-2">Server Offline</h2>
          <p className="text-text-muted mb-3">
            Cannot connect to the server. Please ensure the tldw server is running
            and try again.
          </p>
          <button
            type="button"
            onClick={handleRetryConnection}
            disabled={isChecking}
            className="px-3 py-1.5 rounded-md border border-border hover:bg-muted transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isChecking ? "Checking connection..." : "Retry connection"}
          </button>
          <p className="mt-2 text-xs text-text-muted">
            Retrying automatically in {retryCountdownSeconds}s...
          </p>
        </div>
      </div>
    )
  }

  // No RAG support
  if (!capabilitiesLoading && !hasRag) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 mx-auto mb-4 text-text-muted" />
          <h2 className="text-xl font-semibold mb-2">RAG Not Available</h2>
          <p className="text-text-muted mb-2">
            Knowledge search requires the RAG module to be enabled on the server.
          </p>
          <p className="text-text-muted mb-4">
            Configure embedding models and enable RAG in your server setup, then
            restart the server and retry capability detection.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={handleRetryCapabilities}
              className="px-3 py-1.5 rounded-md border border-border hover:bg-muted transition-colors"
            >
              Retry capability check
            </button>
            <a
              href="https://github.com/rmusser01/tldw_server2#readme"
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-md border border-primary/40 bg-primary/10 text-primary hover:bg-primary/15 transition-colors"
            >
              Open setup guide
            </a>
          </div>
        </div>
      </div>
    )
  }

  const hasResults = results.length > 0 || Boolean(answer)
  const showNoResultsState =
    hasSearched && !isSearching && !error && results.length === 0 && !answer
  const hasVisibleResultsArea =
    hasResults || showNoResultsState || Boolean(error) || isSearching

  return (
    <div className="relative flex h-full">
      <a
        href="#knowledge-search-input"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm text-text focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:ring-2 focus:ring-primary"
      >
        Skip to search
      </a>

      {/* History sidebar */}
      <aside aria-label="Search history">
        <HistorySidebar />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Search area */}
        <div
          data-testid="knowledge-search-shell"
          className={cn(
            "flex flex-col items-center justify-center transition-all duration-300",
            hasVisibleResultsArea ? "pt-6 pb-4" : "flex-1"
          )}
        >
          {/* Logo/branding when no results */}
          {!hasVisibleResultsArea && (
            <div className="mb-8 text-center">
              <BookOpen className="w-16 h-16 mx-auto mb-4 text-primary" />
              <h1 className="text-3xl font-bold mb-2">Knowledge QA</h1>
              <p className="text-text-muted max-w-md">
                Ask questions about your documents and get AI-powered answers
                with citations from your knowledge base.
              </p>
            </div>
          )}

          <SearchBar />
        </div>

        {/* Results area */}
        {hasVisibleResultsArea && (
          <div
            data-testid="knowledge-results-shell"
            className="flex-1 overflow-y-auto px-6 pb-6 animate-in fade-in duration-200"
          >
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Export button */}
              {hasResults && (
                <div className="flex justify-end">
                  <button
                    onClick={() => setExportDialogOpen(true)}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Export
                  </button>
                </div>
              )}

              {showNoResultsState && (
                <div className="rounded-xl border border-border bg-muted/20 p-6">
                  <h2 className="text-base font-semibold">No results found</h2>
                  <p className="mt-2 text-sm text-text-muted">
                    Try rephrasing your query or broadening the scope of your search.
                  </p>
                  <ul className="mt-3 space-y-1 text-sm text-text-muted">
                    <li>Try different keywords or fewer constraints.</li>
                    <li>Broaden the question before adding details.</li>
                    <li>Confirm your sources were ingested and indexed.</li>
                  </ul>
                </div>
              )}

              <ConversationThread />
              <AnswerPanel />
              <SearchDetailsPanel />
              <FollowUpInput />
              <SourceList />
            </div>
          </div>
        )}
      </main>

      {/* Settings panel (drawer) */}
      <SettingsPanel
        open={settingsPanelOpen}
        onClose={() => setSettingsPanelOpen(false)}
      />

      {/* Export dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
      />
    </div>
  )
}

// Export the wrapped component
export function KnowledgeQA() {
  return (
    <KnowledgeQAProvider>
      <KnowledgeQAContent />
    </KnowledgeQAProvider>
  )
}

// Also export individual components for flexibility
export { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
export { SearchBar } from "./SearchBar"
export { AnswerPanel } from "./AnswerPanel"
export { SearchDetailsPanel } from "./SearchDetailsPanel"
export { ConversationThread } from "./ConversationThread"
export { SourceCard } from "./SourceCard"
export { SourceList } from "./SourceList"
export { FollowUpInput } from "./FollowUpInput"
export { HistorySidebar } from "./HistorySidebar"
export { SettingsPanel } from "./SettingsPanel"
export { ExportDialog } from "./ExportDialog"
export type * from "./types"
