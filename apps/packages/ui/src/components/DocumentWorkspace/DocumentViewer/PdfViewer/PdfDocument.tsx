import React, { useCallback, useState, useRef, useEffect } from "react"
import { Document, pdfjs } from "react-pdf"
import type { DocumentProps } from "react-pdf"
import { Spin, Alert } from "antd"
import { PdfPage } from "./PdfPage"
import { TextSelectionPopover } from "../TextSelectionPopover"
import { useTextSelection } from "@/hooks/document-workspace/useTextSelection"
import type { ViewMode } from "../../types"

// Configure PDF.js worker
// For Next.js: The worker is copied to public/ during postinstall (scripts/copy-pdf-worker.mjs)
// For browser extension: Falls back to CDN
// For development: Uses CDN for simplicity
function getPdfWorkerSrc(): string {
  // CDN fallback URL
  const cdnUrl = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

  // SSR check
  if (typeof window === "undefined") {
    return cdnUrl
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
  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // Text selection for popover actions
  const { selection, clearSelection } = useTextSelection(containerRef)

  const handleDocumentLoadSuccess = useCallback<NonNullable<DocumentProps["onLoadSuccess"]>>(
    (pdf) => {
      setNumPages(pdf.numPages)
      setLoading(false)
      setError(null)
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

  const scale = zoomLevel / 100

  return (
    <div
      ref={containerRef}
      className="flex h-full w-full flex-col items-center overflow-auto p-4"
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
          <div className="flex h-64 w-full items-center justify-center">
            <Spin size="large" tip="Loading document..." />
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
          // Single page mode
          <PdfPage
            pageNumber={currentPage}
            scale={scale}
            onSetRef={(el) => setPageRef(currentPage, el)}
          />
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
