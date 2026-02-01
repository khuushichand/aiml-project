import React from "react"
import { useTranslation } from "react-i18next"
import { Empty, Skeleton, Alert } from "antd"
import { Image as ImageIcon } from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useDocumentFigures } from "@/hooks/document-workspace/useDocumentFigures"

/**
 * FiguresTab - Displays extracted images/figures from the current document.
 *
 * Features:
 * - Grid display of extracted figures
 * - Click to navigate to the source page
 * - Shows page number for each figure
 * - Loading and empty states
 */
export const FiguresTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)

  const { data, isLoading, error } = useDocumentFigures(activeDocumentId)

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

  // Loading state
  if (isLoading) {
    return (
      <div className="p-3 space-y-3">
        <Skeleton.Image active className="!w-full !h-24" />
        <Skeleton.Image active className="!w-full !h-24" />
        <Skeleton.Image active className="!w-full !h-24" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="p-3">
        <Alert
          type="error"
          message={t("option:documentWorkspace.figuresError", "Failed to load figures")}
          description={error.message}
          showIcon
        />
      </div>
    )
  }

  // No figures found
  if (!data?.has_figures || data.figures.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<ImageIcon className="mx-auto h-12 w-12 text-muted" />}
          description={t(
            "option:documentWorkspace.noFigures",
            "No figures found in this document"
          )}
        />
      </div>
    )
  }

  // Handle figure click - navigate to the page
  const handleFigureClick = (page: number) => {
    setCurrentPage(page)
  }

  return (
    <div className="h-full overflow-auto p-3">
      {/* Header with count */}
      <div className="mb-3 text-xs text-muted">
        {data.total_count} {data.total_count === 1 ? "figure" : "figures"}{" "}
        {t("option:documentWorkspace.figuresFound", "found")}
      </div>

      {/* Figures grid */}
      <div className="grid grid-cols-2 gap-3">
        {data.figures.map((figure) => (
          <button
            key={figure.id}
            onClick={() => handleFigureClick(figure.page)}
            className="group relative overflow-hidden rounded border border-border bg-surface transition-all hover:border-primary hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {figure.data_url ? (
              <img
                src={figure.data_url}
                alt={figure.caption || `Figure on page ${figure.page}`}
                className="h-auto w-full object-contain"
                style={{ maxHeight: 160 }}
                loading="lazy"
              />
            ) : (
              <div className="flex h-24 w-full items-center justify-center bg-surface2">
                <ImageIcon className="h-8 w-8 text-muted" />
              </div>
            )}

            {/* Page number badge */}
            <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 text-center text-xs text-white">
              {t("option:documentWorkspace.page", "Page")} {figure.page}
            </div>

            {/* Caption tooltip on hover (if available) */}
            {figure.caption && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-2 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                {figure.caption}
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Dimensions info (collapsed by default) */}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs text-muted hover:text-text">
          {t("option:documentWorkspace.figureDetails", "Figure details")}
        </summary>
        <div className="mt-2 space-y-1 text-xs text-muted">
          {data.figures.map((figure) => (
            <div key={figure.id} className="flex justify-between">
              <span>
                {t("option:documentWorkspace.page", "Page")} {figure.page}
              </span>
              <span>
                {figure.width} x {figure.height}px ({figure.format})
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

export default FiguresTab
