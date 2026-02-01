import React, { useEffect, useRef, useCallback, useState } from "react"
import { useTranslation } from "react-i18next"
import { Spin, Alert } from "antd"
import type { Book, Rendition, NavItem, Location } from "epubjs"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { TextSelectionPopover } from "../TextSelectionPopover"
import { EpubSearch } from "./EpubSearch"
import { EPUB_THEMES } from "@/hooks/document-workspace/useEpubSettings"
import type { EpubLocation } from "@/hooks/document-workspace/useEpubReader"
import type { TocItem, Annotation, AnnotationColor, EpubTheme, EpubScrollMode } from "../../types"

// Color mapping for EPUB highlights
const HIGHLIGHT_COLORS: Record<AnnotationColor, string> = {
  yellow: "rgba(254, 240, 138, 0.4)",
  green: "rgba(187, 247, 208, 0.4)",
  blue: "rgba(191, 219, 254, 0.4)",
  pink: "rgba(251, 207, 232, 0.4)"
}

/**
 * Convert epub.js NavItem to our TocItem format
 */
function convertNavToTocItems(nav: NavItem[], level: number = 0): TocItem[] {
  return nav.map((item, idx) => ({
    title: item.label.trim(),
    page: idx + 1,
    level,
    href: item.href,
    children: item.subitems ? convertNavToTocItems(item.subitems, level + 1) : undefined
  }))
}

interface EpubViewerProps {
  url: string
  documentId: number
  onLoadSuccess?: (data: { chapterCount: number; toc: NavItem[] }) => void
  onLoadError?: (error: Error) => void
  onLocationChange?: (location: EpubLocation) => void
}

/**
 * EPUB viewer component using epub.js.
 *
 * Renders EPUB documents with chapter navigation, text selection,
 * and progress tracking via CFI (Canonical Fragment Identifier).
 */
