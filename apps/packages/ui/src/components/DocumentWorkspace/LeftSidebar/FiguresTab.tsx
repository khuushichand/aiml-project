import React from "react"
import { useTranslation } from "react-i18next"
import { Document, Page } from "react-pdf"
import { Empty, Skeleton, Alert } from "antd"
import { Image as ImageIcon } from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

/**
 * FiguresTab - Displays page thumbnails for the current PDF document.
 *
 * Features:
 * - Grid display of page thumbnails
 * - Click to navigate to the source page
 * - Highlights current page
 * - Loading and empty states
 */
export const FiguresTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const activeDocumentType = useDocumentWorkspaceStore((s) => s.activeDocumentType)
  const openDocuments = useDocumentWorkspaceStore((s) => s.openDocuments)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)
  const totalPages = useDocumentWorkspaceStore((s) => s.totalPages)

  const [numPages, setNumPages] = React.useState<number>(0)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  const activeDocument = openDocuments.find((doc) => doc.id === activeDocumentId)
  const documentUrl = activeDocument?.url
  const pageCount = totalPages || numPages

  // No document selected
  if (!activeDocumentId) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<ImageIcon className="mx-auto h-12 w-12 text-muted" />}
          description={t(
            "option:documentWorkspace.figuresNoDocument",
            "Open a document to view figures"
          )}
        />
      </div>
    )
  }

  if (activeDocumentType !== "pdf") {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<ImageIcon className="mx-auto h-12 w-12 text-muted" />}
          description={t(
            "option:documentWorkspace.thumbnailsPdfOnly",
            "Thumbnails are available for PDF documents."
          )}
        />
      </div>
    )
  }

  if (!documentUrl) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<ImageIcon className="mx-auto h-12 w-12 text-muted" />}
          description={t(
            "option:documentWorkspace.missingDocumentFile",
            "No document file available"
          )}
        />
      </div>
    )
  }

  const handleThumbnailClick = (page: number) => {
    setCurrentPage(page)
  }

  return (
    <div className="h-full overflow-auto p-3">
      <Document
        file={documentUrl}
        onLoadSuccess={(pdf) => {
          setNumPages(pdf.numPages)
          setLoadError(null)
        }}
        onLoadError={(error) => {
          setLoadError(error.message || "Failed to load PDF")
        }}
        loading={
          <div className="space-y-3">
            <Skeleton.Image active className="!w-full !h-24" />
            <Skeleton.Image active className="!w-full !h-24" />
            <Skeleton.Image active className="!w-full !h-24" />
          </div>
        }
        error={
          <Alert
            type="error"
            message={t("option:documentWorkspace.figuresError", "Failed to load document")}
            description={loadError || t("common:unknownError", "An unknown error occurred")}
            showIcon
          />
        }
      >
        {pageCount > 0 ? (
          <>
            <div className="mb-2 text-xs text-muted">
              {t("option:documentWorkspace.pagesCount", "{{count}} pages", {
                count: pageCount,
              })}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: pageCount }, (_, index) => {
                const pageNumber = index + 1
                const isActive = pageNumber === currentPage
                return (
                  <button
                    key={`thumb-${pageNumber}`}
                    onClick={() => handleThumbnailClick(pageNumber)}
                    className={`group relative overflow-hidden rounded border transition-all focus:outline-none focus:ring-2 focus:ring-primary ${
                      isActive
                        ? "border-primary shadow-md"
                        : "border-border hover:border-primary"
                    }`}
                  >
                    <Page
                      pageNumber={pageNumber}
                      scale={0.25}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      loading=""
                    />
                    <span className="absolute bottom-1 left-1/2 -translate-x-1/2 rounded bg-black/70 px-2 py-0.5 text-xs text-white">
                      {pageNumber}
                    </span>
                  </button>
                )
              })}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center p-4">
            <Empty
              image={<ImageIcon className="mx-auto h-12 w-12 text-muted" />}
              description={t(
                "option:documentWorkspace.noPages",
                "No pages found in this document"
              )}
            />
          </div>
        )}
      </Document>
    </div>
  )
}

export default FiguresTab
