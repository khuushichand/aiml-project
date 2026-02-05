import React, { useCallback, useState, useRef, useEffect, useLayoutEffect } from "react"
import { Document, pdfjs } from "react-pdf"
import type { DocumentProps } from "react-pdf"
import "react-pdf/dist/esm/Page/AnnotationLayer.css"
import "react-pdf/dist/esm/Page/TextLayer.css"
import { Spin, Alert } from "antd"
import { PdfPage } from "./PdfPage"
import { TextSelectionPopover } from "../TextSelectionPopover"
import { useTextSelection } from "@/hooks/document-workspace/useTextSelection"
import { getBrowserRuntime } from "@/utils/browser-runtime"
import type { ViewMode } from "../../types"

// Configure PDF.js worker
// For Next.js: The worker is copied to public/ during postinstall (scripts/copy-pdf-worker.mjs)
// For browser extension: Falls back to CDN
// For development: Uses CDN for simplicity
function getPdfWorkerSrc(): string {
  // CDN fallback URL
  const cdnUrl = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

  // SSR check
  if (typeof window === "undefined") {
    return cdnUrl
  }

  // In extension runtime, use the packaged worker file from the extension bundle.
  const runtime = getBrowserRuntime()
  if (runtime?.id) {
    return runtime.getURL ? runtime.getURL("pdf.worker.min.mjs") : cdnUrl
  }

  // In Next.js production builds, use the local worker from public/
  // The file is copied by scripts/copy-pdf-worker.mjs during postinstall
  if (process.env.NODE_ENV === "production") {
    return "/pdf.worker.min.mjs"
  }

  // Development and other environments: use CDN
  return cdnUrl
}

pdfjs.GlobalWorkerOptions.workerSrc = getPdfWorkerSrc()

interface PdfDocumentProps {
  url?: string
  documentId: number
  currentPage: number
  zoomLevel: number
  viewMode: ViewMode
  onLoadSuccess: (numPages: number) => void
  onLoadError: (error: Error) => void
  onPageChange: (page: number) => void
  pdfDocumentRef?: React.MutableRefObject<PdfDocumentProxy | null>
}

type PdfDocumentProxy = Parameters<NonNullable<DocumentProps["onLoadSuccess"]>>[0]

