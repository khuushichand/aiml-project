import { useState, useCallback } from "react"
import type { Book, Rendition } from "epubjs"

export interface EpubSearchResult {
  cfi: string
  excerpt: string
  chapter?: string
}

export interface UseEpubSearchReturn {
  results: EpubSearchResult[]
  isSearching: boolean
  search: (query: string) => Promise<void>
  clearResults: () => void
  navigateToResult: (cfi: string) => void
}

/**
 * Hook for searching within an EPUB document.
 *
 * Uses epub.js book.search() to find text and navigate to results.
 *
 * @param book - The epub.js Book instance
 * @param rendition - The epub.js Rendition instance
 * @returns Search functions and results
 */
export function useEpubSearch(
  book: Book | null,
  rendition: Rendition | null
): UseEpubSearchReturn {
  const [results, setResults] = useState<EpubSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)

  const search = useCallback(async (query: string) => {
    if (!book || !query.trim()) {
      setResults([])
      return
    }

    setIsSearching(true)

    try {
      // epub.js search returns results from all chapters
      const searchFn = (book as any)?.search
      const searchResults = searchFn ? await searchFn.call(book, query) : []

      // Map results to our format
      const mappedResults: EpubSearchResult[] = (searchResults || []).map((result: any) => ({
        cfi: result.cfi,
        excerpt: result.excerpt || query,
        chapter: result.section?.label
      }))

      setResults(mappedResults)
    } catch (error) {
      console.error("EPUB search error:", error)
      setResults([])
    } finally {
      setIsSearching(false)
    }
  }, [book])

  const clearResults = useCallback(() => {
    setResults([])
  }, [])

  const navigateToResult = useCallback((cfi: string) => {
    if (rendition) {
      rendition.display(cfi)
    }
  }, [rendition])

  return {
    results,
    isSearching,
    search,
    clearResults,
    navigateToResult
  }
}
