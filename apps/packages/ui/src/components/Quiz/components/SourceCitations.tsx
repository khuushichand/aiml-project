import React from "react"
import { Typography } from "antd"
import type { SourceCitation } from "@/services/quizzes"

interface SourceCitationsProps {
  citations?: SourceCitation[] | null
  fallbackMediaId?: number | null
  className?: string
}

const toPositiveInteger = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  const normalized = Math.trunc(value)
  return normalized > 0 ? normalized : null
}

const toSafeDirectHref = (value: unknown): string | null => {
  if (typeof value !== "string") return null
  const directUrl = value.trim()
  if (!directUrl) return null

  // Allow internal app-relative links.
  if (directUrl.startsWith("/")) {
    return directUrl
  }

  try {
    const parsed = new URL(directUrl)
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString()
    }
  } catch {
    return null
  }

  return null
}

const toLinkHref = (
  citation: SourceCitation,
  fallbackMediaId?: number | null
): string | null => {
  const directHref = toSafeDirectHref(citation.source_url)
  if (directHref) return directHref

  const mediaId = toPositiveInteger(citation.media_id) ?? toPositiveInteger(fallbackMediaId)
  if (mediaId == null) return null

  const params = new URLSearchParams({ id: String(mediaId) })
  const chunkId = typeof citation.chunk_id === "string" ? citation.chunk_id.trim() : ""
  if (chunkId.length > 0) {
    params.set("chunk_id", chunkId)
  }
  if (typeof citation.timestamp_seconds === "number" && Number.isFinite(citation.timestamp_seconds)) {
    params.set("t", String(Math.max(0, Math.floor(citation.timestamp_seconds))))
  }
  return `/media?${params.toString()}`
}

const buildCitationLabel = (citation: SourceCitation, index: number): string => {
  const label = typeof citation.label === "string" ? citation.label.trim() : ""
  if (label.length > 0) return label
  return `Source ${index + 1}`
}

export const SourceCitations: React.FC<SourceCitationsProps> = ({
  citations,
  fallbackMediaId,
  className
}) => {
  if (!Array.isArray(citations) || citations.length === 0) return null

  const normalized = citations.filter((entry) => entry && typeof entry === "object")
  if (normalized.length === 0) return null

  return (
    <div className={className ?? "space-y-1"}>
      <Typography.Text className="block text-xs font-medium text-text-muted">
        Source citations
      </Typography.Text>
      <ul className="list-disc pl-4 text-xs text-text-muted space-y-1">
        {normalized.map((citation, index) => {
          const href = toLinkHref(citation, fallbackMediaId)
          const label = buildCitationLabel(citation, index)
          const quote = typeof citation.quote === "string" ? citation.quote.trim() : ""
          return (
            <li key={`${label}-${index}`}>
              {href ? (
                <Typography.Link href={href} target="_blank" rel="noopener noreferrer">
                  {label}
                </Typography.Link>
              ) : (
                <span>{label}</span>
              )}
              {quote.length > 0 && <span>{`: ${quote}`}</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default SourceCitations
