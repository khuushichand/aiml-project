/**
 * AnswerPanel - Displays generated answer with inline citations
 */

import React, { useMemo } from "react"
import { Sparkles, AlertCircle, Loader2 } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"

type AnswerPanelProps = {
  className?: string
}

// Parse answer text and replace [N] citations with clickable links
function renderAnswerWithCitations(
  answer: string,
  citedIndices: number[],
  onCitationClick: (index: number) => void
): React.ReactNode {
  const parts: React.ReactNode[] = []
  const regex = /\[(\d+)\]/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(answer)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index))
    }

    const citationNum = parseInt(match[1], 10)
    const isCited = citedIndices.includes(citationNum)

    // Add the citation as a clickable badge
    parts.push(
      <button
        key={`citation-${match.index}`}
        onClick={() => onCitationClick(citationNum)}
        aria-label={`Jump to source ${citationNum}`}
        className={cn(
          "inline-flex items-center justify-center",
          "min-w-[1.5rem] h-5 px-1.5 mx-0.5",
          "text-xs font-medium rounded",
          "transition-colors duration-200",
          isCited
            ? "bg-primary text-white hover:bg-primaryStrong"
            : "bg-surface2 text-text-muted border border-border hover:bg-muted hover:text-text"
        )}
        title={`Jump to source ${citationNum}`}
      >
        {citationNum}
      </button>
    )

    lastIndex = match.index + match[0].length
  }

  // Add remaining text
  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex))
  }

  return parts
}

export function AnswerPanel({ className }: AnswerPanelProps) {
  const { answer, citations, isSearching, error, scrollToSource, results } = useKnowledgeQA()

  // Get cited indices for highlighting
  const citedIndices = useMemo(() => citations.map((c) => c.index), [citations])

  const handleCitationClick = (index: number) => {
    scrollToSource(index - 1) // Convert from 1-based to 0-based
  }

  // Loading state
  if (isSearching) {
    return (
      <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <div>
            <p className="font-medium">Searching your knowledge base...</p>
            <p className="text-sm text-text-muted">
              Finding relevant documents and generating an answer
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className={cn("p-6 rounded-xl bg-danger/10 border border-danger/20", className)}>
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-danger mt-0.5" />
          <div>
            <p className="font-medium text-danger">Search failed</p>
            <p className="text-sm text-text-muted mt-1">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  // No answer yet
  if (!answer) {
    // Show empty state only if we have no results either
    if (results.length === 0) {
      return null
    }

    // Results but no generated answer
    return (
      <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-text-muted mt-0.5" />
          <div>
            <p className="text-text-muted">
              Found {results.length} relevant source{results.length !== 1 ? "s" : ""}.
              Enable answer generation in settings to get a synthesized response.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Answer with citations
  return (
    <div className={cn("rounded-xl bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/20", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-primary/10">
        <Sparkles className="w-4 h-4 text-primary" />
        <span className="font-medium text-sm">AI Answer</span>
        {citations.length > 0 && (
          <span className="ml-auto text-xs text-text-muted">
            {citations.length} citation{citations.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Answer content */}
      <div className="p-6">
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <p className="whitespace-pre-wrap leading-relaxed">
            {renderAnswerWithCitations(answer, citedIndices, handleCitationClick)}
          </p>
        </div>
      </div>

      {/* Citation summary */}
      {citations.length > 0 && (
        <div className="px-6 py-3 bg-muted/20 border-t border-primary/10">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-text-muted">Sources:</span>
            {citations.map((citation) => (
              <button
                key={citation.index}
                onClick={() => handleCitationClick(citation.index)}
                aria-label={`Jump to source ${citation.index}`}
                className="px-2 py-0.5 bg-surface text-text-muted border border-border rounded hover:bg-surface2 hover:text-text transition-colors"
              >
                [{citation.index}]
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
