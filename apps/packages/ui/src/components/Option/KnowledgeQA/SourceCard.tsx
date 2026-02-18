/**
 * SourceCard - Individual source/document display
 */

import React, { useCallback } from "react"
import {
  FileText,
  MessageSquare,
  ExternalLink,
  Copy,
  Check,
  Quote,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { RagResult } from "./types"
import {
  formatChunkPosition,
  formatSourceDate,
  getRelevanceDescriptor,
  getSourceTypeLabel,
} from "./sourceListUtils"

export type SourceAskTemplate = "detail" | "summary" | "quotes"

type SourceCardProps = {
  result: RagResult
  index: number // 1-based for display
  isCited: boolean
  isFocused: boolean
  onAskAbout: (result: RagResult, template: SourceAskTemplate) => void
  onViewFull: (result: RagResult, index: number) => void
  onSourceFeedback: (result: RagResult, index: number, thumb: "up" | "down") => void
  onRetrySourceFeedback: (result: RagResult, index: number) => void
  feedbackThumb: "up" | "down" | null
  feedbackSubmitting: boolean
  feedbackError: string | null
  className?: string
}

function getSourceIcon(sourceType?: string) {
  switch (sourceType) {
    case "notes":
      return FileText
    case "characters":
      return MessageSquare
    case "chats":
      return MessageSquare
    default:
      return FileText
  }
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength).trimEnd() + "..."
}

function buildCitationText(result: RagResult, fallbackIndex: number): string {
  const title =
    result.metadata?.title || result.metadata?.source || `Source ${fallbackIndex}`
  const pageNumber = result.metadata?.page_number
  const url = result.metadata?.url

  const segments = [title]
  if (typeof pageNumber === "number") {
    segments.push(`(Page ${pageNumber})`)
  }
  if (url) {
    segments.push(`- ${url}`)
  }
  return segments.join(" ")
}

