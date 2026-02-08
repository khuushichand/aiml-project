import React from "react"
import { useTranslation } from "react-i18next"
import type { RagPresetName, RagSource } from "@/services/rag/unified-rag"
import type { RagPinnedResult } from "@/utils/rag-format"
import type { QASearchResponse, QADocument } from "../hooks/useQASearch"
import { SearchInput } from "../SearchTab/SearchInput"
import { QAQuickSettings } from "./QAQuickSettings"
import { QAResultsView } from "./QAResultsView"

type QASearchTabProps = {
  // Query state
  query: string
  onQueryChange: (query: string) => void
  useCurrentMessage: boolean
  onUseCurrentMessageChange: (value: boolean) => void

  // Search execution
  onSearch: () => void
  loading: boolean
  queryError: string | null

  // Quick settings
  preset: RagPresetName
  onPresetChange: (preset: RagPresetName) => void
  strategy: "standard" | "agentic"
  onStrategyChange: (strategy: "standard" | "agentic") => void
  selectedSources: RagSource[]
  onSourcesChange: (sources: RagSource[]) => void

  // Results
  response: QASearchResponse | null
  hasAttemptedSearch: boolean
  timedOut: boolean

  // Pinned results
  pinnedResults: RagPinnedResult[]

  // Result actions
  onCopyAnswer: () => void
  onInsertAnswer: () => void
  onCopyChunk: (doc: QADocument) => void
  onInsertChunk: (doc: QADocument) => void
  onPinChunk: (doc: QADocument) => void

  // Connection state
  isConnected?: boolean
  autoFocus?: boolean
  onOpenContext?: () => void
}

/**
 * QA Search tab — full RAG pipeline search with answer generation.
 */
export const QASearchTab: React.FC<QASearchTabProps> = ({
  query,
  onQueryChange,
  useCurrentMessage,
  onUseCurrentMessageChange,
  onSearch,
  loading,
  queryError,
  preset,
  onPresetChange,
  strategy,
  onStrategyChange,
  selectedSources,
  onSourcesChange,
  response,
  hasAttemptedSearch,
  timedOut,
  pinnedResults,
  onCopyAnswer,
  onInsertAnswer,
  onCopyChunk,
  onInsertChunk,
  onPinChunk,
  isConnected = true,
  autoFocus = true,
  onOpenContext
}) => {
  const { t } = useTranslation(["sidepanel"])

  return (
    <div
      className="flex flex-col gap-4 p-3"
      role="tabpanel"
      id="knowledge-tabpanel-qa-search"
      aria-labelledby="knowledge-tab-qa-search"
    >
      <SearchInput
        query={query}
        onQueryChange={onQueryChange}
        useCurrentMessage={useCurrentMessage}
        onUseCurrentMessageChange={onUseCurrentMessageChange}
        onSearch={onSearch}
        loading={loading}
        error={queryError}
        autoFocus={autoFocus}
        disabled={!isConnected}
      />

      <QAQuickSettings
        preset={preset}
        onPresetChange={onPresetChange}
        strategy={strategy}
        onStrategyChange={onStrategyChange}
        selectedSources={selectedSources}
        onSourcesChange={onSourcesChange}
        disabled={!isConnected}
      />

      <QAResultsView
        response={response}
        loading={loading}
        hasAttemptedSearch={hasAttemptedSearch}
        timedOut={timedOut}
        query={query}
        pinnedResults={pinnedResults}
        onRetry={onSearch}
        onCopyAnswer={onCopyAnswer}
        onInsertAnswer={onInsertAnswer}
        onCopyChunk={onCopyChunk}
        onInsertChunk={onInsertChunk}
        onPinChunk={onPinChunk}
      />

      {pinnedResults.length > 0 && (
        <div className="flex items-center justify-between border-t border-border pt-2 text-xs text-text-muted">
          <span>
            {t("sidepanel:rag.savedResultsCount", "Saved results ({{count}})", {
              count: pinnedResults.length
            })}
          </span>
          {onOpenContext && (
            <button
              type="button"
              onClick={onOpenContext}
              className="text-xs text-accent hover:text-accent/80 transition-colors"
            >
              {t("sidepanel:rag.manageSavedResults", "Manage in Context")}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
