import React, { useCallback, useEffect, useRef } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "antd"
import { FileText, AlertCircle } from "lucide-react"
import type { PdfDocumentProxy } from "@/hooks/document-workspace/usePdfSearch"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { ViewerToolbar } from "./ViewerToolbar"
import { PdfDocument } from "./PdfViewer/PdfDocument"
import { PdfSearch } from "./PdfSearch"
import { EpubViewer } from "./EpubViewer"
import type { DocumentType } from "../types"

interface DocumentViewerProps {
  className?: string
  onOpenLibrary?: () => void
  onOpenUpload?: () => void
  onReloadDocument?: (mediaId: number, docTypeHint?: DocumentType | null) => Promise<void> | void
}

const shouldRetryBlobLoad = (error: Error, url?: string): boolean => {
  if (!url || !url.startsWith("blob:")) return false
  const message = String(error?.message || "")
  const status = (error as Error & { status?: number })?.status
  if (status === 0) return true
  if ((error as Error & { name?: string })?.name === "UnexpectedResponseException") return true
  return [
    "Unexpected server response",
    "ERR_FILE_NOT_FOUND",
    "Failed to fetch",
    "NetworkError",
    "Invalid name"
  ].some((needle) => message.includes(needle))
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  className,
  onOpenLibrary,
  onOpenUpload,
  onReloadDocument
}) => {
  const { t } = useTranslation(["option", "common"])
  const pdfDocumentRef = useRef<PdfDocumentProxy | null>(null)
  const reloadAttemptsRef = useRef<Map<number, number>>(new Map())
  const reloadInFlightRef = useRef<Set<number>>(new Set())

  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const activeDocumentType = useDocumentWorkspaceStore(
    (s) => s.activeDocumentType
  )
  const openDocuments = useDocumentWorkspaceStore((s) => s.openDocuments)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const totalPages = useDocumentWorkspaceStore((s) => s.totalPages)
  const zoomLevel = useDocumentWorkspaceStore((s) => s.zoomLevel)
  const viewMode = useDocumentWorkspaceStore((s) => s.viewMode)

  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)
  const setTotalPages = useDocumentWorkspaceStore((s) => s.setTotalPages)
  const setZoomLevel = useDocumentWorkspaceStore((s) => s.setZoomLevel)
  const setViewMode = useDocumentWorkspaceStore((s) => s.setViewMode)
  const goToNextPage = useDocumentWorkspaceStore((s) => s.goToNextPage)
  const goToPreviousPage = useDocumentWorkspaceStore((s) => s.goToPreviousPage)
  const setSearchOpen = useDocumentWorkspaceStore((s) => s.setSearchOpen)
  const searchOpen = useDocumentWorkspaceStore((s) => s.searchOpen)
  const currentPercentage = useDocumentWorkspaceStore((s) => s.currentPercentage)

  const activeDocument = openDocuments.find((d) => d.id === activeDocumentId)

  // Keyboard navigation and search shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!activeDocumentId) return

      // Cmd/Ctrl+F to open search (always handle, even in inputs)
      if ((e.metaKey || e.ctrlKey) && e.key === "f") {
        e.preventDefault()
        setSearchOpen(true)
        return
      }

      // Don't handle navigation if focus is in an input (but search already handled above)
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
          goToNextPage()
          break
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault()
          goToPreviousPage()
          break
        case "Home":
          e.preventDefault()
          setCurrentPage(1)
          break
        case "End":
          e.preventDefault()
          if (totalPages > 0) {
            setCurrentPage(totalPages)
          }
          break
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [
    activeDocumentId,
    totalPages,
    goToNextPage,
    goToPreviousPage,
    setCurrentPage,
    setSearchOpen
  ])

  const handleLoadSuccess = useCallback(
    (numPages: number) => {
      setTotalPages(numPages)
      if (activeDocumentId !== null) {
        reloadAttemptsRef.current.delete(activeDocumentId)
      }
    },
    [activeDocumentId, setTotalPages]
  )

  const handleLoadError = useCallback(
    (error: Error) => {
      console.error("Failed to load document:", error)
      if (!onReloadDocument) return
      if (activeDocumentType !== "pdf") return
      if (activeDocumentId === null) return
      if (!activeDocument) return
      const { url, type } = activeDocument
      if (!url) return
      if (!shouldRetryBlobLoad(error, url)) return
      const attempts = reloadAttemptsRef.current.get(activeDocumentId) ?? 0
      if (attempts >= 1) return
      if (reloadInFlightRef.current.has(activeDocumentId)) return
      reloadAttemptsRef.current.set(activeDocumentId, attempts + 1)
      reloadInFlightRef.current.add(activeDocumentId)
      Promise.resolve(onReloadDocument(activeDocumentId, type))
        .finally(() => {
          reloadInFlightRef.current.delete(activeDocumentId)
        })
    },
    [activeDocument, activeDocumentId, activeDocumentType, onReloadDocument]
  )

  if (!activeDocumentId || !activeDocument) {
    return (
      <div
        className={`flex h-full flex-col items-center justify-center gap-4 p-8 text-center ${className || ""}`}
      >
        <FileText className="h-16 w-16 text-muted" />
        <div>
          <h3 className="text-lg font-medium">
            {t("option:documentWorkspace.noDocument", "No document selected")}
          </h3>
          <p className="text-sm text-muted">
            {t(
              "option:documentWorkspace.noDocumentHint",
              "Open a document from your media library to start reading"
            )}
          </p>
        </div>
        {(onOpenLibrary || onOpenUpload) && (
          <div className="flex flex-wrap items-center justify-center gap-2">
            {onOpenUpload && (
              <Button type="primary" onClick={onOpenUpload}>
                {t("option:documentWorkspace.upload", "Upload")}
              </Button>
            )}
            {onOpenLibrary && (
              <Button onClick={onOpenLibrary}>
                {t("option:documentWorkspace.openDocument", "Open document")}
              </Button>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderViewer = () => {
    switch (activeDocumentType) {
      case "pdf":
        return (
          <PdfDocument
            url={activeDocument.url}
            documentId={activeDocumentId}
            currentPage={currentPage}
            zoomLevel={zoomLevel}
            viewMode={viewMode}
            onLoadSuccess={handleLoadSuccess}
            onLoadError={handleLoadError}
            onPageChange={setCurrentPage}
            pdfDocumentRef={pdfDocumentRef}
          />
        )
      case "epub":
        return (
          <EpubViewer
            url={activeDocument.url!}
            documentId={activeDocumentId}
            onLoadSuccess={({ chapterCount }) => {
              // chapterCount is available if needed
            }}
            onLoadError={handleLoadError}
          />
        )
      default:
        return (
          <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
            <AlertCircle className="h-12 w-12 text-warning" />
            <p className="text-muted">Unsupported document type</p>
          </div>
        )
    }
  }

  return (
    <div className={`flex h-full flex-col ${className || ""}`}>
      <ViewerToolbar
        currentPage={currentPage}
        totalPages={totalPages}
        zoomLevel={zoomLevel}
        viewMode={viewMode}
        documentType={activeDocumentType}
        percentage={currentPercentage}
        onPageChange={setCurrentPage}
        onZoomChange={setZoomLevel}
        onViewModeChange={setViewMode}
        onPreviousPage={goToPreviousPage}
        onNextPage={goToNextPage}
      />
      <div className="relative min-h-0 flex-1 overflow-auto bg-neutral-200 dark:bg-neutral-800">
        {activeDocumentType === "pdf" && (
          <PdfSearch pdfDocumentRef={pdfDocumentRef} />
        )}
        {renderViewer()}
      </div>
    </div>
  )
}

export default DocumentViewer