export function SourceCard({
  result,
  index,
  isCited,
  isFocused,
  onAskAbout,
  onViewFull,
  onSourceFeedback,
  onRetrySourceFeedback,
  feedbackThumb,
  feedbackSubmitting,
  feedbackError,
  className,
}: SourceCardProps) {
  const [copiedState, setCopiedState] = React.useState<"text" | "citation" | null>(null)
  const [isExpanded, setIsExpanded] = React.useState(false)
  const [askTemplate, setAskTemplate] = React.useState<SourceAskTemplate>("detail")

  const title = result.metadata?.title || result.metadata?.source || `Source ${index}`
  const content = result.content || result.text || result.chunk || ""
  const excerpt = isExpanded ? content : truncateText(content, 300)
  const canExpand = content.length > 300
  const url = result.metadata?.url
  const score = result.score
  const sourceType = result.metadata?.source_type || "media_db"
  const sourceTypeLabel = getSourceTypeLabel(sourceType)
  const chunkPosition = formatChunkPosition(result.metadata?.chunk_id)
  const sourceDate = formatSourceDate(result)
  const relevanceDescriptor = getRelevanceDescriptor(score)

  const Icon = getSourceIcon(sourceType)

  const handleCopyText = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedState("text")
      setTimeout(() => setCopiedState(null), 2000)
    } catch (error) {
      console.error("Failed to copy source text:", error)
    }
  }, [content])

  const handleCopyCitation = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(buildCitationText(result, index))
      setCopiedState("citation")
      setTimeout(() => setCopiedState(null), 2000)
    } catch (error) {
      console.error("Failed to copy source citation:", error)
    }
  }, [index, result])

  const handleOpenExternal = useCallback(() => {
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer")
    }
  }, [url])

  return (
    <div
      id={`source-card-${index - 1}`}
      role="listitem"
      className={cn(
        "group rounded-lg border transition-all duration-200",
        isFocused
          ? "border-primary bg-primary/5 ring-2 ring-primary/20"
          : isCited
            ? "border-border bg-surface hover:border-primary/30"
            : "border-border/70 bg-surface/90 hover:border-border-strong",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-2.5 p-3 pb-2 sm:gap-3 sm:p-4 sm:pb-2">
        {/* Index badge */}
        <div
          className={cn(
            "flex-shrink-0 h-6 w-6 rounded-md flex items-center justify-center text-xs font-medium sm:h-7 sm:w-7 sm:text-sm",
            isCited ? "bg-primary text-white dark:text-slate-900" : "bg-muted text-text"
          )}
        >
          {index}
        </div>

        {/* Title and metadata */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2">
            <Icon className="w-4 h-4 text-text-muted mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <h4 className="font-medium text-sm truncate" title={title}>
                {title}
              </h4>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-text-muted sm:gap-2 sm:text-xs">
                {relevanceDescriptor && (
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5",
                      relevanceDescriptor.className
                    )}
                    title={`${relevanceDescriptor.label} (${relevanceDescriptor.percent}%)`}
                  >
                    {relevanceDescriptor.label} ({relevanceDescriptor.percent}%)
                  </span>
                )}
                <span>{sourceTypeLabel}</span>
                {chunkPosition ? <span>{chunkPosition}</span> : null}
                {sourceDate ? <span>{sourceDate}</span> : null}
                {isCited && (
                  <span className="flex items-center gap-1 text-primary">
                    <Quote className="w-3 h-3" />
                    Cited
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content excerpt */}
      <div className="px-3 pb-2 sm:px-4 sm:pb-3">
        <p className="text-xs text-text-muted leading-relaxed whitespace-pre-wrap sm:text-sm">
          {excerpt}
        </p>
        {canExpand && (
          <button
            type="button"
            onClick={() => setIsExpanded((previous) => !previous)}
            className="mt-2 text-xs font-medium text-primary hover:text-primaryStrong transition-colors"
          >
            {isExpanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/50 bg-muted/20 px-3 py-2 sm:px-4">
        <div className="flex flex-wrap items-center gap-1">
          <button
            type="button"
            onClick={() => onViewFull(result, index)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-muted text-text hover:bg-surface2 transition-colors"
            title="View the full source content"
            aria-label={`View full source ${index}`}
          >
            <FileText className="w-3.5 h-3.5" />
            View full
          </button>

          <div className="inline-flex items-center rounded-md border border-border bg-surface">
            <button
              type="button"
              onClick={() => onAskAbout(result, askTemplate)}
              title="Create a question about this source"
              aria-label={`Ask about ${title}`}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-text hover:bg-muted transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Ask
            </button>
            <select
              aria-label={`Ask template for ${title}`}
              value={askTemplate}
              onChange={(event) =>
                setAskTemplate(event.target.value as SourceAskTemplate)
              }
              className="border-l border-border bg-transparent px-1.5 py-1.5 text-xs text-text-muted focus:outline-none"
            >
              <option value="detail">Tell me more</option>
              <option value="summary">Summarize</option>
              <option value="quotes">Key quotes</option>
            </select>
          </div>

          <button
            type="button"
            onClick={handleCopyText}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-muted text-text hover:bg-surface2 transition-colors"
            title="Copy full source text"
          >
            {copiedState === "text" ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Copied text
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy text
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleCopyCitation}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-muted text-text hover:bg-surface2 transition-colors"
            title="Copy citation"
          >
            {copiedState === "citation" ? "Copied citation" : "Copy citation"}
          </button>
        </div>

        <button
          type="button"
          onClick={handleOpenExternal}
          disabled={!url}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors",
            url
              ? "text-text-muted hover:text-text hover:bg-muted"
              : "text-text-subtle opacity-60 cursor-not-allowed"
          )}
          title={url ? "Open original" : "No external URL available"}
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Open
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-t border-border/50 text-xs">
        <span className="text-text-muted">Relevant?</span>
        <button
          type="button"
          onClick={() => onSourceFeedback(result, index, "up")}
          disabled={feedbackSubmitting}
          aria-pressed={feedbackThumb === "up"}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors",
            feedbackThumb === "up"
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-text-muted hover:text-text hover:bg-muted",
            feedbackSubmitting && "opacity-60 cursor-not-allowed"
          )}
        >
          <ThumbsUp className="w-3.5 h-3.5" />
          Yes
        </button>
        <button
          type="button"
          onClick={() => onSourceFeedback(result, index, "down")}
          disabled={feedbackSubmitting}
          aria-pressed={feedbackThumb === "down"}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors",
            feedbackThumb === "down"
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-text-muted hover:text-text hover:bg-muted",
            feedbackSubmitting && "opacity-60 cursor-not-allowed"
          )}
        >
          <ThumbsDown className="w-3.5 h-3.5" />
          No
        </button>
        {feedbackError && (
          <button
            type="button"
            onClick={() => onRetrySourceFeedback(result, index)}
            className="text-primary underline hover:opacity-80"
          >
            Retry feedback
          </button>
        )}
      </div>
    </div>
  )
}
