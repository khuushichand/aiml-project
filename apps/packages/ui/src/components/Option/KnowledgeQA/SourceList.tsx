/**
 * SourceList - List of retrieved source documents
 */

import React, { useCallback, useMemo, useEffect } from "react"
import { FileText, Keyboard, X } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { SourceCard, type SourceAskTemplate } from "./SourceCard"
import { SourceViewerModal } from "./SourceViewerModal"
import { cn } from "@/lib/utils"
import type { RagResult } from "./types"
import { getFeedbackSessionId, submitExplicitFeedback } from "@/services/feedback"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { trackKnowledgeQaSearchMetric } from "@/utils/knowledge-qa-search-metrics"
import {
  buildSourceTypeCounts,
  filterItemsBySourceType,
  getSourceTypeLabel,
  sortSourceItems,
  type SourceListItem,
  type SourceSortMode,
} from "./sourceListUtils"

const PAGE_SIZE = 10

type SourceListProps = {
  className?: string
}

type SourceFeedbackState = {
  thumb: "up" | "down" | null
  pendingThumb: "up" | "down" | null
  submitting: boolean
  error: string | null
}

function getResultFeedbackKey(result: RagResult, index: number): string {
  if (typeof result.id === "string" && result.id.length > 0) {
    return result.id
  }
  return `source-${index}`
}

function buildAskPrompt(template: SourceAskTemplate, title: string): string {
  if (template === "summary") {
    return `Summarize ${title}`
  }
  if (template === "quotes") {
    return `Key quotes from ${title}`
  }
  return `Tell me more about ${title}`
}

