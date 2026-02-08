import React from "react"
import { Spin } from "antd"
import { useTranslation } from "react-i18next"
import type { RagPinnedResult } from "@/utils/rag-format"
import type { QASearchResponse, QADocument } from "../hooks/useQASearch"
import { SearchEmptyState } from "../SearchTab/SearchEmptyState"
import { GeneratedAnswerCard } from "./GeneratedAnswerCard"
import { SourceChunksList } from "./SourceChunksList"

type QAResultsViewProps = {
  response: QASearchResponse | null
  loading: boolean
  hasAttemptedSearch: boolean
  timedOut: boolean
  query?: string
  pinnedResults: RagPinnedResult[]
  onRetry?: () => void
  onCopyAnswer: () => void
  onInsertAnswer: () => void
  onCopyChunk: (doc: QADocument) => void
  onInsertChunk: (doc: QADocument) => void
  onPinChunk: (doc: QADocument) => void
  onPreviewChunk: (doc: QADocument) => void
}

/**
 * Orchestrates the QA Search results display:
 * generated answer card on top, source chunks below.
 */
export const QAResultsView: React.FC<QAResultsViewProps> = ({
  response,
  loading,
  hasAttemptedSearch,
  timedOut,
  query,
  pinnedResults,
  onRetry,
  onCopyAnswer,
  onInsertAnswer,
  onCopyChunk,
  onInsertChunk,
  onPinChunk,
  onPreviewChunk
}) => {
  const { t } = useTranslation(["sidepanel"])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spin size="default" />
        <span className="ml-2 text-sm text-text-muted">
          {t("sidepanel:qaSearch.searching", "Searching knowledge base...")}
        </span>
      </div>
    )
  }

  if (timedOut) {
    return <SearchEmptyState variant="timeout" onRetry={onRetry} />
  }

  if (!hasAttemptedSearch) {
    return <SearchEmptyState variant="initial" />
  }

  if (!response) {
    return <SearchEmptyState variant="no-results" />
  }

  const hasAnswer = !!response.generatedAnswer
  const hasDocs = response.documents.length > 0

  if (!hasAnswer && !hasDocs) {
    return <SearchEmptyState variant="no-results" />
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Errors */}
      {response.errors.length > 0 && (
        <div className="rounded-lg border border-warn/30 bg-warn/5 p-3">
          <p className="text-xs text-warn">
            {response.errors.join("; ")}
          </p>
        </div>
      )}

      {/* Generated Answer */}
      {hasAnswer && (
        <GeneratedAnswerCard
          answer={response.generatedAnswer!}
          totalTime={response.totalTime}
          cacheHit={response.cacheHit}
          onCopy={onCopyAnswer}
          onInsert={onInsertAnswer}
        />
      )}

      {/* Source Chunks */}
      {hasDocs && (
        <SourceChunksList
          documents={response.documents}
          query={query}
          pinnedResults={pinnedResults}
          onCopy={onCopyChunk}
          onInsert={onInsertChunk}
          onPin={onPinChunk}
          onPreview={onPreviewChunk}
        />
      )}
    </div>
  )
}
