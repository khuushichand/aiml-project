/**
 * HistorySidebar - Past searches sidebar
 */

import React, { useMemo, useState, useEffect } from "react"
import {
  History,
  Search,
  FileText,
  Sparkles,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Settings,
} from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import type { SearchHistoryItem } from "./types"

const KNOWLEDGE_QA_KEYWORD = "__knowledge_QA__"

type HistorySidebarProps = {
  className?: string
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } else if (days === 1) {
    return "Yesterday"
  } else if (days < 7) {
    return date.toLocaleDateString([], { weekday: "short" })
  } else {
    return date.toLocaleDateString([], { month: "short", day: "numeric" })
  }
}

// Skeleton loading component for history items
function HistorySkeleton() {
  return (
    <div className="py-2 space-y-3 animate-pulse" aria-label="Loading search history">
      {[1, 2, 3].map((i) => (
        <div key={i} className="px-4">
          <div className="flex items-start gap-2 px-2 py-2">
            <div className="w-4 h-4 bg-muted rounded flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/2" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function groupByDate(items: SearchHistoryItem[]): Map<string, SearchHistoryItem[]> {
  const groups = new Map<string, SearchHistoryItem[]>()

  for (const item of items) {
    const date = new Date(item.timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    let groupKey: string
    if (days === 0) {
      groupKey = "Today"
    } else if (days === 1) {
      groupKey = "Yesterday"
    } else if (days < 7) {
      groupKey = "This Week"
    } else if (days < 30) {
      groupKey = "This Month"
    } else {
      groupKey = "Older"
    }

    if (!groups.has(groupKey)) {
      groups.set(groupKey, [])
    }
    groups.get(groupKey)!.push(item)
  }

  return groups
}

export function HistorySidebar({ className }: HistorySidebarProps) {
  const {
    searchHistory,
    historySidebarOpen,
    setHistorySidebarOpen,
    restoreFromHistory,
    deleteHistoryItem,
    preset,
    setSettingsPanelOpen,
  } = useKnowledgeQA()

  // Initial loading state for better UX feedback
  const [isInitialLoad, setIsInitialLoad] = useState(true)

  // Clear initial load state after brief delay or when history is available
  useEffect(() => {
    if (searchHistory.length > 0) {
      setIsInitialLoad(false)
    } else {
      // Show skeleton briefly even if empty to indicate loading attempt
      const timer = setTimeout(() => setIsInitialLoad(false), 500)
      return () => clearTimeout(timer)
    }
  }, [searchHistory])

  const filteredHistory = useMemo(() => {
    return searchHistory.filter((item) => {
      const keywords = Array.isArray(item.keywords) ? item.keywords : []
      return keywords.some(
        (kw) => String(kw).toLowerCase() === KNOWLEDGE_QA_KEYWORD.toLowerCase()
      )
    })
  }, [searchHistory])

  const groupedHistory = useMemo(
    () => groupByDate(filteredHistory),
    [filteredHistory]
  )

  // Collapsed state
  if (!historySidebarOpen) {
    return (
      <div className={cn("flex flex-col items-center py-4 px-2 border-r border-border bg-muted/30", className)}>
        <button
          onClick={() => setHistorySidebarOpen(true)}
          className="p-2 rounded-lg hover:bg-muted transition-colors"
          title="Expand sidebar"
        >
          <ChevronRight className="w-5 h-5 text-text-muted" />
        </button>

        <div className="mt-4 flex flex-col gap-2">
          <button
            onClick={() => setHistorySidebarOpen(true)}
            className="p-2 rounded-lg hover:bg-muted transition-colors"
            title="Search history"
          >
            <History className="w-5 h-5 text-text-muted" />
          </button>

          <button
            onClick={() => setSettingsPanelOpen(true)}
            className="p-2 rounded-lg hover:bg-muted transition-colors"
            title="Settings"
          >
            <Settings className="w-5 h-5 text-text-muted" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("flex flex-col w-64 border-r border-border bg-muted/30", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-text-muted" />
          <span className="font-medium text-sm">History</span>
        </div>
        <button
          onClick={() => setHistorySidebarOpen(false)}
          className="p-1 rounded hover:bg-muted transition-colors"
          title="Collapse sidebar"
        >
          <ChevronLeft className="w-4 h-4 text-text-muted" />
        </button>
      </div>

      {/* Preset indicator */}
      <div className="px-4 py-2 border-b border-border">
        <button
          onClick={() => setSettingsPanelOpen(true)}
          className="flex items-center justify-between w-full text-xs hover:bg-muted rounded-md px-2 py-1.5 transition-colors"
        >
          <span className="text-text-muted">Preset:</span>
          <span className="font-medium capitalize">{preset}</span>
        </button>
      </div>

      {/* History list */}
      <div className="flex-1 overflow-y-auto">
        {isInitialLoad ? (
          <HistorySkeleton />
        ) : filteredHistory.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-text-muted">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No search history yet</p>
            <p className="text-xs mt-1">Your searches will appear here</p>
          </div>
        ) : (
          <div className="py-2">
            {Array.from(groupedHistory.entries()).map(([group, items]) => (
              <div key={group} className="mb-3">
                <div className="px-4 py-1 text-xs font-medium text-text-muted uppercase tracking-wide">
                  {group}
                </div>
                <div className="space-y-1">
                  {items.map((item) => (
                    <HistoryItem
                      key={item.id}
                      item={item}
                      onSelect={() => restoreFromHistory(item)}
                      onDelete={() => deleteHistoryItem(item.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Settings button */}
      <div className="px-4 py-3 border-t border-border">
        <button
          onClick={() => setSettingsPanelOpen(true)}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted transition-colors"
        >
          <Settings className="w-4 h-4 text-text-muted" />
          <span>Advanced Settings</span>
        </button>
      </div>
    </div>
  )
}

// Individual history item
function HistoryItem({
  item,
  onSelect,
  onDelete,
}: {
  item: SearchHistoryItem
  onSelect: () => void
  onDelete: () => void
}) {
  const [confirmDelete, setConfirmDelete] = React.useState(false)

  // Reset confirm state after 3 seconds
  React.useEffect(() => {
    if (confirmDelete) {
      const timer = setTimeout(() => setConfirmDelete(false), 3000)
      return () => clearTimeout(timer)
    }
  }, [confirmDelete])

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirmDelete) {
      onDelete()
      setConfirmDelete(false)
    } else {
      setConfirmDelete(true)
    }
  }

  return (
    <div className="group relative px-2">
      <button
        onClick={onSelect}
        className="flex items-start gap-2 w-full px-2 py-2 text-left rounded-md hover:bg-muted transition-colors"
      >
        <Search className="w-4 h-4 mt-0.5 text-text-muted flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm truncate">{item.query}</p>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-text-muted">
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3" />
              {item.sourcesCount}
            </span>
            {item.hasAnswer && (
              <span className="flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
              </span>
            )}
            <span>{formatTimestamp(item.timestamp)}</span>
          </div>
        </div>
      </button>

      {/* Delete button (shown on hover) - requires confirmation */}
      <button
        onClick={handleDeleteClick}
        onBlur={() => setConfirmDelete(false)}
        aria-label={confirmDelete ? "Click again to confirm deletion" : "Delete from history"}
        className={cn(
          "absolute right-2 top-1/2 -translate-y-1/2 rounded transition-all",
          confirmDelete
            ? "px-2 py-1 text-xs font-medium bg-danger text-white opacity-100"
            : "p-1 opacity-0 group-hover:opacity-100 hover:bg-danger/10 hover:text-danger"
        )}
        title={confirmDelete ? "Click to confirm delete" : "Delete from history"}
      >
        {confirmDelete ? (
          "Delete?"
        ) : (
          <Trash2 className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  )
}
