import React, { useRef, useEffect, useCallback, useState } from "react"
import { useTranslation } from "react-i18next"
import { Input, Button, Spin } from "antd"
import { X, ChevronUp, ChevronDown } from "lucide-react"
import type { Book, Rendition } from "epubjs"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

interface EpubSearchResult {
  cfi: string
  excerpt: string
}

interface EpubSearchProps {
  bookRef: React.RefObject<Book | null>
  renditionRef: React.RefObject<Rendition | null>
}

/**
 * EPUB search overlay component.
 * Fixed position in top-right of viewer with search input and navigation.
 */
export const EpubSearch: React.FC<EpubSearchProps> = ({ bookRef, renditionRef }) => {
  const { t } = useTranslation(["option", "common"])
  const inputRef = useRef<HTMLInputElement>(null)

  const searchOpen = useDocumentWorkspaceStore((s) => s.searchOpen)
  const setSearchOpen = useDocumentWorkspaceStore((s) => s.setSearchOpen)

  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<EpubSearchResult[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [isSearching, setIsSearching] = useState(false)

  // Perform search
  const performSearch = useCallback(async (query: string) => {
    const book = bookRef.current
    if (!book || !query.trim()) {
      setSearchResults([])
      return
    }

    setIsSearching(true)

    try {
      const results = await book.search(query)
      const mapped: EpubSearchResult[] = results.map((r: any) => ({
        cfi: r.cfi,
        excerpt: r.excerpt || query
      }))
      setSearchResults(mapped)
      setActiveIndex(0)

      // Navigate to first result
      if (mapped.length > 0 && renditionRef.current) {
        renditionRef.current.display(mapped[0].cfi)
      }
    } catch (error) {
      console.error("EPUB search error:", error)
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }, [bookRef, renditionRef])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim().length >= 2) {
        performSearch(searchQuery)
      } else {
        setSearchResults([])
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [searchQuery, performSearch])

  // Auto-focus input when search opens
  useEffect(() => {
    if (searchOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [searchOpen])

  // Close and reset
  const closeSearch = useCallback(() => {
    setSearchOpen(false)
    setSearchQuery("")
    setSearchResults([])
    setActiveIndex(0)
  }, [setSearchOpen])

  // Navigate to result
  const goToResult = useCallback((index: number) => {
    if (index < 0 || index >= searchResults.length) return

    setActiveIndex(index)
    const result = searchResults[index]
    if (result && renditionRef.current) {
      renditionRef.current.display(result.cfi)
    }
  }, [searchResults, renditionRef])

  const goToNextResult = useCallback(() => {
    const nextIndex = (activeIndex + 1) % searchResults.length
    goToResult(nextIndex)
  }, [activeIndex, searchResults.length, goToResult])

  const goToPreviousResult = useCallback(() => {
    const prevIndex = (activeIndex - 1 + searchResults.length) % searchResults.length
    goToResult(prevIndex)
  }, [activeIndex, searchResults.length, goToResult])

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
  const currentMatch = matchCount > 0 ? activeIndex + 1 : 0

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
            isSearching ? (
              <Spin size="small" />
            ) : matchCount > 0 ? (
              <span className="text-xs text-muted">
                {currentMatch} / {matchCount}
              </span>
            ) : searchQuery.length >= 2 ? (
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

export default EpubSearch
