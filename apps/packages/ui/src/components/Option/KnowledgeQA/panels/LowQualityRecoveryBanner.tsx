import React from "react"
import { Lightbulb, X, Globe, Search, Layers } from "lucide-react"

type LowQualityRecoveryBannerProps = {
  onRefine: () => void
  onEnableWeb: () => void
  onSelectSources: () => void
  onDismiss: () => void
  title?: string
  description?: string
  refineLabel?: string
  enableWebLabel?: string
  selectSourcesLabel?: string
}

export function LowQualityRecoveryBanner({
  onRefine,
  onEnableWeb,
  onSelectSources,
  onDismiss,
  title = "These sources may not closely match your question.",
  description = "Try refining your search:",
  refineLabel = "Use more specific terms",
  enableWebLabel = "Include web sources",
  selectSourcesLabel = "Select different sources",
}: LowQualityRecoveryBannerProps) {
  return (
    <div
      className="rounded-lg border border-warn/20 bg-warn/5 p-4"
      role="status"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-text">{title}</p>
            <p className="text-[13px] leading-5 text-text-muted">{description}</p>
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                onClick={onRefine}
                className="inline-flex items-center gap-1 rounded-md border border-primary/40 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/15 transition-colors"
                aria-label={refineLabel}
              >
                <Search className="h-3 w-3" />
                {refineLabel}
              </button>
              <button
                type="button"
                onClick={onEnableWeb}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
                aria-label={enableWebLabel}
              >
                <Globe className="h-3 w-3" />
                {enableWebLabel}
              </button>
              <button
                type="button"
                onClick={onSelectSources}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-subtle hover:bg-hover hover:text-text transition-colors"
                aria-label={selectSourcesLabel}
              >
                <Layers className="h-3 w-3" />
                {selectSourcesLabel}
              </button>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md p-1 text-text-muted hover:bg-hover hover:text-text transition-colors"
          aria-label="Dismiss recovery suggestions"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
