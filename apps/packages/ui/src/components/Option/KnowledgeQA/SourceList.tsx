/**
 * SourceList - List of retrieved source documents
 */

import React, { useCallback, useMemo, useEffect } from "react"
import { FileText, SortAsc, SortDesc } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { SourceCard } from "./SourceCard"
import { cn } from "@/lib/utils"
import type { RagResult } from "./types"

type SortMode = "relevance" | "title"

type SourceListProps = {
  className?: string
}

export function SourceList({ className }: SourceListProps) {
  const {
    results,
    citations,
    focusedSourceIndex,
    focusSource,
    setQuery,
    search,
  } = useKnowledgeQA()

  const [sortMode, setSortMode] = React.useState<SortMode>("relevance")

  // Get cited indices (0-based)
  const citedIndices = useMemo(
    () => new Set(citations.map((c) => c.index - 1)),
    [citations]
  )

  // Sort results
  const sortedResults = useMemo(() => {
    const copy = [...results]
    if (sortMode === "title") {
      copy.sort((a, b) => {
        const titleA = a.metadata?.title || ""
        const titleB = b.metadata?.title || ""
        return titleA.localeCompare(titleB)
      })
    }
    // Relevance is default order from API
    return copy
  }, [results, sortMode])

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Number keys 1-9 to jump to source
      if (e.key >= "1" && e.key <= "9" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = e.target as HTMLElement
        if (target.tagName !== "INPUT" && target.tagName !== "TEXTAREA") {
          const index = parseInt(e.key, 10) - 1
          if (index < results.length) {
            e.preventDefault()
            focusSource(index)
            const element = document.getElementById(`source-card-${index}`)
            element?.scrollIntoView({ behavior: "smooth", block: "center" })
          }
        }
      }

      // Tab to navigate between sources
      if (e.key === "Tab" && focusedSourceIndex !== null && !e.shiftKey) {
        const target = e.target as HTMLElement
        if (target.closest('[id^="source-card-"]')) {
          e.preventDefault()
          const nextIndex = (focusedSourceIndex + 1) % results.length
          focusSource(nextIndex)
          const element = document.getElementById(`source-card-${nextIndex}`)
          element?.scrollIntoView({ behavior: "smooth", block: "center" })
        }
      }

      // Escape to clear focus
      if (e.key === "Escape") {
        focusSource(null)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [results.length, focusedSourceIndex, focusSource])

  // Handle "Ask About This" - populate query without auto-submitting
  const handleAskAbout = useCallback(
    (result: RagResult) => {
      const title = result.metadata?.title || "this document"
      setQuery(`Tell me more about ${title}`)
      // Focus the search input so user can review/modify before submitting
      // The search input has a known ID or can be found by its aria-label
      const searchInput = document.querySelector('input[aria-label="Search your knowledge base"]') as HTMLInputElement
      if (searchInput) {
        searchInput.focus()
        // Move cursor to end of input
        searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length)
      }
    },
    [setQuery]
  )

  if (results.length === 0) {
    return null
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-text-muted" />
          <h3 className="font-semibold">
            Sources ({results.length})
          </h3>
        </div>

        {/* Sort toggle */}
        <button
          onClick={() => setSortMode(sortMode === "relevance" ? "title" : "relevance")}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-muted text-text-muted hover:text-text hover:bg-surface2 transition-colors"
        >
          {sortMode === "relevance" ? (
            <>
              <SortDesc className="w-3.5 h-3.5" />
              By Relevance
            </>
          ) : (
            <>
              <SortAsc className="w-3.5 h-3.5" />
              By Title
            </>
          )}
        </button>
      </div>

      {/* Keyboard hint */}
      <div className="text-xs text-text-muted">
        Press <kbd className="px-1 py-0.5 bg-muted rounded font-mono">1-9</kbd> to jump to source,{" "}
        <kbd className="px-1 py-0.5 bg-muted rounded font-mono">Tab</kbd> to navigate
      </div>

      {/* Source cards - consistent 2-column layout above md breakpoint */}
      <div className="grid gap-4 md:grid-cols-2">
        {sortedResults.map((result, index) => {
          // Find original index for citation matching
          const originalIndex = results.indexOf(result)
          return (
            <SourceCard
              key={result.id || `result-${index}`}
              result={result}
              index={originalIndex + 1} // 1-based for display
              isCited={citedIndices.has(originalIndex)}
              isFocused={focusedSourceIndex === originalIndex}
              onAskAbout={handleAskAbout}
            />
          )
        })}
      </div>
    </div>
  )
}
