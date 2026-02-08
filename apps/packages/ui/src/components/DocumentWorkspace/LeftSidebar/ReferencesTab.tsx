import React from "react"
import { useTranslation } from "react-i18next"
import { Empty, Skeleton, Tag, Tooltip, Input, message, Button } from "antd"
import {
  BookOpen,
  ExternalLink,
  Download,
  Quote,
  User,
  Calendar,
  FileText,
  Search,
  Copy,
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import {
  useDocumentReferences,
  getReferenceUrl,
  formatCitationCount,
  type ReferenceEntry,
} from "@/hooks/document-workspace"
import { useConnectionStore } from "@/store/connection"
import { tldwClient } from "@/services/tldw"
import { useQueryClient } from "@tanstack/react-query"

/** FNV-1a 32-bit hash for generating stable, short identifiers from reference text. */
const hashReferenceText = (value: string): string => {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

const getReferenceKey = (reference: ReferenceEntry, index: number): string => {
  const stableId =
    reference.doi || reference.arxiv_id || reference.semantic_scholar_id
  if (stableId) {
    return stableId
  }

  const rawText = reference.raw_text?.trim()
  if (rawText) {
    return `ref-${hashReferenceText(rawText)}`
  }

  return `ref-${index}`
}

/**
 * Single reference card display.
 */
const ReferenceCard: React.FC<{
  reference: ReferenceEntry
  index: number
  onEnrich?: () => void
  isEnriching?: boolean
}> = ({ reference, index, onEnrich, isEnriching }) => {
  const { t } = useTranslation(["option", "common"])
  const [messageApi, contextHolder] = message.useMessage()
  const url = getReferenceUrl(reference)

  // Use title if available, otherwise use first part of raw_text
  const displayTitle = reference.title || reference.raw_text.slice(0, 150)
  const isRawText = !reference.title
  const showCitations = reference.citation_count !== undefined && reference.citation_count > 0
  const isEnriched =
    reference.citation_count !== undefined ||
    Boolean(reference.open_access_pdf) ||
    Boolean(reference.semantic_scholar_id)
  const copyText = reference.raw_text || displayTitle

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    event.stopPropagation()
    try {
      await navigator.clipboard.writeText(copyText)
      messageApi.success(
        t("option:documentWorkspace.referenceCopied", "Reference copied")
      )
    } catch {
      messageApi.error(
        t("option:documentWorkspace.referenceCopyFailed", "Copy failed")
      )
    }
  }

  const cardContent = (
    <div className="rounded-lg border border-border bg-surface-alt p-3 text-sm transition-shadow hover:shadow-md">
      {contextHolder}
      {/* Reference number */}
      <div className="flex items-start gap-2">
        <span className="shrink-0 rounded bg-surface px-1.5 py-0.5 text-xs font-medium text-text-muted">
          [{index + 1}]
        </span>
        <div className="min-w-0 flex-1">
          {onEnrich && !isEnriched && (
            <div className="mb-1 flex items-center justify-end">
              <Tooltip
                title={t("option:documentWorkspace.enrichReference", "Enrich reference")}
              >
                <Button
                  size="small"
                  type="text"
                  onClick={onEnrich}
                  loading={isEnriching}
                >
                  {t("option:documentWorkspace.enrichReferenceButton", "Enrich")}
                </Button>
              </Tooltip>
            </div>
          )}
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
        <div className="mt-1 flex shrink-0 items-center gap-2">
          <Tooltip title={t("option:documentWorkspace.copyReference", "Copy reference")}>
            <button
              type="button"
              onClick={handleCopy}
              className="rounded p-1 text-muted hover:bg-hover hover:text-text"
              aria-label={t("option:documentWorkspace.copyReference", "Copy reference")}
            >
              <Copy className="h-4 w-4" />
            </button>
          </Tooltip>
          {url && (
            <ExternalLink className="h-4 w-4 text-muted" />
          )}
        </div>
      </div>
    </div>
  )

  if (url) {
    const handleCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null
      if (event.defaultPrevented) {
        return
      }
      if (target?.closest("a, button, [role='button'], input, textarea, select")) {
        return
      }
      window.open(url, "_blank", "noopener,noreferrer")
    }

    const handleCardKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null
      if (event.defaultPrevented) {
        return
      }
      if (target?.closest("a, button, [role='button'], input, textarea, select")) {
        return
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault()
        window.open(url, "_blank", "noopener,noreferrer")
      }
    }

    return (
      <div
        role="link"
        tabIndex={0}
        onClick={handleCardClick}
        onKeyDown={handleCardKeyDown}
        aria-label={t(
          "option:documentWorkspace.referenceOpenAriaLabel",
          "Open reference: {{title}}",
          { title: displayTitle }
        )}
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {cardContent}
      </div>
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
  const [enrich, setEnrich] = React.useState(false)
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"
  const queryClient = useQueryClient()
  const [enrichingRefs, setEnrichingRefs] = React.useState<Record<string, boolean>>({})

  React.useEffect(() => {
    setEnrich(false)
    setEnrichingRefs({})
    setSearchQuery("")
  }, [activeDocumentId])

  // Fetch references with enrichment enabled
  const { data, isLoading, error, isFetching } = useDocumentReferences(
    activeDocumentId,
    enrich
  )

  const references = data?.references ?? []
  const query = searchQuery.trim().toLowerCase()
  const filteredReferences = React.useMemo(() => {
    return references
      .map((ref, index) => ({ ref, index }))
      .filter(({ ref }) => {
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
  }, [query, references])

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

  const totalCount = references.length
  const arxivCount = references.filter((ref) => ref.arxiv_id).length
  const s2Count = references.filter((ref) => ref.semantic_scholar_id).length

  const handleEnrichReference = async (index: number, key: string) => {
    if (!activeDocumentId) return
    setEnrichingRefs((prev) => ({ ...prev, [key]: true }))
    try {
      const response = await tldwClient.getDocumentReferences(activeDocumentId, {
        enrich: true,
        referenceIndex: index,
      })
      queryClient.setQueryData(
        ["document-references", activeDocumentId, false],
        response
      )
      queryClient.setQueryData(
        ["document-references", activeDocumentId, true],
        response
      )
    } catch (err) {
      console.error("Failed to enrich reference:", err)
      message.error(
        t(
          "option:documentWorkspace.enrichReferenceFailed",
          "Failed to enrich reference"
        )
      )
    } finally {
      setEnrichingRefs((prev) => ({ ...prev, [key]: false }))
    }
  }

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
          <div className="flex items-center gap-2">
            {data.enrichment_source && (
              <span className="text-xs text-text-muted">
                {t("option:documentWorkspace.enriched", "enriched")}
              </span>
            )}
            {!enrich && (
              <Tooltip
                title={t(
                  "option:documentWorkspace.enrichReferencesHint",
                  "Fetch citation counts and links (limited)"
                )}
              >
                <Button
                  size="small"
                  type="default"
                  onClick={() => setEnrich(true)}
                  disabled={isFetching}
                >
                  {t("option:documentWorkspace.enrichReferences", "Enrich")}
                </Button>
              </Tooltip>
            )}
            {enrich && isFetching && (
              <span className="text-xs text-text-muted">
                {t("option:documentWorkspace.enriching", "Enriching...")}
              </span>
            )}
          </div>
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
            {filteredReferences.map(({ ref, index }) => {
              const key = getReferenceKey(ref, index)
              return (
                <ReferenceCard
                  key={key}
                  reference={ref}
                  index={index}
                  isEnriching={Boolean(enrichingRefs[key])}
                  onEnrich={() => handleEnrichReference(index, key)}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default ReferencesTab
