/**
 * useSearchHistory - Search history management hook
 *
 * This hook manages the search history state, including:
 * - Loading from local storage and/or server
 * - Persisting new searches
 * - Restoring previous searches with full context
 * - Deleting history items
 */

import { useCallback, useEffect, useState } from "react"
import type { SearchHistoryItem } from "../types"
import { tldwClient } from "@/services/tldw/TldwApiClient"

const STORAGE_KEY = "knowledge_qa_history"
const MAX_HISTORY_ITEMS = 100

export function useSearchHistory() {
  const [history, setHistory] = useState<SearchHistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  // Load history on mount
  useEffect(() => {
    const loadHistory = async () => {
      try {
        // First, try to load from local storage
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
          const parsed = JSON.parse(stored) as SearchHistoryItem[]
          setHistory(parsed)
        }

        // Optionally sync with server
        try {
          const response = await tldwClient.fetchWithAuth(
            "/api/v1/chat/conversations?source=knowledge_qa&limit=50"
          )
          if (response.ok) {
            const data = await response.json()
            // Convert conversations to history items and merge
            // This is a future enhancement
          }
        } catch {
          // Server sync failed, use local only
        }
      } catch (error) {
        console.error("Failed to load search history:", error)
      } finally {
        setLoading(false)
      }
    }

    loadHistory()
  }, [])

  // Save history to local storage when it changes
  useEffect(() => {
    if (history.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
    }
  }, [history])

  const addHistoryItem = useCallback((item: SearchHistoryItem) => {
    setHistory((prev) => {
      // Avoid duplicates based on query
      const filtered = prev.filter((h) => h.query !== item.query)
      return [item, ...filtered].slice(0, MAX_HISTORY_ITEMS)
    })
  }, [])

  const removeHistoryItem = useCallback((id: string) => {
    setHistory((prev) => prev.filter((h) => h.id !== id))
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  const getHistoryItem = useCallback(
    (id: string): SearchHistoryItem | undefined => {
      return history.find((h) => h.id === id)
    },
    [history]
  )

  return {
    history,
    loading,
    addHistoryItem,
    removeHistoryItem,
    clearHistory,
    getHistoryItem,
  }
}
