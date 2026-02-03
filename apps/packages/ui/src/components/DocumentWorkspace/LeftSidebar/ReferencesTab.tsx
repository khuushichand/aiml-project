import React from "react"
import { useTranslation } from "react-i18next"
import { Empty, Skeleton, Tag, Tooltip, Input } from "antd"
import {
  BookOpen,
  ExternalLink,
  Download,
  Quote,
  User,
  Calendar,
  FileText,
  Search,
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import {
  useDocumentReferences,
  getReferenceUrl,
  formatCitationCount,
  type ReferenceEntry,
} from "@/hooks/document-workspace"
import { useConnectionStore } from "@/store/connection"

/**
 * Single reference card display.
 */
const ReferenceCard: React.FC<{ reference: ReferenceEntry; index: number }> = ({
  reference,
  index,
}) => {
  const { t } = useTranslation(["option", "common"])
  const url = getReferenceUrl(reference)

  // Use title if available, otherwise use first part of raw_text
  const displayTitle = reference.title || reference.raw_text.slice(0, 150)
  const isRawText = !reference.title
  const showCitations = reference.citation_count !== undefined && reference.citation_count > 0

  const cardContent = (
    <div className="rounded-lg border border-border bg-surface-alt p-3 text-sm transition-shadow hover:shadow-md">
      {/* Reference number */}
      <div className="flex items-start gap-2">
        <span className="shrink-0 rounded bg-surface px-1.5 py-0.5 text-xs font-medium text-text-muted">
          [{index + 1}]
        </span>
        <div className="min-w-0 flex-1">
          {/* Title */}
          <div
            className={`font-medium leading-snug ${
              isRawText ? "text-text-secondary text-xs" : "text-text"
            }`}
          >
            {displayTitle}
            {isRawText && displayTitle.length >= 150 && "..."}
          </div>

          {/* Authors */}
          {reference.authors && (
            <div className="mt-1 flex items-center gap-1 text-xs text-text-muted">
              <User className="h-3 w-3 shrink-0" />
              <span className="truncate">{reference.authors}</span>
            </div>
          )}

          {/* Year and Venue */}
          {(reference.year || reference.venue) && (
            <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
              {reference.year && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {reference.year}
                </span>
              )}
              {reference.venue && (
                <span className="truncate text-text-secondary">
                  {reference.venue}
                </span>
              )}
            </div>
          )}

          {/* Links and badges */}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {/* Citation count */}
            {showCitations && (
              <Tooltip title={t("option:documentWorkspace.citations", "Citations")}>
                <Tag
                  color="blue"
                  className="m-0 flex items-center gap-1 text-xs"
                >
                  <Quote className="h-3 w-3" />
                  {formatCitationCount(reference.citation_count)}{" "}
                  {t("option:documentWorkspace.citesShort", "cites")}
                </Tag>
              </Tooltip>
            )}

            {/* DOI link */}
            {reference.doi && (
              <a
                href={`https://doi.org/${reference.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                DOI
                <ExternalLink className="h-3 w-3" />
              </a>
            )}

            {/* arXiv link */}
            {reference.arxiv_id && (
              <Tag color="geekblue" className="m-0 px-1.5 py-0.5 text-xs">
                <a
                  href={`https://arxiv.org/abs/${reference.arxiv_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-current"
                >
                  arXiv
                </a>
              </Tag>
            )}

            {reference.semantic_scholar_id && (
              <Tag color="purple" className="m-0 px-1.5 py-0.5 text-xs">
                <a
                  href={`https://www.semanticscholar.org/paper/${reference.semantic_scholar_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-current"
                >
                  S2
                </a>
              </Tag>
            )}

            {/* Open Access PDF */}
            {reference.open_access_pdf && (
              <Tooltip
                title={t("option:documentWorkspace.openAccessPdf", "Open Access PDF")}
              >
                <a
                  href={reference.open_access_pdf}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-success hover:underline"
                >
                  <Download className="h-3 w-3" />
                  PDF
                </a>
              </Tooltip>
            )}

            {/* General URL if no specific links */}
            {url && !reference.doi && !reference.arxiv_id && !reference.semantic_scholar_id && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                {t("common:link", "Link")}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
        {url && (
          <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-muted" />
        )}
      </div>
    </div>
  )

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {cardContent}
      </a>
    )
  }

  return cardContent
}

/**
 * Empty state when no document is selected.
 */
const NoDocumentState: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  return (
    <div className="flex h-full items-center justify-center p-4">
      <Empty
        image={<BookOpen className="h-12 w-12 text-muted mx-auto mb-2" />}
        description={t(
          "option:documentWorkspace.noDocumentForReferences",
          "Open a document to view references"
        )}
      />
    </div>
  )
}

/**
 * Empty state when document has no references.
 */
const NoReferencesState: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  return (
    <div className="flex h-full items-center justify-center p-4">
      <Empty
        image={<FileText className="h-10 w-10 text-muted mx-auto mb-2" />}
        description={t(
          "option:documentWorkspace.noReferencesFound",
          "No references found in this document"
        )}
      />
    </div>
  )
}

/**
 * Empty state when server is not available.
 */
const ServerUnavailableState: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  return (
    <div className="flex h-full items-center justify-center p-4">
      <Empty
        image={<BookOpen className="h-10 w-10 text-muted mx-auto mb-2" />}
        description={t(
          "option:documentWorkspace.serverUnavailable",
          "Server connection required"
        )}
      />
    </div>
  )
}

/**
 * Empty state when filters hide all references.
 */
const NoFilteredReferencesState: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  return (
    <div className="flex h-full items-center justify-center p-4">
      <Empty
        image={<FileText className="h-10 w-10 text-muted mx-auto mb-2" />}
        description={t(
          "option:documentWorkspace.noReferencesMatchFilters",
          "No references match your search"
        )}
      />
    </div>
  )
}

/**
 * Loading state.
 */
const LoadingState: React.FC = () => {
  return (
    <div className="space-y-3 p-4">
      <Skeleton active paragraph={{ rows: 2 }} />
      <Skeleton active paragraph={{ rows: 2 }} />
      <Skeleton active paragraph={{ rows: 2 }} />
      <Skeleton active paragraph={{ rows: 2 }} />
    </div>
  )
}

/**
 * Error state.
 */
const ErrorState: React.FC<{ error: Error }> = ({ error }) => {
  const { t } = useTranslation(["option", "common"])
  return (
    <div className="flex h-full items-center justify-center p-4">
      <Empty
        description={
          <div>
            <p className="text-error mb-1">
              {t(
                "option:documentWorkspace.referencesError",
                "Failed to load references"
              )}
            </p>
            <p className="text-xs text-text-muted">
              {error.message || t("common:unknownError", "An unknown error occurred")}
            </p>
          </div>
        }
      />
    </div>
  )
}

/**
 * ReferencesTab - Display document bibliography/references.
 *
 * Features:
 * - Extract and display references from document content
 * - Enrich with citation counts from Semantic Scholar
 * - Show DOI, arXiv, and open access PDF links
 * - Loading and error states
 */
export const ReferencesTab: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)
  const [searchQuery, setSearchQuery] = React.useState("")
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  // Fetch references with enrichment enabled
  const { data, isLoading, error } = useDocumentReferences(activeDocumentId, true)

  // No document selected
  if (!activeDocumentId) {
    return <NoDocumentState />
  }

  // Server not available
  if (!isServerAvailable) {
    return <ServerUnavailableState />
  }

  // Loading state
  if (isLoading) {
    return <LoadingState />
  }

  // Error state
  if (error) {
    return <ErrorState error={error as Error} />
  }

  // No references found
  if (!data?.has_references || data.references.length === 0) {
    return <NoReferencesState />
  }

  const totalCount = data.references.length
  const arxivCount = data.references.filter((ref) => ref.arxiv_id).length
  const s2Count = data.references.filter((ref) => ref.semantic_scholar_id).length

  const query = searchQuery.trim().toLowerCase()
  const filteredReferences = data.references.filter((ref) => {
    if (!query) return true
    const haystack = [
      ref.title,
      ref.authors,
      ref.venue,
      ref.doi,
      ref.arxiv_id,
      ref.semantic_scholar_id,
      ref.raw_text,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
    return haystack.includes(query)
  })

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-3">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="text-sm font-medium text-text">
              {t("option:documentWorkspace.references", "References")}
            </span>
            <Tag className="m-0 rounded-full px-2 py-0.5 text-xs">
              {totalCount}
            </Tag>
          </div>
          {data.enrichment_source && (
            <span className="text-xs text-text-muted">
              {t("option:documentWorkspace.enriched", "enriched")}
            </span>
          )}
        </div>

        {/* Search */}
        <Input
          placeholder={t(
            "option:documentWorkspace.searchReferences",
            "Search references..."
          )}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          size="small"
          prefix={<Search className="h-4 w-4 text-muted" />}
          className="mb-3"
          allowClear
        />

        {/* Counts */}
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
          <span>
            {t("option:documentWorkspace.referencesCount", "{{count}} references", {
              count: totalCount,
            })}
          </span>
          {arxivCount > 0 && (
            <span>
              {arxivCount}{" "}
              {t("option:documentWorkspace.arxivShort", "arXiv")}
            </span>
          )}
          {s2Count > 0 && (
            <span>
              {s2Count} {t("option:documentWorkspace.s2Short", "S2")}
            </span>
          )}
        </div>

        {/* References list */}
        {filteredReferences.length === 0 ? (
          <NoFilteredReferencesState />
        ) : (
          <div className="space-y-2">
            {filteredReferences.map((ref, idx) => (
              <ReferenceCard key={idx} reference={ref} index={idx} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default ReferencesTab
