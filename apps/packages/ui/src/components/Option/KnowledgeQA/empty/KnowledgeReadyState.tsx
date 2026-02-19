import React from "react"
import { BookOpen, Clock3, SlidersHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

type KnowledgeReadyStateProps = {
  suggestedPrompts: string[]
  onPromptClick: (prompt: string) => void
  onContinueRecent: () => void
  onSelectSources: () => void
  hasSources: boolean
  hasRecentSession: boolean
  className?: string
}

export function KnowledgeReadyState({
  suggestedPrompts,
  onPromptClick,
  onContinueRecent,
  onSelectSources,
  hasSources,
  hasRecentSession,
  className,
}: KnowledgeReadyStateProps) {
  return (
    <div className={cn("space-y-5 text-center", className)}>
      <div className="mx-auto max-w-2xl">
        <BookOpen className="mx-auto mb-3 h-12 w-12 text-primary" />
        <h1 className="text-3xl font-bold">Knowledge QA</h1>
        <p className="mt-1 text-base font-medium">Ask your knowledge base</p>
        <p className="mt-2 text-sm text-text-muted">
          Get grounded answers with citations from your selected sources.
        </p>
      </div>

      <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-center gap-2">
        {suggestedPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPromptClick(prompt)}
            className="rounded-full border border-border bg-muted px-3 py-1.5 text-xs text-text hover:bg-surface2 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={onContinueRecent}
          disabled={!hasRecentSession}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm transition-colors",
            hasRecentSession
              ? "border-border bg-surface hover:bg-muted"
              : "border-border/60 bg-surface text-text-subtle cursor-not-allowed"
          )}
        >
          <Clock3 className="h-4 w-4" />
          Continue recent session
        </button>
        <button
          type="button"
          onClick={onSelectSources}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm transition-colors",
            hasSources
              ? "border-border bg-surface hover:bg-muted"
              : "border-warn/40 bg-warn/10 text-warn hover:bg-warn/20"
          )}
        >
          <SlidersHorizontal className="h-4 w-4" />
          {hasSources ? "Select sources" : "No sources selected"}
        </button>
      </div>
    </div>
  )
}
