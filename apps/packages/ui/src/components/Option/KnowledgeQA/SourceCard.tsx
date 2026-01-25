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
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { RagResult } from "./types"

type SourceCardProps = {
  result: RagResult
  index: number // 1-based for display
  isCited: boolean
  isFocused: boolean
  onAskAbout: (result: RagResult) => void
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

export function SourceCard({
  result,
  index,
  isCited,
  isFocused,
  onAskAbout,
  className,
}: SourceCardProps) {
  const [copied, setCopied] = React.useState(false)

  const title = result.metadata?.title || result.metadata?.source || `Source ${index}`
  const content = result.content || result.text || result.chunk || ""
  const excerpt = truncateText(content, 300)
  const url = result.metadata?.url
  const score = result.score
  const sourceType = result.metadata?.source_type || "media_db"
  const pageNumber = result.metadata?.page_number

  const Icon = getSourceIcon(sourceType)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error("Failed to copy:", error)
    }
  }, [content])

  const handleOpenExternal = useCallback(() => {
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer")
    }
  }, [url])

  return (
    <div
      id={`source-card-${index - 1}`}
      className={cn(
        "group rounded-lg border transition-all duration-200",
        isFocused
          ? "border-primary bg-primary/5 ring-2 ring-primary/20"
          : "border-border bg-surface hover:border-primary/30",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4 pb-2">
        {/* Index badge */}
        <div
          className={cn(
            "flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center text-sm font-medium",
            isCited
              ? "bg-primary text-white"
              : "bg-muted text-text-muted"
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
              <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
                {score !== undefined && (
                  <span className="px-1.5 py-0.5 bg-muted rounded">
                    {Math.round(score * 100)}% match
                  </span>
                )}
                {pageNumber && (
                  <span>Page {pageNumber}</span>
                )}
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
      <div className="px-4 pb-3">
        <p className="text-sm text-text-muted leading-relaxed">
          {excerpt}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-border/50 bg-muted/20">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onAskAbout(result)}
            title="Create a question about this source"
            aria-label={`Ask about ${title}`}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-primary text-white hover:bg-primaryStrong transition-colors"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Ask About This
          </button>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md bg-muted text-text-muted hover:text-text hover:bg-surface2 transition-colors"
            title="Copy content"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy
              </>
            )}
          </button>
        </div>

        {url && (
          <button
            onClick={handleOpenExternal}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md text-text-muted hover:text-text transition-colors"
            title="Open original"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Open
          </button>
        )}
      </div>
    </div>
  )
}
