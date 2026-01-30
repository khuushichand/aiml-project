import React, { useRef, useEffect, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { Input, Button, Spin } from "antd"
import { X, ChevronUp, ChevronDown } from "lucide-react"
import { usePdfSearch, type PdfDocumentProxy } from "@/hooks/document-workspace/usePdfSearch"

interface PdfSearchProps {
  pdfDocumentRef: React.RefObject<PdfDocumentProxy | null>
}

/**
 * PDF search overlay component.
 * Fixed position in top-right of viewer with search input and navigation.
 */
export const PdfSearch: React.FC<PdfSearchProps> = ({ pdfDocumentRef }) => {
  const { t } = useTranslation(["option", "common"])
  const inputRef = useRef<HTMLInputElement>(null)

  const {
    searchOpen,
    searchQuery,
    searchResults,
    activeSearchIndex,
    isIndexing,
    setSearchQuery,
    closeSearch,
    goToNextResult,
    goToPreviousResult
  } = usePdfSearch(pdfDocumentRef)

  // Auto-focus input when search opens
  useEffect(() => {
    if (searchOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [searchOpen])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        closeSearch()
      } else if (e.key === "Enter") {
        e.preventDefault()
        if (e.shiftKey) {
          goToPreviousResult()
        } else {
          goToNextResult()
        }
      }
    },
    [closeSearch, goToNextResult, goToPreviousResult]
  )

  if (!searchOpen) {
    return null
  }

  const matchCount = searchResults.length
  const currentMatch = matchCount > 0 ? activeSearchIndex + 1 : 0

  return (
    <div className="absolute right-4 top-4 z-50 flex items-center gap-2 rounded-lg border border-border bg-surface p-2 shadow-lg">
      <div className="relative">
        <Input
          ref={inputRef as React.RefObject<any>}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("option:documentWorkspace.searchPlaceholder", "Search in document...")}
          size="small"
          className="w-48 pr-16"
          suffix={
            isIndexing ? (
              <Spin size="small" />
            ) : matchCount > 0 ? (
              <span className="text-xs text-muted">
                {currentMatch} / {matchCount}
              </span>
            ) : searchQuery ? (
              <span className="text-xs text-muted">0 / 0</span>
            ) : null
          }
        />
      </div>

      <div className="flex items-center gap-1">
        <Button
          type="text"
          size="small"
          icon={<ChevronUp className="h-4 w-4" />}
          onClick={goToPreviousResult}
          disabled={matchCount === 0}
          title={t("option:documentWorkspace.previousMatch", "Previous (Shift+Enter)")}
        />
        <Button
          type="text"
          size="small"
          icon={<ChevronDown className="h-4 w-4" />}
          onClick={goToNextResult}
          disabled={matchCount === 0}
          title={t("option:documentWorkspace.nextMatch", "Next (Enter)")}
        />
        <Button
          type="text"
          size="small"
          icon={<X className="h-4 w-4" />}
          onClick={closeSearch}
          title={t("common:close", "Close (Escape)")}
        />
      </div>
    </div>
  )
}

export default PdfSearch
