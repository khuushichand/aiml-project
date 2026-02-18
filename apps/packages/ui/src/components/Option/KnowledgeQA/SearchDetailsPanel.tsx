/**
 * SearchDetailsPanel - Optional runtime details for retrieval quality inspection
 */

import React from "react"
import { BarChart3 } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"

type SearchDetailsPanelProps = {
  className?: string
}

function formatPercent(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "N/A"
  return `${Math.round(value * 100)}%`
}

export function SearchDetailsPanel({ className }: SearchDetailsPanelProps) {
  const { searchDetails, isSearching } = useKnowledgeQA()

  if (!searchDetails) {
    return null
  }

  const expansionTerms =
    searchDetails.expandedQueries.length > 0
      ? searchDetails.expandedQueries.join(", ")
      : "None"

  return (
    <details
      className={cn("rounded-xl border border-border bg-muted/20", className)}
      aria-label="Search details"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
        <BarChart3 className="w-4 h-4 text-text-muted" />
        Search details
        {isSearching && (
          <span className="ml-auto text-xs text-text-muted">Updating...</span>
        )}
      </summary>

      <div className="grid gap-2 border-t border-border px-4 py-3 text-sm">
        <div>
          <span className="font-medium">Query expansion:</span> {expansionTerms}
        </div>
        <div>
          <span className="font-medium">Reranking:</span>{" "}
          {searchDetails.rerankingEnabled
            ? `Enabled (${searchDetails.rerankingStrategy})`
            : "Disabled"}
        </div>
        <div>
          <span className="font-medium">Average relevance:</span>{" "}
          {formatPercent(searchDetails.averageRelevance)}
        </div>
        <div>
          <span className="font-medium">Web fallback:</span>{" "}
          {searchDetails.webFallbackEnabled
            ? searchDetails.webFallbackTriggered
              ? `Triggered${searchDetails.webFallbackEngine ? ` (${searchDetails.webFallbackEngine})` : ""}`
              : "Enabled (not triggered)"
            : "Disabled"}
        </div>
        {searchDetails.whyTheseSources && (
          <div>
            <span className="font-medium">Why these sources:</span>{" "}
            topicality {formatPercent(searchDetails.whyTheseSources.topicality)}, diversity{" "}
            {formatPercent(searchDetails.whyTheseSources.diversity)}, freshness{" "}
            {formatPercent(searchDetails.whyTheseSources.freshness)}
          </div>
        )}
      </div>
    </details>
  )
}