export function SourceList({ className }: SourceListProps) {
  const {
    results = [],
    citations = [],
    focusedSourceIndex = null,
    focusSource,
    setQuery,
    query = "",
    currentThreadId = null,
    messages = [],
  } = useKnowledgeQA()
  const messageApi = useAntdMessage()

  const [sortMode, setSortMode] = React.useState<SourceSortMode>("relevance")
  const [activeSourceType, setActiveSourceType] = React.useState<string>("all")
  const [visibleCount, setVisibleCount] = React.useState(PAGE_SIZE)
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false)
  const [viewerState, setViewerState] = React.useState<{
    result: RagResult | null
    index: number | null
  }>({
    result: null,
    index: null,
  })
  const [feedbackBySource, setFeedbackBySource] = React.useState<
    Record<string, SourceFeedbackState>
  >({})
  const feedbackSessionId = React.useMemo(() => getFeedbackSessionId(), [])
  const latestAssistantMessageId = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "assistant") {
        return messages[index].id
      }
    }
    return null
  }, [messages])

  const sourceItems = useMemo<SourceListItem[]>(
    () => results.map((result, originalIndex) => ({ result, originalIndex })),
    [results]
  )

  // Get cited indices (0-based)
  const citedIndices = useMemo(
    () => new Set(citations.map((citation) => citation.index - 1)),
    [citations]
  )

  const sourceTypeCounts = useMemo(() => buildSourceTypeCounts(results), [results])

  const sourceTypeFilters = useMemo(() => {
    const options = [
      {
        key: "all",
        label: "All",
        count: results.length,
      },
      ...Object.entries(sourceTypeCounts)
        .filter(([, count]) => count > 0)
        .sort((left, right) => right[1] - left[1])
        .map(([sourceType, count]) => ({
          key: sourceType,
          label: getSourceTypeLabel(sourceType, { plural: true }),
          count,
        })),
    ]

    return options
  }, [results.length, sourceTypeCounts])

  const filteredItems = useMemo(
    () => filterItemsBySourceType(sourceItems, activeSourceType),
    [activeSourceType, sourceItems]
  )

  const sortedItems = useMemo(
    () => sortSourceItems(filteredItems, sortMode, citedIndices),
    [citedIndices, filteredItems, sortMode]
  )

  const visibleItems = useMemo(
    () => sortedItems.slice(0, visibleCount),
    [sortedItems, visibleCount]
  )

  const visibleIndices = useMemo(
    () => visibleItems.map((item) => item.originalIndex),
    [visibleItems]
  )

  const hasMoreResults = visibleItems.length < sortedItems.length

  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [results, activeSourceType, sortMode])

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const isEditableTarget =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable

      if (event.key === "?" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        if (isEditableTarget) return
        event.preventDefault()
        setShortcutsOpen(true)
        return
      }

      // Number keys 1-9 to jump to visible sources
      if (
        event.key >= "1" &&
        event.key <= "9" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        if (isEditableTarget) return

        const visiblePosition = Number.parseInt(event.key, 10) - 1
        const selectedItem = visibleItems[visiblePosition]
        if (!selectedItem) return

        event.preventDefault()
        focusSource(selectedItem.originalIndex)
        const element = document.getElementById(
          `source-card-${selectedItem.originalIndex}`
        )
        element?.scrollIntoView({ behavior: "smooth", block: "center" })
        return
      }

      // Tab to navigate between visible sources
      if (event.key === "Tab" && !event.shiftKey && visibleIndices.length > 0) {
        if (!target?.closest('[id^="source-card-"]')) return

        event.preventDefault()
        const focusedElementId = target.closest('[id^="source-card-"]')?.id
        const focusedElementIndex = focusedElementId
          ? Number.parseInt(focusedElementId.replace("source-card-", ""), 10)
          : null
        const currentIndex =
          focusedSourceIndex != null ? focusedSourceIndex : focusedElementIndex
        const currentPosition =
          currentIndex != null ? visibleIndices.indexOf(currentIndex) : -1
        const nextPosition =
          currentPosition >= 0
            ? (currentPosition + 1) % visibleIndices.length
            : 0

        const nextIndex = visibleIndices[nextPosition]
        focusSource(nextIndex)
        const element = document.getElementById(`source-card-${nextIndex}`)
        element?.scrollIntoView({ behavior: "smooth", block: "center" })
        return
      }

      // Escape to close shortcut legend or clear focus
      if (event.key === "Escape") {
        if (shortcutsOpen) {
          setShortcutsOpen(false)
          return
        }
        focusSource(null)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [focusSource, focusedSourceIndex, shortcutsOpen, visibleIndices, visibleItems])

  // Handle "Ask About This" - populate query without auto-submitting
  const handleAskAbout = useCallback(
    (result: RagResult, template: SourceAskTemplate) => {
      const title = result.metadata?.title || "this source"
      setQuery(buildAskPrompt(template, title))

      const searchInput =
        (document.getElementById("knowledge-search-input") as HTMLInputElement | null) ||
        (document.querySelector(
          'input[aria-label="Search your knowledge base"]'
        ) as HTMLInputElement | null)
      if (searchInput) {
        searchInput.focus()
        searchInput.setSelectionRange(
          searchInput.value.length,
          searchInput.value.length
        )
      }
    },
    [setQuery]
  )

  const handleViewFull = useCallback((result: RagResult, index: number) => {
    setViewerState({ result, index })
  }, [])

  const closeViewer = useCallback(() => {
    setViewerState({ result: null, index: null })
  }, [])

  const submitSourceFeedback = useCallback(
    async (result: RagResult, resultIndex: number, thumb: "up" | "down") => {
      const sourceKey = getResultFeedbackKey(result, resultIndex)
      const chunkId =
        typeof result.metadata?.chunk_id === "string" &&
        result.metadata.chunk_id.length > 0
          ? result.metadata.chunk_id
          : undefined

      setFeedbackBySource((previous) => ({
        ...previous,
        [sourceKey]: {
          thumb,
          pendingThumb: thumb,
          submitting: true,
          error: null,
        },
      }))

      try {
        await submitExplicitFeedback({
          conversation_id: currentThreadId || undefined,
          message_id: latestAssistantMessageId || undefined,
          query: query.trim() || undefined,
          feedback_type: "relevance",
          relevance_score: thumb === "up" ? 5 : 1,
          document_ids: result.id ? [result.id] : undefined,
          chunk_ids: chunkId ? [chunkId] : undefined,
          session_id: feedbackSessionId,
        })
        setFeedbackBySource((previous) => ({
          ...previous,
          [sourceKey]: {
            thumb,
            pendingThumb: thumb,
            submitting: false,
            error: null,
          },
        }))
        void trackKnowledgeQaSearchMetric({
          type: "source_feedback_submit",
          relevant: thumb === "up",
        })
      } catch (feedbackError) {
        const detail =
          feedbackError instanceof Error && feedbackError.message
            ? feedbackError.message
            : "Unable to send source feedback."
        setFeedbackBySource((previous) => ({
          ...previous,
          [sourceKey]: {
            thumb: previous[sourceKey]?.thumb ?? null,
            pendingThumb: thumb,
            submitting: false,
            error: detail,
          },
        }))
        messageApi.open({
          type: "error",
          content: "Source feedback could not be sent. Retry when online.",
          duration: 3,
        })
      }
    },
    [
      currentThreadId,
      feedbackSessionId,
      latestAssistantMessageId,
      messageApi,
      query,
    ]
  )

  const retrySourceFeedback = useCallback(
    (result: RagResult, resultIndex: number) => {
      const sourceKey = getResultFeedbackKey(result, resultIndex)
      const pendingThumb = feedbackBySource[sourceKey]?.pendingThumb
      if (!pendingThumb) return
      void submitSourceFeedback(result, resultIndex, pendingThumb)
    },
    [feedbackBySource, submitSourceFeedback]
  )

  useEffect(() => {
    setFeedbackBySource({})
  }, [results])

  if (results.length === 0) {
    return null
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-text-muted" />
          <h3 className="font-semibold">Sources ({results.length})</h3>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="knowledge-source-sort" className="sr-only">
            Sort sources
          </label>
          <select
            id="knowledge-source-sort"
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SourceSortMode)}
            className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-text"
          >
            <option value="relevance">By Relevance</option>
            <option value="title">By Title</option>
            <option value="date">By Date</option>
            <option value="cited">Cited First</option>
          </select>
        </div>
      </div>

      {/* Source type filters */}
      <div className="flex flex-wrap items-center gap-2" aria-label="Source type filters">
        {sourceTypeFilters.map((filter) => (
          <button
            key={filter.key}
            type="button"
            onClick={() => setActiveSourceType(filter.key)}
            aria-pressed={activeSourceType === filter.key}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
              activeSourceType === filter.key
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border bg-muted text-text hover:bg-surface2"
            )}
          >
            {filter.label}
            <span className="text-[11px] opacity-80">{filter.count}</span>
          </button>
        ))}
      </div>

      {/* Keyboard hint + visible count */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-muted">
        <span>
          Showing {visibleItems.length} of {sortedItems.length}
          {sortedItems.length !== results.length ? ` (filtered from ${results.length})` : ""} sources
        </span>
        <div className="flex items-center gap-2">
          <span>
            Press <kbd className="px-1 py-0.5 bg-muted text-text rounded font-mono">1-9</kbd> to jump,
            <kbd className="ml-1 px-1 py-0.5 bg-muted text-text rounded font-mono">Tab</kbd> to cycle
          </span>
          <button
            type="button"
            onClick={() => setShortcutsOpen(true)}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-text hover:bg-surface2 transition-colors"
            aria-label="Open source keyboard shortcuts"
          >
            <Keyboard className="h-3.5 w-3.5" />
            ?
          </button>
        </div>
      </div>

      {visibleItems.length === 0 ? (
        <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-text-muted">
          No sources match the selected filters.
        </div>
      ) : (
        <>
          {/* Source cards - consistent 2-column layout above md breakpoint */}
          <div className="grid gap-4 md:grid-cols-2" role="list" aria-label="Retrieved sources">
            {visibleItems.map((item) => {
              const sourceKey = getResultFeedbackKey(item.result, item.originalIndex)
              const feedbackState = feedbackBySource[sourceKey] ?? {
                thumb: null,
                pendingThumb: null,
                submitting: false,
                error: null,
              }
              return (
                <SourceCard
                  key={item.result.id || `result-${item.originalIndex}`}
                  result={item.result}
                  index={item.originalIndex + 1}
                  isCited={citedIndices.has(item.originalIndex)}
                  isFocused={focusedSourceIndex === item.originalIndex}
                  onAskAbout={handleAskAbout}
                  onViewFull={handleViewFull}
                  onSourceFeedback={(value, sourceIndex, thumb) => {
                    void submitSourceFeedback(value, sourceIndex - 1, thumb)
                  }}
                  onRetrySourceFeedback={(value, sourceIndex) => {
                    retrySourceFeedback(value, sourceIndex - 1)
                  }}
                  feedbackThumb={feedbackState.thumb}
                  feedbackSubmitting={feedbackState.submitting}
                  feedbackError={feedbackState.error}
                />
              )
            })}
          </div>

          {hasMoreResults && (
            <div className="flex justify-center pt-1">
              <button
                type="button"
                onClick={() => setVisibleCount((previous) => previous + PAGE_SIZE)}
                className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text hover:bg-muted transition-colors"
              >
                Show more ({sortedItems.length - visibleItems.length} remaining)
              </button>
            </div>
          )}
        </>
      )}

      <SourceViewerModal
        open={Boolean(viewerState.result)}
        result={viewerState.result}
        index={viewerState.index}
        onClose={closeViewer}
      />

      {shortcutsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/45"
            aria-label="Close source shortcuts"
            onClick={() => setShortcutsOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Source keyboard shortcuts"
            className="relative w-full max-w-md rounded-xl border border-border bg-surface p-4 shadow-xl"
          >
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-sm font-semibold">Source keyboard shortcuts</h4>
              <button
                type="button"
                onClick={() => setShortcutsOpen(false)}
                className="rounded p-1 text-text-muted hover:bg-muted hover:text-text"
                aria-label="Close source shortcuts"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="space-y-2 text-sm text-text-muted">
              <li>
                <kbd className="px-1 py-0.5 bg-muted text-text rounded font-mono">1-9</kbd> Jump to the
                first nine visible sources.
              </li>
              <li>
                <kbd className="px-1 py-0.5 bg-muted text-text rounded font-mono">Tab</kbd> Cycle through
                visible source cards.
              </li>
              <li>
                <kbd className="px-1 py-0.5 bg-muted text-text rounded font-mono">Esc</kbd> Clear source
                focus or close this legend.
              </li>
              <li>
                <kbd className="px-1 py-0.5 bg-muted text-text rounded font-mono">?</kbd> Open this legend.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
