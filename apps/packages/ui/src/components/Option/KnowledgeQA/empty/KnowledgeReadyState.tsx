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

      <div className="mx-auto max-w-2xl rounded-lg border border-border bg-muted/20 px-4 py-3 text-left">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          How it works
        </p>
        <ol className="mt-2 grid gap-1 text-sm text-text-muted sm:grid-cols-3 sm:gap-3">
          <li>
            <span className="font-medium text-text">1.</span> Select sources
          </li>
          <li>
            <span className="font-medium text-text">2.</span> Ask a question
          </li>
          <li>
            <span className="font-medium text-text">3.</span> Review cited answer
          </li>
        </ol>
      </div>

      <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-center gap-2">
        {suggestedPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPromptClick(prompt)}
            className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-text transition-colors hover:border-primary hover:bg-surface2"
          >
            {prompt}
          </button>
        ))}
      </div>

      {!hasSources ? (
        <div className="mx-auto max-w-2xl rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-left text-sm text-warn">
          <p>
            No sources are selected. Start by choosing source categories, or use web
            fallback for web-first searches.
          </p>
          <button
            type="button"
            onClick={onSelectSources}
            className="mt-2 inline-flex items-center rounded-md border border-warn/40 px-2.5 py-1 text-xs font-medium hover:bg-warn/20 transition-colors"
          >
            Open source settings
          </button>
        </div>
      ) : null}

      <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={onContinueRecent}
          disabled={!hasRecentSession}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm transition-colors",
            hasRecentSession
              ? "border-border bg-surface text-text-subtle hover:bg-hover hover:text-text"
              : "border-border bg-surface text-text-subtle cursor-not-allowed opacity-70"
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
              ? "border-border bg-surface text-text-subtle hover:bg-hover hover:text-text"
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
