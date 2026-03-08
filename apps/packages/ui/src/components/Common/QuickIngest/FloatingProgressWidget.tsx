import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useTranslation } from "react-i18next"
import { Loader2, Check, ExternalLink } from "lucide-react"
import { useIngestWizard } from "./IngestWizardContext"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Seconds to show the "Done!" state before auto-dismissing. */
const AUTO_DISMISS_DELAY_MS = 10_000

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const FloatingProgressWidget: React.FC = () => {
  const { t } = useTranslation(["option"])
  const { state, restore } = useIngestWizard()
  const { processingState, isMinimized } = state
  const [dismissed, setDismissed] = useState(false)
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const qi = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      options
        ? t(`quickIngest.${key}`, { defaultValue, ...options })
        : t(`quickIngest.${key}`, defaultValue),
    [t]
  )

  // Compute counts and overall progress
  const { completedCount, totalCount, overallPercent } = useMemo(() => {
    const items = processingState.perItemProgress
    if (items.length === 0) return { completedCount: 0, totalCount: 0, overallPercent: 0 }

    let completed = 0
    let percentSum = 0
    for (const p of items) {
      if (p.status === "complete" || p.status === "failed" || p.status === "cancelled") {
        completed++
      }
      percentSum += p.progressPercent
    }

    return {
      completedCount: completed,
      totalCount: items.length,
      overallPercent: Math.round(percentSum / items.length),
    }
  }, [processingState.perItemProgress])

  const allDone = processingState.status === "complete" ||
    processingState.status === "cancelled" ||
    processingState.status === "error" ||
    (completedCount === totalCount && totalCount > 0)

  // Auto-dismiss after completion
  useEffect(() => {
    if (!isMinimized) {
      // Reset dismissed state when not minimized
      setDismissed(false)
      return
    }

    if (allDone && isMinimized && !dismissed) {
      dismissTimerRef.current = setTimeout(() => {
        setDismissed(true)
      }, AUTO_DISMISS_DELAY_MS)
    }

    return () => {
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current)
        dismissTimerRef.current = null
      }
    }
  }, [allDone, isMinimized, dismissed])

  const handleOpen = useCallback(() => {
    setDismissed(false)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
    restore()
  }, [restore])

  // Only render when minimized and not dismissed
  if (!isMinimized || dismissed) return null

  const estimatedText =
    processingState.estimatedRemaining > 0
      ? processingState.estimatedRemaining < 60
        ? `~${Math.ceil(processingState.estimatedRemaining)}s`
        : `~${Math.ceil(processingState.estimatedRemaining / 60)} min`
      : ""

  const widget = (
    <div
      className="fixed bottom-4 right-4 z-[9000] w-72 rounded-lg border border-border bg-surface shadow-lg"
      role="status"
      aria-live="polite"
      aria-label={qi("widget.ariaLabel", "Ingest progress")}
    >
      <div className="flex flex-col gap-2 p-3">
        {/* Header line */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-text">
            {allDone ? (
              <>
                <Check className="h-4 w-4 text-primary" strokeWidth={2.5} aria-hidden="true" />
                <span>{qi("widget.done", "Done!")}</span>
              </>
            ) : (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
                <span>
                  {qi("widget.ingesting", "Ingesting {{done}}/{{total}}", {
                    done: completedCount,
                    total: totalCount,
                  })}
                </span>
                {estimatedText && (
                  <span className="text-xs text-text-muted">{estimatedText}</span>
                )}
              </>
            )}
          </div>
        </div>

        {/* Progress bar + percentage + Open button */}
        <div className="flex items-center gap-2">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface2">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                allDone ? "bg-primary" : "bg-primary"
              }`}
              style={{ width: `${overallPercent}%` }}
            />
          </div>
          <span className="w-8 text-right text-xs tabular-nums text-text-muted">
            {overallPercent}%
          </span>
          <button
            type="button"
            onClick={handleOpen}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-primary transition hover:bg-surface2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus"
            aria-label={qi("widget.open", "Open ingest wizard")}
          >
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
            {qi("widget.openLabel", "Open")}
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(widget, document.body)
}

export default FloatingProgressWidget
