import { useState, useCallback, useEffect, useRef } from "react"
import type { PDFDocumentProxy } from "pdfjs-dist"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

export interface SearchResult {
  page: number
  text: string
  matchIndex: number
  itemIndex: number
}

interface TextItem {
  str: string
  transform: number[]
}

interface SearchIndex {
  pageTexts: Map<number, string>
  pageItems: Map<number, TextItem[]>
}

/**
 * Hook for PDF in-document text search.
 *
 * Provides search functionality including:
 * - Building a searchable text index from the PDF
 * - Finding matches across all pages
 * - Navigating between results
 * - Highlighting matching text spans
 */
export function usePdfSearch(pdfDocumentRef: React.RefObject<PDFDocumentProxy | null>) {
  const [searchIndex, setSearchIndex] = useState<SearchIndex | null>(null)
  const [isIndexing, setIsIndexing] = useState(false)
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const highlightedElementsRef = useRef<HTMLElement[]>([])

  const searchOpen = useDocumentWorkspaceStore((s) => s.searchOpen)
  const searchQuery = useDocumentWorkspaceStore((s) => s.searchQuery)
  const searchResults = useDocumentWorkspaceStore((s) => s.searchResults)
  const activeSearchIndex = useDocumentWorkspaceStore((s) => s.activeSearchIndex)
  const setSearchOpen = useDocumentWorkspaceStore((s) => s.setSearchOpen)
  const setSearchQuery = useDocumentWorkspaceStore((s) => s.setSearchQuery)
  const setSearchResults = useDocumentWorkspaceStore((s) => s.setSearchResults)
  const setActiveSearchIndex = useDocumentWorkspaceStore((s) => s.setActiveSearchIndex)
  const clearSearch = useDocumentWorkspaceStore((s) => s.clearSearch)
  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)

  /**
   * Build search index from PDF document.
   * Extracts text content from all pages.
   */
  const buildSearchIndex = useCallback(async () => {
    const pdfDocument = pdfDocumentRef.current
    if (!pdfDocument) return

    setIsIndexing(true)

    try {
      const pageTexts = new Map<number, string>()
      const pageItems = new Map<number, TextItem[]>()

      for (let pageNum = 1; pageNum <= pdfDocument.numPages; pageNum++) {
        const page = await pdfDocument.getPage(pageNum)
        const textContent = await page.getTextContent()

        const items: TextItem[] = textContent.items
          .filter((item): item is TextItem & { str: string } => "str" in item)
          .map((item) => ({
            str: item.str,
            transform: item.transform as number[]
          }))

        pageItems.set(pageNum, items)
        pageTexts.set(pageNum, items.map((item) => item.str).join(" "))
      }

      setSearchIndex({ pageTexts, pageItems })
    } catch (error) {
      console.error("Error building search index:", error)
    } finally {
      setIsIndexing(false)
    }
  }, [pdfDocumentRef])

  /**
   * Search for query across all pages.
   */
  const search = useCallback(
    (query: string) => {
      if (!searchIndex || !query.trim()) {
        setSearchResults([])
        return
      }

      const normalizedQuery = query.toLowerCase()
      const results: SearchResult[] = []

      searchIndex.pageTexts.forEach((pageText, page) => {
        const normalizedText = pageText.toLowerCase()
        let matchIndex = 0
        let startPos = 0

        while (true) {
          const pos = normalizedText.indexOf(normalizedQuery, startPos)
          if (pos === -1) break

          // Find which item this match belongs to
          const items = searchIndex.pageItems.get(page) || []
          let currentPos = 0
          let itemIndex = 0

          for (let i = 0; i < items.length; i++) {
            const itemLength = items[i].str.length + 1 // +1 for space
            if (currentPos + itemLength > pos) {
              itemIndex = i
              break
            }
            currentPos += itemLength
          }

          results.push({
            page,
            text: pageText.slice(Math.max(0, pos - 20), pos + query.length + 20),
            matchIndex,
            itemIndex
          })

          matchIndex++
          startPos = pos + 1
        }
      })

      // Sort by page number
      results.sort((a, b) => a.page - b.page || a.matchIndex - b.matchIndex)

      setSearchResults(results)
    },
    [searchIndex, setSearchResults]
  )

  /**
   * Navigate to a specific search result.
   */
  const navigateToResult = useCallback(
    (index: number) => {
      if (index < 0 || index >= searchResults.length) return

      const result = searchResults[index]
      setActiveSearchIndex(index)
      setCurrentPage(result.page)

      // Scroll to the result after a short delay to allow page render
      setTimeout(() => {
        highlightMatches(searchQuery, index)
      }, 100)
    },
    [searchResults, setActiveSearchIndex, setCurrentPage, searchQuery]
  )

  /**
   * Go to next search result.
   */
  const goToNextResult = useCallback(() => {
    if (searchResults.length === 0) return
    const nextIndex = (activeSearchIndex + 1) % searchResults.length
    navigateToResult(nextIndex)
  }, [activeSearchIndex, searchResults.length, navigateToResult])

  /**
   * Go to previous search result.
   */
  const goToPreviousResult = useCallback(() => {
    if (searchResults.length === 0) return
    const prevIndex =
      activeSearchIndex === 0 ? searchResults.length - 1 : activeSearchIndex - 1
    navigateToResult(prevIndex)
  }, [activeSearchIndex, searchResults.length, navigateToResult])

  /**
   * Highlight matching text spans in the PDF text layer.
   */
  const highlightMatches = useCallback(
    (query: string, activeIndex: number = -1) => {
      // Clear previous highlights
      highlightedElementsRef.current.forEach((el) => {
        el.classList.remove("pdf-search-match", "pdf-search-match-active")
      })
      highlightedElementsRef.current = []

      if (!query.trim()) return

      // Find all text spans in the PDF text layer
      const textLayers = document.querySelectorAll(".react-pdf__Page__textContent")

      textLayers.forEach((layer) => {
        const spans = layer.querySelectorAll("span")

        spans.forEach((span) => {
          const text = span.textContent || ""
          const normalizedText = text.toLowerCase()
          const normalizedQuery = query.toLowerCase()

          if (normalizedText.includes(normalizedQuery)) {
            span.classList.add("pdf-search-match")
            highlightedElementsRef.current.push(span as HTMLElement)
          }
        })
      })

      // Highlight active result
      if (activeIndex >= 0 && activeIndex < searchResults.length) {
        const activeResult = searchResults[activeIndex]
        // Find the specific element for the active result on its page
        const pageContainer = document.querySelector(
          `[data-page-number="${activeResult.page}"]`
        )
        if (pageContainer) {
          const textLayer = pageContainer.querySelector(".react-pdf__Page__textContent")
          if (textLayer) {
            const spans = textLayer.querySelectorAll("span.pdf-search-match")
            // Mark the first match on this page as active (simplified logic)
            const activeSpan = spans[0]
            if (activeSpan) {
              activeSpan.classList.add("pdf-search-match-active")
              activeSpan.scrollIntoView({ behavior: "smooth", block: "center" })
            }
          }
        }
      }
    },
    [searchResults]
  )

  /**
   * Clear all highlights.
   */
  const clearHighlights = useCallback(() => {
    highlightedElementsRef.current.forEach((el) => {
      el.classList.remove("pdf-search-match", "pdf-search-match-active")
    })
    highlightedElementsRef.current = []
  }, [])

  /**
   * Open search overlay.
   */
  const openSearch = useCallback(() => {
    setSearchOpen(true)
    // Build index if not already built
    if (!searchIndex && !isIndexing) {
      buildSearchIndex()
    }
  }, [setSearchOpen, searchIndex, isIndexing, buildSearchIndex])

  /**
   * Close search overlay and clear results.
   */
  const closeSearch = useCallback(() => {
    setSearchOpen(false)
    clearSearch()
    clearHighlights()
  }, [setSearchOpen, clearSearch, clearHighlights])

  // Build search index when PDF document changes
  useEffect(() => {
    if (pdfDocumentRef.current && !searchIndex && !isIndexing) {
      buildSearchIndex()
    }
  }, [pdfDocumentRef.current, searchIndex, isIndexing, buildSearchIndex])

  // Debounce search query to prevent jank on large PDFs
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Perform search when debounced query changes
  useEffect(() => {
    if (searchOpen && debouncedQuery) {
      search(debouncedQuery)
    }
  }, [searchOpen, debouncedQuery, search])

  // Update highlights when results change
  useEffect(() => {
    if (searchOpen && searchResults.length > 0) {
      highlightMatches(searchQuery, activeSearchIndex)
    }
  }, [searchOpen, searchResults, activeSearchIndex, searchQuery, highlightMatches])

  // Clear highlights when search closes
  useEffect(() => {
    if (!searchOpen) {
      clearHighlights()
    }
  }, [searchOpen, clearHighlights])

  return {
    // State
    searchOpen,
    searchQuery,
    searchResults,
    activeSearchIndex,
    isIndexing,

    // Actions
    setSearchQuery,
    openSearch,
    closeSearch,
    goToNextResult,
    goToPreviousResult,
    navigateToResult,
    highlightMatches,
    clearHighlights
  }
}