export const EpubViewer: React.FC<EpubViewerProps> = ({
  url,
  documentId,
  onLoadSuccess,
  onLoadError,
  onLocationChange
}) => {
  const { t } = useTranslation(["option", "common"])
  const containerRef = useRef<HTMLDivElement>(null)
  const bookRef = useRef<Book | null>(null)
  const renditionRef = useRef<Rendition | null>(null)

  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toc, setToc] = useState<NavItem[]>([])

  // Text selection state for popover
  const [selection, setSelection] = useState<{
    text: string
    cfi: string
    rect: DOMRect
  } | null>(null)

  // Store access
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)
  const setTotalPages = useDocumentWorkspaceStore((s) => s.setTotalPages)
  const currentCfi = useDocumentWorkspaceStore((s) => s.currentCfi)
  const setCurrentCfi = useDocumentWorkspaceStore((s) => s.setCurrentCfi)
  const setCurrentPercentage = useDocumentWorkspaceStore((s) => s.setCurrentPercentage)
  const setCurrentChapterTitle = useDocumentWorkspaceStore((s) => s.setCurrentChapterTitle)
  const annotations = useDocumentWorkspaceStore((s) => s.annotations)
  const epubTheme = useDocumentWorkspaceStore((s) => s.epubTheme)
  const epubScrollMode = useDocumentWorkspaceStore((s) => s.epubScrollMode)

  // Dispatch loading event when starting
  useEffect(() => {
    if (url) {
      window.dispatchEvent(
        new CustomEvent("epub-loading", {
          detail: { documentId }
        })
      )
    }
  }, [url, documentId])

  // Initialize epub.js book
  useEffect(() => {
    if (!url || !containerRef.current) return

    let mounted = true

    const initEpub = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Dynamically import epub.js for SSR compatibility
        const ePubModule = await import("epubjs")
        const ePub = ePubModule.default

        // Clean up previous book
        if (bookRef.current) {
          bookRef.current.destroy()
        }

        const book = ePub(url)
        bookRef.current = book

        await book.ready

        if (!mounted || !containerRef.current) {
          book.destroy()
          return
        }

        // Get initial scroll mode from store
        const initialScrollMode = useDocumentWorkspaceStore.getState().epubScrollMode
        const initialTheme = useDocumentWorkspaceStore.getState().epubTheme

        // Create rendition with current scroll mode
        const rendition = book.renderTo(containerRef.current, {
          width: "100%",
          height: "100%",
          spread: "none",
          flow: initialScrollMode === "continuous" ? "scrolled" : "paginated"
        })

        renditionRef.current = rendition

        // Load navigation
        await book.loaded.navigation

        // Generate locations for percentage tracking (150 chars per location)
        await book.locations.generate(150)

        // Set total "pages" (actually locations for EPUB)
        const totalLocations = book.locations.length()
        setTotalPages(totalLocations)

        // Extract TOC
        const navigation = book.navigation
        setToc(navigation.toc)

        // Dispatch TOC ready event for TableOfContentsTab
        const tocItems = convertNavToTocItems(navigation.toc)
        window.dispatchEvent(
          new CustomEvent("epub-outline-ready", {
            detail: { documentId, items: tocItems }
          })
        )

        // Display the book - start from saved position if available
        if (currentCfi) {
          await rendition.display(currentCfi)
        } else {
          await rendition.display()
        }

        if (!mounted) {
          rendition.destroy()
          book.destroy()
          return
        }

        // Set up location change handler
        rendition.on("relocated", (location: Location) => {
          if (!mounted) return

          const cfi = location.start.cfi
          const percentage = book.locations.percentageFromCfi(cfi) || 0
          const locationIndex = book.locations.locationFromCfi(cfi) || 0

          setCurrentCfi(cfi)
          setCurrentPercentage(percentage * 100)
          setCurrentPage(locationIndex + 1) // 1-indexed for UI consistency

          // Find chapter info
          let chapterTitle: string | undefined
          let chapterIndex: number | undefined

          const spine = book.spine
          const chapter = spine.get(location.start.href)
          if (chapter) {
            chapterIndex = chapter.index
          }

          // Find chapter title from TOC
          const findTocItem = (items: NavItem[]): NavItem | undefined => {
            for (const item of items) {
              if (item.href && location.start.href.includes(item.href.split("#")[0])) {
                return item
              }
              if (item.subitems) {
                const found = findTocItem(item.subitems)
                if (found) return found
              }
            }
            return undefined
          }
          const tocItem = findTocItem(navigation.toc)
          if (tocItem) {
            chapterTitle = tocItem.label.trim()
          }

          // Update chapter title in store for annotation creation
          setCurrentChapterTitle(chapterTitle ?? null)

          onLocationChange?.({
            cfi,
            percentage: percentage * 100,
            chapterIndex,
            chapterTitle
          })
        })

        // Set up text selection handler
        rendition.on("selected", (cfiRange: string, contents: any) => {
          if (!mounted) return

          try {
            const range = rendition.getRange(cfiRange)
            if (!range) return

            const text = range.toString().trim()
            if (text.length === 0) return

            // Get the bounding rect relative to viewport
            const rect = range.getBoundingClientRect()

            setSelection({
              text,
              cfi: cfiRange,
              rect
            })
          } catch (e) {
            console.error("Selection error:", e)
          }
        })

        // Clear selection when clicking elsewhere
        rendition.on("click", () => {
          setSelection(null)
        })

        // Register all themes
        Object.entries(EPUB_THEMES).forEach(([name, styles]) => {
          rendition.themes.register(name, {
            ...styles,
            body: {
              ...styles.body,
              "font-family": "'Inter', system-ui, sans-serif",
              "line-height": "1.6",
              "padding": "20px"
            }
          })
        })

        // Apply current theme
        rendition.themes.select(initialTheme)

        setIsLoading(false)
        onLoadSuccess?.({
          chapterCount: book.spine.length,
          toc: navigation.toc
        })
      } catch (err) {
        if (mounted) {
          const error = err instanceof Error ? err : new Error("Failed to load EPUB")
          setError(error.message)
          setIsLoading(false)
          onLoadError?.(error)
        }
      }
    }

    initEpub()

    return () => {
      mounted = false
      if (renditionRef.current) {
        renditionRef.current.destroy()
        renditionRef.current = null
      }
      if (bookRef.current) {
        bookRef.current.destroy()
        bookRef.current = null
      }
    }
  }, [url]) // Only re-init on URL change

  // Listen for navigation events from TOC (href-based)
  useEffect(() => {
    const handleNavigate = (e: CustomEvent<{ href: string; documentId: number }>) => {
      if (e.detail.documentId !== documentId) return

      const rendition = renditionRef.current
      if (rendition) {
        rendition.display(e.detail.href)
      }
    }

    window.addEventListener("epub-navigate", handleNavigate as EventListener)

    return () => {
      window.removeEventListener("epub-navigate", handleNavigate as EventListener)
    }
  }, [documentId])

  // Listen for CFI navigation events (from annotations panel)
  useEffect(() => {
    const handleNavigateCfi = (e: CustomEvent<{ cfi: string; documentId: number }>) => {
      if (e.detail.documentId !== documentId) return

      const rendition = renditionRef.current
      if (rendition) {
        rendition.display(e.detail.cfi)
      }
    }

    window.addEventListener("epub-navigate-cfi", handleNavigateCfi as EventListener)

    return () => {
      window.removeEventListener("epub-navigate-cfi", handleNavigateCfi as EventListener)
    }
  }, [documentId])

  // Render highlights from annotations
  // NOTE: epubScrollMode is included as a dependency because switching scroll modes
  // destroys and recreates the rendition, so highlights need to be re-applied
  useEffect(() => {
    const rendition = renditionRef.current
    if (!rendition || isLoading) return

    // Clear existing highlights
    // Note: epub.js doesn't have a clear all method, so we track added highlights
    const highlightIds: string[] = []

    // Add highlights for EPUB annotations (those with CFI locations)
    annotations
      .filter((ann): ann is Annotation & { location: string } =>
        typeof ann.location === "string" &&
        ann.documentId === documentId &&
        ann.annotationType === "highlight"
      )
      .forEach((ann) => {
        try {
          rendition.annotations.highlight(
            ann.location,
            { id: ann.id },
            undefined, // onClick callback - optional
            `highlight-${ann.color}`,
            { fill: HIGHLIGHT_COLORS[ann.color], "fill-opacity": "1" }
          )
          highlightIds.push(ann.id)
        } catch (e) {
          // Highlight CFI may not be valid for current view
          console.debug("Could not render highlight:", ann.id, e)
        }
      })

    // Cleanup function to remove highlights
    return () => {
      highlightIds.forEach((id) => {
        try {
          rendition.annotations.remove(annotations.find(a => a.id === id)?.location as string, "highlight")
        } catch (e) {
          // Ignore cleanup errors
        }
      })
    }
  }, [annotations, documentId, isLoading, epubScrollMode])

  // Handle navigation via store's currentPage (which maps to location index)
  useEffect(() => {
    const book = bookRef.current
    const rendition = renditionRef.current

    if (!book || !rendition || isLoading) return

    // Convert page number to CFI and navigate
    const cfi = book.locations.cfiFromLocation(currentPage - 1)
    if (cfi) {
      rendition.display(cfi)
    }
  }, [currentPage, isLoading])

  // Keyboard navigation
  useEffect(() => {
    const rendition = renditionRef.current
    if (!rendition) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle if in input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return
      }

      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
          e.preventDefault()
          rendition.next()
          break
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault()
          rendition.prev()
          break
      }
    }

    // Also handle rendition keyboard events
    rendition.on("keydown", handleKeyDown)

    return () => {
      rendition.off("keydown", handleKeyDown)
    }
  }, [isLoading])

  // Handle theme changes
  useEffect(() => {
    const rendition = renditionRef.current
    if (!rendition || isLoading) return

    rendition.themes.select(epubTheme)
  }, [epubTheme, isLoading])

  // Handle scroll mode changes - requires re-rendering the book
  useEffect(() => {
    const book = bookRef.current
    const rendition = renditionRef.current
    if (!book || !rendition || isLoading || !containerRef.current) return

    // Get current location before destroying rendition
    const currentLocation = rendition.currentLocation()
    const currentCfiFromStore = useDocumentWorkspaceStore.getState().currentCfi

    // Destroy current rendition
    rendition.destroy()

    // Create new rendition with updated flow
    const newRendition = book.renderTo(containerRef.current, {
      width: "100%",
      height: "100%",
      spread: "none",
      flow: epubScrollMode === "continuous" ? "scrolled" : "paginated"
    })

    renditionRef.current = newRendition

    // Re-register themes
    Object.entries(EPUB_THEMES).forEach(([name, styles]) => {
      newRendition.themes.register(name, {
        ...styles,
        body: {
          ...styles.body,
          "font-family": "'Inter', system-ui, sans-serif",
          "line-height": "1.6",
          "padding": "20px"
        }
      })
    })

    // Apply current theme
    newRendition.themes.select(epubTheme)

    // Display at previous location
    const targetCfi = currentCfiFromStore || (currentLocation?.start?.cfi)
    if (targetCfi) {
      newRendition.display(targetCfi)
    } else {
      newRendition.display()
    }

    // Re-setup event handlers
    newRendition.on("relocated", (location: Location) => {
      const cfi = location.start.cfi
      const percentage = book.locations.percentageFromCfi(cfi) || 0
      const locationIndex = book.locations.locationFromCfi(cfi) || 0

      useDocumentWorkspaceStore.getState().setCurrentCfi(cfi)
      useDocumentWorkspaceStore.getState().setCurrentPercentage(percentage * 100)
      useDocumentWorkspaceStore.getState().setCurrentPage(locationIndex + 1)
    })

    newRendition.on("selected", (cfiRange: string) => {
      try {
        const range = newRendition.getRange(cfiRange)
        if (!range) return

        const text = range.toString().trim()
        if (text.length === 0) return

        const rect = range.getBoundingClientRect()
        setSelection({ text, cfi: cfiRange, rect })
      } catch (e) {
        console.error("Selection error:", e)
      }
    })

    newRendition.on("click", () => {
      setSelection(null)
    })
  }, [epubScrollMode]) // Only re-run when scroll mode changes

  const clearSelection = useCallback(() => {
    setSelection(null)
  }, [])

  if (!url) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Alert
          type="warning"
          message={t("option:documentWorkspace.noUrl", "No document URL")}
          description={t(
            "option:documentWorkspace.selectDocument",
            "Please select a document to view"
          )}
          showIcon
        />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Alert
          type="error"
          message={t("option:documentWorkspace.loadError", "Failed to load EPUB")}
          description={error}
          showIcon
        />
      </div>
    )
  }

  return (
    <div className="relative h-full w-full">
      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/80">
          <Spin size="large" tip={t("option:documentWorkspace.loading", "Loading...")} />
        </div>
      )}

      {/* Search overlay */}
      <EpubSearch bookRef={bookRef} renditionRef={renditionRef} />

      {/* Text Selection Popover */}
      {selection && selection.text.length > 0 && (
        <TextSelectionPopover
          text={selection.text}
          position={{
            x: selection.rect.left + selection.rect.width / 2 - 80,
            y: selection.rect.bottom + 8
          }}
          onClose={clearSelection}
          epubCfi={selection.cfi}
        />
      )}

      {/* EPUB container */}
      <div
        ref={containerRef}
        className="h-full w-full"
        style={{
          // epub.js needs explicit dimensions
          minHeight: "400px"
        }}
      />
    </div>
  )
}

export default EpubViewer