export const PdfDocument: React.FC<PdfDocumentProps> = ({
  url,
  documentId,
  currentPage,
  zoomLevel,
  viewMode,
  onLoadSuccess,
  onLoadError,
  onPageChange,
  pdfDocumentRef
}) => {
  const [numPages, setNumPages] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pdfInstance, setPdfInstance] = useState<PdfDocumentProxy | null>(null)
  const [pageMetrics, setPageMetrics] = useState<{ height: number; width: number }>({
    height: 0,
    width: 0
  })
  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  const isUserScrollingRef = useRef(false)
  const scrollTimeoutRef = useRef<number | null>(null)
  const scrollRafRef = useRef<number | null>(null)
  const wheelAccumulatorRef = useRef(0)
  const wheelResetRef = useRef<number | null>(null)

  // Text selection for popover actions
  const { selection, clearSelection } = useTextSelection(containerRef)

  const handleDocumentLoadSuccess = useCallback<NonNullable<DocumentProps["onLoadSuccess"]>>(
    (pdf) => {
      setNumPages(pdf.numPages)
      setLoading(false)
      setError(null)
      setPdfInstance(pdf)
      onLoadSuccess(pdf.numPages)
      // Store reference for search functionality
      if (pdfDocumentRef) {
        pdfDocumentRef.current = pdf
      }
    },
    [onLoadSuccess, pdfDocumentRef]
  )

  const handleDocumentLoadError = useCallback(
    (error: Error) => {
      setLoading(false)
      setError(error.message || "Failed to load PDF")
      setPdfInstance(null)
      onLoadError(error)
    },
    [onLoadError]
  )

  // Scroll to current page in continuous mode
  useEffect(() => {
    if (viewMode === "continuous" && numPages > 0) {
      const pageElement = pageRefs.current.get(currentPage)
      if (pageElement) {
        pageElement.scrollIntoView({ behavior: "smooth", block: "start" })
      }
    }
  }, [currentPage, viewMode, numPages])

  // Handle page click in thumbnail mode
  const handleThumbnailClick = useCallback(
    (pageNumber: number) => {
      onPageChange(pageNumber)
    },
    [onPageChange]
  )

  // Intersection observer for continuous scroll page tracking
  useEffect(() => {
    if (viewMode !== "continuous" || numPages === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const pageNumber = parseInt(
              entry.target.getAttribute("data-page-number") || "1",
              10
            )
            onPageChange(pageNumber)
          }
        })
      },
      {
        root: containerRef.current,
        threshold: 0.5
      }
    )

    pageRefs.current.forEach((element) => {
      observer.observe(element)
    })

    return () => {
      observer.disconnect()
    }
  }, [viewMode, numPages, onPageChange])

  const setPageRef = useCallback(
    (pageNumber: number, element: HTMLDivElement | null) => {
      if (element) {
        pageRefs.current.set(pageNumber, element)
      } else {
        pageRefs.current.delete(pageNumber)
      }
    },
    []
  )

  // Fallback measurement based on rendered DOM height (more reliable in extension).
  // Note: `pdfInstance.getPage()` provides initial metrics; ResizeObserver corrects to
  // the actual rendered size once the page is in the DOM.
  useLayoutEffect(() => {
    if (viewMode !== "single") return
    const pageElement = pageRefs.current.get(currentPage)
    if (!pageElement) return
    const rect = pageElement.getBoundingClientRect()
    if (rect.height > 0 && Math.abs(rect.height - pageMetrics.height) > 1) {
      setPageMetrics({ height: rect.height, width: rect.width })
    }

    if (typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { height, width } = entry.contentRect
      if (height > 0 && Math.abs(height - pageMetrics.height) > 1) {
        setPageMetrics({ height, width })
      }
    })
    observer.observe(pageElement)
    return () => observer.disconnect()
  }, [viewMode, currentPage, zoomLevel, loading, pageMetrics.height])

  // Compute initial page dimensions for virtual single-page scrolling.
  useEffect(() => {
    if (!pdfInstance) return
    let cancelled = false
    const scale = zoomLevel / 100
    const computeMetrics = async () => {
      try {
        const firstPage = await pdfInstance.getPage(1)
        const viewport = firstPage.getViewport({ scale })
        if (!cancelled) {
          setPageMetrics({ height: viewport.height, width: viewport.width })
        }
      } catch {
        if (!cancelled) {
          setPageMetrics({ height: 0, width: 0 })
        }
      }
    }
    void computeMetrics()
    return () => {
      cancelled = true
    }
  }, [pdfInstance, zoomLevel])

  const scale = zoomLevel / 100
  const pageGap = 16
  const fallbackPageHeight = 1100 * scale
  const fallbackPageWidth = 800 * scale
  const basePageHeight = pageMetrics.height > 0 ? pageMetrics.height : fallbackPageHeight
  const basePageWidth = pageMetrics.width > 0 ? pageMetrics.width : fallbackPageWidth
  const virtualPageHeight = basePageHeight + pageGap
  const totalPageCount =
    numPages || pdfDocumentRef?.current?.numPages || 0
  const virtualScrollEnabled = viewMode === "single" && totalPageCount > 0

  const handleVirtualScroll = useCallback(() => {
    if (!virtualScrollEnabled || !containerRef.current) return
    const container = containerRef.current

    isUserScrollingRef.current = true
    if (scrollTimeoutRef.current) {
      window.clearTimeout(scrollTimeoutRef.current)
    }
    scrollTimeoutRef.current = window.setTimeout(() => {
      isUserScrollingRef.current = false
    }, 120)

    if (scrollRafRef.current) {
      cancelAnimationFrame(scrollRafRef.current)
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      const nextPage = Math.min(
        totalPageCount,
        Math.max(1, Math.floor(container.scrollTop / virtualPageHeight) + 1)
      )
      if (nextPage !== currentPage) {
        onPageChange(nextPage)
      }
    })
  }, [virtualScrollEnabled, totalPageCount, currentPage, onPageChange, virtualPageHeight])

  useEffect(() => {
    if (!virtualScrollEnabled || !containerRef.current) return
    const container = containerRef.current
    const targetTop = (currentPage - 1) * virtualPageHeight
    if (isUserScrollingRef.current) return
    if (Math.abs(container.scrollTop - targetTop) > 4) {
      container.scrollTop = targetTop
    }
  }, [virtualScrollEnabled, currentPage, virtualPageHeight])

  const handleSingleWheel = useCallback(
    (event: React.WheelEvent<HTMLDivElement>) => {
      // Fallback path only when virtual scrolling is disabled (e.g., page count
      // not yet resolved). This keeps wheel paging from overriding normal scroll.
      if (viewMode !== "single" || virtualScrollEnabled) return
      if (totalPageCount <= 1) return

      wheelAccumulatorRef.current += event.deltaY
      if (wheelResetRef.current) {
        window.clearTimeout(wheelResetRef.current)
      }
      wheelResetRef.current = window.setTimeout(() => {
        wheelAccumulatorRef.current = 0
      }, 200)

      const threshold = 120
      if (Math.abs(wheelAccumulatorRef.current) >= threshold) {
        event.preventDefault()
        const direction = wheelAccumulatorRef.current > 0 ? 1 : -1
        const nextPage = Math.min(
          totalPageCount,
          Math.max(1, currentPage + direction)
        )
        if (nextPage !== currentPage) {
          onPageChange(nextPage)
        }
        wheelAccumulatorRef.current = 0
      }
    },
    [viewMode, virtualScrollEnabled, totalPageCount, currentPage, onPageChange]
  )

  useEffect(() => {
    return () => {
      if (scrollRafRef.current) {
        cancelAnimationFrame(scrollRafRef.current)
        scrollRafRef.current = null
      }
      if (scrollTimeoutRef.current) {
        window.clearTimeout(scrollTimeoutRef.current)
        scrollTimeoutRef.current = null
      }
      if (wheelResetRef.current) {
        window.clearTimeout(wheelResetRef.current)
        wheelResetRef.current = null
      }
      isUserScrollingRef.current = false
      wheelAccumulatorRef.current = 0
    }
  }, [])

  if (!url) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Alert
          type="warning"
          message="No document URL"
          description="Please select a document to view"
          showIcon
        />
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="flex h-full min-h-0 w-full flex-col items-center overflow-x-auto overflow-y-auto py-4 px-2 sm:px-4"
      onScroll={virtualScrollEnabled ? handleVirtualScroll : undefined}
      onWheel={handleSingleWheel}
    >
      {/* Text Selection Popover */}
      {selection && selection.text.length > 0 && (
        <TextSelectionPopover
          text={selection.text}
          position={{
            x: selection.rect.left + selection.rect.width / 2 - 80, // Center above selection
            y: selection.rect.bottom + 8 // Below selection
          }}
          onClose={clearSelection}
        />
      )}

      <Document
        file={url}
        onLoadSuccess={handleDocumentLoadSuccess}
        onLoadError={handleDocumentLoadError}
        loading={
          <div className="flex h-64 w-full flex-col items-center justify-center gap-2">
            <Spin size="large" />
            <div className="text-sm text-text-muted">Loading document…</div>
          </div>
        }
        error={
          <Alert
            type="error"
            message="Failed to load PDF"
            description={error || "An error occurred while loading the document"}
            showIcon
          />
        }
      >
        {loading ? null : viewMode === "single" ? (
          virtualScrollEnabled ? (
            // Virtualized single-page scroll mode (render neighbors to avoid blank gaps)
            <div
              className="relative"
              style={{
                height: virtualPageHeight * totalPageCount,
                width: basePageWidth,
                minWidth: basePageWidth,
                margin: "0 auto"
              }}
            >
              {[currentPage - 1, currentPage, currentPage + 1]
                .filter(
                  (pageNumber) =>
                    pageNumber >= 1 && pageNumber <= totalPageCount
                )
                .map((pageNumber) => (
                  <div
                    key={`virtual-page-${pageNumber}`}
                    className="absolute left-1/2 -translate-x-1/2"
                    style={{ top: (pageNumber - 1) * virtualPageHeight }}
                  >
                    <PdfPage
                      pageNumber={pageNumber}
                      scale={scale}
                      onSetRef={(el) => setPageRef(pageNumber, el)}
                    />
                  </div>
                ))}
            </div>
          ) : (
            // Fallback single page mode
            <PdfPage
              pageNumber={currentPage}
              scale={scale}
              onSetRef={(el) => setPageRef(currentPage, el)}
            />
          )
        ) : viewMode === "continuous" ? (
          // Continuous scroll mode
          <div className="flex flex-col items-center gap-4">
            {Array.from({ length: numPages }, (_, index) => (
              <PdfPage
                key={`page-${index + 1}`}
                pageNumber={index + 1}
                scale={scale}
                onSetRef={(el) => setPageRef(index + 1, el)}
              />
            ))}
          </div>
        ) : (
          // Thumbnail grid mode
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {Array.from({ length: numPages }, (_, index) => (
              <button
                key={`thumb-${index + 1}`}
                onClick={() => handleThumbnailClick(index + 1)}
                className={`relative cursor-pointer rounded border-2 transition-all hover:shadow-lg ${
                  currentPage === index + 1
                    ? "border-primary shadow-md"
                    : "border-transparent"
                }`}
              >
                <PdfPage
                  pageNumber={index + 1}
                  scale={0.25}
                  onSetRef={(el) => setPageRef(index + 1, el)}
                  hidePageNote
                />
                <span className="absolute bottom-1 left-1/2 -translate-x-1/2 rounded bg-black/70 px-2 py-0.5 text-xs text-white">
                  {index + 1}
                </span>
              </button>
            ))}
          </div>
        )}
      </Document>
    </div>
  )
}

export default PdfDocument
