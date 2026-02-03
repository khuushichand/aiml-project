import React from "react"
import { useTranslation } from "react-i18next"
import { Empty, Skeleton } from "antd"
import { ChevronRight, ChevronDown, FileText } from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { usePdfOutline } from "@/hooks/document-workspace"
import type { TocItem, DocumentType } from "../types"

interface TocEntryProps {
  item: TocItem
  currentPage: number
  documentType: DocumentType | null
  onNavigate: (page: number, href?: string) => void
  depth?: number
}

const TocEntry: React.FC<TocEntryProps> = ({
  item,
  currentPage,
  documentType,
  onNavigate,
  depth = 0
}) => {
  const { t } = useTranslation(["option", "common"])
  const [expanded, setExpanded] = React.useState(true)
  const hasChildren = item.children && item.children.length > 0

  // Determine if this item or any of its children contains the current page
  const containsCurrentPage = React.useMemo(() => {
    const checkContains = (entry: TocItem): boolean => {
      if (entry.page === currentPage) return true
      if (entry.children) {
        return entry.children.some(checkContains)
      }
      return false
    }
    return checkContains(item)
  }, [item, currentPage])

  const isActive = item.page === currentPage

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onNavigate(item.page, item.href)
  }

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded(!expanded)
  }

  // Indent based on depth (max 4 levels of indent)
  const paddingLeft = Math.min(depth, 4) * 12 + 8

  // For EPUB, don't show page numbers (they're meaningless)
  const showPageNumber = documentType === "pdf"

  return (
    <div
      role="treeitem"
      aria-expanded={hasChildren ? expanded : undefined}
      aria-current={isActive ? "page" : undefined}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onNavigate(item.page, item.href)
        }
      }}
    >
      <div
        className={`
          group flex w-full items-center gap-1 rounded px-2 py-1.5 text-left text-sm
          transition-colors hover:bg-hover
          ${isActive ? "bg-primary/10 text-primary font-medium" : "text-text"}
          ${containsCurrentPage && !isActive ? "text-text-secondary" : ""}
        `}
        style={{ paddingLeft }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={handleToggle}
            className="shrink-0 rounded p-0.5 hover:bg-hover-deep"
            aria-label={
              expanded
                ? t("option:documentWorkspace.collapseSection", "Collapse section")
                : t("option:documentWorkspace.expandSection", "Expand section")
            }
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-4" aria-hidden="true" /> // Spacer for alignment
        )}

        <button
          type="button"
          onClick={handleClick}
          className="flex min-w-0 flex-1 items-center gap-1 text-left"
        >
          <span className="flex-1 truncate" title={item.title}>
            {item.title}
          </span>

          {showPageNumber && (
            <span
              className={`
                shrink-0 text-xs tabular-nums
                ${isActive ? "text-primary" : "text-muted"}
                opacity-0 group-hover:opacity-100
                ${isActive ? "opacity-100" : ""}
              `}
              aria-label={t("option:documentWorkspace.pageNumber", "Page {{page}}", { page: item.page })}
            >
              {item.page}
            </span>
          )}
        </button>
      </div>

      {hasChildren && expanded && (
        <div role="group">
          {item.children!.map((child, idx) => (
            <TocEntry
              key={`${child.page}-${idx}`}
              item={child}
              currentPage={currentPage}
              documentType={documentType}
              onNavigate={onNavigate}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export const TableOfContentsTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const activeDocumentType = useDocumentWorkspaceStore((s) => s.activeDocumentType)
  const currentPage = useDocumentWorkspaceStore((s) => s.currentPage)
  const setCurrentPage = useDocumentWorkspaceStore((s) => s.setCurrentPage)

  // For PDF, fetch outline from server
  // For EPUB, outline comes from the viewer component via custom event
  const {
    data: pdfOutline,
    isLoading: pdfLoading,
    error: pdfError
  } = usePdfOutline(activeDocumentType === "pdf" ? activeDocumentId : null)

  // EPUB outline state - populated by EpubViewer via custom event
  const [epubOutline, setEpubOutline] = React.useState<TocItem[] | null>(null)
  const [epubLoading, setEpubLoading] = React.useState(false)

  // Listen for EPUB outline updates
  React.useEffect(() => {
    const handleEpubOutline = (e: CustomEvent<{ documentId: number; items: TocItem[] }>) => {
      if (e.detail.documentId === activeDocumentId) {
        setEpubOutline(e.detail.items)
        setEpubLoading(false)
      }
    }

    const handleEpubLoading = (e: CustomEvent<{ documentId: number }>) => {
      if (e.detail.documentId === activeDocumentId) {
        setEpubLoading(true)
        setEpubOutline(null)
      }
    }

    window.addEventListener("epub-outline-ready", handleEpubOutline as EventListener)
    window.addEventListener("epub-loading", handleEpubLoading as EventListener)

    return () => {
      window.removeEventListener("epub-outline-ready", handleEpubOutline as EventListener)
      window.removeEventListener("epub-loading", handleEpubLoading as EventListener)
    }
  }, [activeDocumentId])

  // Reset EPUB outline when document changes
  React.useEffect(() => {
    if (activeDocumentType === "epub") {
      setEpubLoading(true)
    } else {
      setEpubOutline(null)
      setEpubLoading(false)
    }
  }, [activeDocumentId, activeDocumentType])

  const handleNavigate = React.useCallback(
    (page: number, href?: string) => {
      if (activeDocumentType === "epub" && href) {
        // For EPUB, dispatch event to navigate to href
        window.dispatchEvent(
          new CustomEvent("epub-navigate", {
            detail: { href, documentId: activeDocumentId }
          })
        )
      } else {
        // For PDF, use page navigation
        setCurrentPage(page)
      }
    },
    [activeDocumentType, activeDocumentId, setCurrentPage]
  )

  // Determine which outline to use
  const outline = activeDocumentType === "epub" ? epubOutline : pdfOutline?.items
  const isLoading = activeDocumentType === "epub" ? epubLoading : pdfLoading
  const error = activeDocumentType === "epub" ? null : pdfError

  if (!activeDocumentId) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<FileText className="mx-auto h-12 w-12 text-muted" />}
          description={t(
            "option:documentWorkspace.noDocumentSelected",
            "No document selected"
          )}
        />
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-2 p-4">
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          description={t(
            "option:documentWorkspace.errorLoadingToc",
            "Failed to load table of contents"
          )}
        />
      </div>
    )
  }

  if (!outline || outline.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Empty
          image={<FileText className="mx-auto h-12 w-12 text-muted" />}
          description={
            <div className="text-center">
              <p className="mb-1 text-sm text-text-secondary">
                {t(
                  "option:documentWorkspace.noToc",
                  "No table of contents"
                )}
              </p>
              <p className="text-xs text-muted">
                {t(
                  "option:documentWorkspace.noTocHint",
                  "This document doesn't have an embedded outline"
                )}
              </p>
            </div>
          }
        />
      </div>
    )
  }

  return (
    <nav
      className="h-full overflow-y-auto"
      aria-label={t("option:documentWorkspace.tableOfContents", "Table of contents")}
    >
      <div className="py-2" role="tree">
        {outline.map((item, idx) => (
          <TocEntry
            key={`${item.page}-${idx}`}
            item={item}
            currentPage={currentPage}
            documentType={activeDocumentType}
            onNavigate={handleNavigate}
          />
        ))}
      </div>
    </nav>
  )
}

export default TableOfContentsTab
