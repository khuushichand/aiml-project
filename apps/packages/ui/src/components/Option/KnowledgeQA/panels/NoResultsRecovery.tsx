import React from "react"
import { SearchX } from "lucide-react"

type NoResultsRecoveryProps = {
  onBroadenScope: () => void
  onEnableWeb: () => void
  onShowNearestMatches: () => void
  webEnabled: boolean
}

export function NoResultsRecovery({
  onBroadenScope,
  onEnableWeb,
  onShowNearestMatches,
  webEnabled,
}: NoResultsRecoveryProps) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-6">
      <div className="flex items-start gap-3">
        <SearchX className="mt-0.5 h-5 w-5 text-text-muted" />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">No results found</h2>
          <p className="mt-1 text-sm text-text-muted">
            Try broader sources or enable web search for recovery.
          </p>
          <ul className="mt-2 space-y-1 text-sm text-text-muted">
            <li>Try different keywords or fewer constraints.</li>
            <li>Broaden the question before adding details.</li>
            <li>Confirm your sources were ingested and indexed.</li>
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onBroadenScope}
              className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm hover:bg-muted transition-colors"
            >
              Broaden source scope
            </button>
            <button
              type="button"
              onClick={onEnableWeb}
              disabled={webEnabled}
              className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm disabled:opacity-60 disabled:cursor-not-allowed hover:bg-muted transition-colors"
            >
              {webEnabled ? "Web search enabled" : "Enable web search"}
            </button>
            <button
              type="button"
              onClick={onShowNearestMatches}
              className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm hover:bg-muted transition-colors"
            >
              Show nearest matches
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
