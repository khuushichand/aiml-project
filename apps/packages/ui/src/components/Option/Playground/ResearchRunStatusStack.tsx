import React from "react"

import type { ChatLinkedResearchRun } from "@/services/tldw/TldwApiClient"

import {
  CHAT_LINKED_RESEARCH_VISIBLE_TERMINAL_ROWS,
  buildChatLinkedResearchPath,
  getChatLinkedResearchStatusLabel,
  isTerminalResearchRun,
  orderChatLinkedResearchRuns
} from "./research-run-status"

type ResearchRunStatusStackProps = {
  runs: ChatLinkedResearchRun[]
}

const STATUS_BADGE_CLASSNAME: Record<string, string> = {
  Running: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  "Needs review": "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  Completed: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Failed: "bg-red-500/10 text-red-700 dark:text-red-300",
  Cancelled: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300",
  Paused: "bg-violet-500/10 text-violet-700 dark:text-violet-300"
}

export const ResearchRunStatusStack: React.FC<ResearchRunStatusStackProps> = ({
  runs
}) => {
  const [showAllTerminal, setShowAllTerminal] = React.useState(false)
  const orderedRuns = React.useMemo(() => orderChatLinkedResearchRuns(runs), [runs])
  const activeRuns = orderedRuns.filter((run) => !isTerminalResearchRun(run))
  const terminalRuns = orderedRuns.filter((run) => isTerminalResearchRun(run))
  const visibleTerminalRuns = showAllTerminal
    ? terminalRuns
    : terminalRuns.slice(0, CHAT_LINKED_RESEARCH_VISIBLE_TERMINAL_ROWS)
  const hiddenTerminalCount = Math.max(0, terminalRuns.length - visibleTerminalRuns.length)
  const visibleRuns = [...activeRuns, ...visibleTerminalRuns]

  React.useEffect(() => {
    setShowAllTerminal(false)
  }, [runs])

  if (runs.length === 0) {
    return null
  }

  return (
    <section
      aria-label="Linked deep research runs"
      data-testid="research-run-status-stack"
      className="mb-4 mt-4 w-full max-w-5xl px-4"
    >
      <div className="rounded-2xl border border-border/70 bg-surface/80 p-3 shadow-sm backdrop-blur-sm">
        <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-text-subtle">
          Research runs
        </div>
        <div className="space-y-2">
          {visibleRuns.map((run) => {
            const statusLabel = getChatLinkedResearchStatusLabel(run)
            return (
              <div
                key={run.run_id}
                data-testid="research-run-status-row"
                className="flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-background/70 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-text">{run.query}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-text-subtle">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 font-medium ${STATUS_BADGE_CLASSNAME[statusLabel] ?? "bg-muted text-text-subtle"}`}
                    >
                      {statusLabel}
                    </span>
                    <span className="truncate">{run.run_id}</span>
                  </div>
                </div>
                <a
                  href={buildChatLinkedResearchPath(run.run_id)}
                  className="shrink-0 text-sm font-medium text-primary hover:underline"
                >
                  Open in Research
                </a>
              </div>
            )
          })}
        </div>
        {hiddenTerminalCount > 0 && (
          <button
            type="button"
            className="mt-3 text-sm font-medium text-text-subtle hover:text-text"
            onClick={() => setShowAllTerminal((current) => !current)}
          >
            {showAllTerminal ? "Show fewer" : `Show ${hiddenTerminalCount} more`}
          </button>
        )}
      </div>
    </section>
  )
}
