import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import type { RagSettings } from "@/services/rag/unified-rag"

export type RagSearchHistoryEntry = {
  query: string
  timestamp: number
  resultCount: number
  settings?: Partial<Pick<RagSettings, "search_mode" | "strategy" | "sources" | "top_k">>
}

const MAX_HISTORY = 50

export interface UseRagSearchHistoryDeps {
  resolvedQuery: string
  resultsLength: number
  batchResultsLength: number
  draftSettings: RagSettings
}

export function useRagSearchHistory(deps: UseRagSearchHistoryDeps) {
  const { resolvedQuery, resultsLength, batchResultsLength, draftSettings } = deps

  const [searchHistory, setSearchHistory] = useStorage<RagSearchHistoryEntry[]>(
    "ragSearchHistory",
    []
  )
  const [historyIndex, setHistoryIndex] = React.useState<number | null>(null)

  const recordSearch = React.useCallback(
    (query: string, resultCount: number) => {
      if (!query.trim()) return
      const entry: RagSearchHistoryEntry = {
        query: query.trim(),
        timestamp: Date.now(),
        resultCount,
        settings: {
          search_mode: draftSettings.search_mode,
          strategy: draftSettings.strategy,
          sources: draftSettings.sources,
          top_k: draftSettings.top_k
        }
      }
      setSearchHistory((prev) => {
        const existing = Array.isArray(prev) ? prev : []
        const deduped = existing.filter(
          (e) => e.query.toLowerCase() !== entry.query.toLowerCase()
        )
        return [entry, ...deduped].slice(0, MAX_HISTORY)
      })
      setHistoryIndex(null)
    },
    [draftSettings.search_mode, draftSettings.strategy, draftSettings.sources, draftSettings.top_k, setSearchHistory]
  )

  const recentSearches = React.useMemo(() => {
    const history = Array.isArray(searchHistory) ? searchHistory : []
    return history.slice(0, 10)
  }, [searchHistory])

  const navigateHistory = React.useCallback(
    (direction: "prev" | "next"): string | null => {
      const history = Array.isArray(searchHistory) ? searchHistory : []
      if (history.length === 0) return null

      let nextIndex: number
      if (direction === "prev") {
        nextIndex = historyIndex === null ? 0 : Math.min(historyIndex + 1, history.length - 1)
      } else {
        if (historyIndex === null || historyIndex <= 0) {
          setHistoryIndex(null)
          return ""
        }
        nextIndex = historyIndex - 1
      }

      setHistoryIndex(nextIndex)
      return history[nextIndex]?.query ?? null
    },
    [historyIndex, searchHistory]
  )

  const clearHistory = React.useCallback(() => {
    setSearchHistory([])
    setHistoryIndex(null)
  }, [setSearchHistory])

  const removeHistoryEntry = React.useCallback(
    (timestamp: number) => {
      setSearchHistory((prev) => {
        const existing = Array.isArray(prev) ? prev : []
        return existing.filter((e) => e.timestamp !== timestamp)
      })
    },
    [setSearchHistory]
  )

  return {
    searchHistory: Array.isArray(searchHistory) ? searchHistory : [],
    recentSearches,
    historyIndex,
    recordSearch,
    navigateHistory,
    clearHistory,
    removeHistoryEntry,
  }
}
