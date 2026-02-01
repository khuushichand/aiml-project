import { useState, useEffect, useCallback, useRef } from "react"
import type ePub from "epubjs"
import type { Book, Rendition, NavItem, Location } from "epubjs"

export interface EpubLocation {
  cfi: string
  percentage: number
  chapterIndex?: number
  chapterTitle?: string
}

export interface EpubReaderState {
  book: Book | null
  rendition: Rendition | null
  isLoading: boolean
  error: Error | null
  currentLocation: EpubLocation | null
  toc: NavItem[]
}

export interface UseEpubReaderReturn extends EpubReaderState {
  display: (target?: string) => void
  next: () => void
  prev: () => void
  goToPercentage: (percentage: number) => void
}

/**
 * Core hook for managing epub.js book lifecycle.
 *
 * @param url - URL to the EPUB file
 * @returns Book instance, rendition, loading state, and navigation functions
 */
export function useEpubReader(url: string | undefined): UseEpubReaderReturn {
  const [book, setBook] = useState<Book | null>(null)
  const [rendition, setRendition] = useState<Rendition | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [currentLocation, setCurrentLocation] = useState<EpubLocation | null>(null)
  const [toc, setToc] = useState<NavItem[]>([])

  const bookRef = useRef<Book | null>(null)
  const renditionRef = useRef<Rendition | null>(null)

  // Initialize book when URL changes
  useEffect(() => {
    if (!url) {
      setIsLoading(false)
      return
    }

    let mounted = true

    const initBook = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Dynamically import epubjs to avoid SSR issues
        const ePubModule = await import("epubjs")
        const ePub = ePubModule.default

        // Clean up previous book if exists
        if (bookRef.current) {
          bookRef.current.destroy()
        }

        const newBook = ePub(url)
        bookRef.current = newBook

        // Wait for book to be ready
        await newBook.ready

        if (!mounted) {
          newBook.destroy()
          return
        }

        // Load navigation/TOC
        await newBook.loaded.navigation
        const navigation = newBook.navigation

        setBook(newBook)
        setToc(navigation.toc)
        setIsLoading(false)
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err : new Error("Failed to load EPUB"))
          setIsLoading(false)
        }
      }
    }

    initBook()

    return () => {
      mounted = false
      if (bookRef.current) {
        bookRef.current.destroy()
        bookRef.current = null
      }
      setBook(null)
      setRendition(null)
      setCurrentLocation(null)
      setToc([])
    }
  }, [url])

  // Store rendition reference
  useEffect(() => {
    renditionRef.current = rendition
  }, [rendition])

  // Update location when rendition location changes
  useEffect(() => {
    if (!rendition) return

    const handleRelocated = (location: Location) => {
      const cfi = location.start.cfi
      const percentage = rendition.book.locations.percentageFromCfi(cfi) || 0

      // Find chapter info
      const spine = rendition.book.spine
      const chapter = spine.get(location.start.href)
      let chapterTitle: string | undefined
      let chapterIndex: number | undefined

      if (chapter) {
        chapterIndex = chapter.index
        // Try to find the chapter title from TOC
        const findTocItem = (items: NavItem[]): NavItem | undefined => {
          for (const item of items) {
            if (item.href.includes(location.start.href)) {
              return item
            }
            if (item.subitems) {
              const found = findTocItem(item.subitems)
              if (found) return found
            }
          }
          return undefined
        }
        const tocItem = findTocItem(toc)
        if (tocItem) {
          chapterTitle = tocItem.label
        }
      }

      setCurrentLocation({
        cfi,
        percentage,
        chapterIndex,
        chapterTitle
      })
    }

    rendition.on("relocated", handleRelocated)

    return () => {
      rendition.off("relocated", handleRelocated)
    }
  }, [rendition, toc])

  // Navigation functions
  const display = useCallback((target?: string) => {
    if (renditionRef.current) {
      renditionRef.current.display(target)
    }
  }, [])

  const next = useCallback(() => {
    if (renditionRef.current) {
      renditionRef.current.next()
    }
  }, [])

  const prev = useCallback(() => {
    if (renditionRef.current) {
      renditionRef.current.prev()
    }
  }, [])

  const goToPercentage = useCallback((percentage: number) => {
    if (renditionRef.current && bookRef.current) {
      const locations = bookRef.current.locations
      const cfi = locations.cfiFromPercentage(percentage)
      if (cfi) {
        renditionRef.current.display(cfi)
      }
    }
  }, [])

  return {
    book,
    rendition,
    isLoading,
    error,
    currentLocation,
    toc,
    display,
    next,
    prev,
    goToPercentage
  }
}

/**
 * Hook to set up a rendition on a container element.
 *
 * @param book - The epub.js Book instance
 * @param containerRef - Ref to the container element
 * @param options - Rendition options
 * @returns The Rendition instance
 */
export function useEpubRendition(
  book: Book | null,
  containerRef: React.RefObject<HTMLElement | null>,
  options?: {
    width?: string
    height?: string
    spread?: "none" | "auto" | "always"
    flow?: "paginated" | "scrolled" | "scrolled-doc"
    minSpreadWidth?: number
  }
): Rendition | null {
  const [rendition, setRendition] = useState<Rendition | null>(null)

  useEffect(() => {
    if (!book || !containerRef.current) return

    // Create rendition
    const rend = book.renderTo(containerRef.current, {
      width: options?.width || "100%",
      height: options?.height || "100%",
      spread: options?.spread || "none",
      flow: options?.flow || "paginated",
      minSpreadWidth: options?.minSpreadWidth || 800
    })

    // Generate locations for percentage-based navigation
    book.ready.then(() => {
      // Generate locations with ~150 chars per location
      return book.locations.generate(150)
    })

    // Display the book
    rend.display()

    setRendition(rend)

    return () => {
      rend.destroy()
      setRendition(null)
    }
  }, [book, containerRef, options?.width, options?.height, options?.spread, options?.flow, options?.minSpreadWidth])

  return rendition
}
