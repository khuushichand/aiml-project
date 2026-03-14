import React from "react"

import type { PersonaConfirmationMode } from "@/hooks/useResolvedPersonaVoiceDefaults"
import type { PersonaGardenTabKey } from "@/utils/persona-garden-route"

export type SetupReviewSummary = {
  starterCommands: { mode: "added"; count: number } | { mode: "skipped" }
  confirmationMode: PersonaConfirmationMode | null
  connection: { mode: "created"; name: string } | { mode: "skipped" }
}

type PersonaSetupHandoffCardProps = {
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
  onDismiss: () => void
  onOpenCommands: () => void
  onOpenTestLab: () => void
  onOpenLive: () => void
  onOpenProfiles: () => void
  onOpenConnections: () => void
}

function getCompletionCopy(completionType: "dry_run" | "live_session"): string {
  return completionType === "live_session"
    ? "Completed with live session"
    : "Completed with dry run"
}

function formatConfirmationMode(mode: PersonaConfirmationMode | null): string {
  if (mode === "always") return "Always ask before actions"
  if (mode === "never") return "Never ask"
  return "Ask for destructive actions"
}

function formatStarterCommandSummary(summary: SetupReviewSummary["starterCommands"]): string {
  if (summary.mode === "added") {
    return `Added ${summary.count} starter command${summary.count === 1 ? "" : "s"}`
  }
  return "Skipped starter commands"
}

function formatConnectionSummary(summary: SetupReviewSummary["connection"]): string {
  if (summary.mode === "created") {
    return `Connection added: ${summary.name}`
  }
  return "No external connection yet"
}

export const PersonaSetupHandoffCard: React.FC<PersonaSetupHandoffCardProps> = ({
  targetTab,
  completionType,
  reviewSummary,
  onDismiss,
  onOpenCommands,
  onOpenTestLab,
  onOpenLive,
  onOpenProfiles,
  onOpenConnections
}) => {
  const primaryAction =
    targetTab === "commands"
      ? {
          label: "Review starter commands",
          onClick: onOpenCommands
        }
      : targetTab === "live"
        ? {
            label: "Start live session",
            onClick: onOpenLive
          }
        : {
            label: "Adjust assistant defaults",
            onClick: onOpenProfiles
          }

  return (
    <div
      data-testid="persona-setup-handoff-card"
      className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-3 text-sm text-sky-100"
    >
      <div className="font-medium">Assistant setup complete</div>
      <div className="mt-1 text-xs text-sky-100/80">{getCompletionCopy(completionType)}</div>
      <div className="mt-3 rounded-md border border-sky-500/30 bg-sky-500/5 px-3 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-sky-100/80">
          Starter pack review
        </div>
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium text-sky-100">Starter commands</div>
              <div className="text-xs text-sky-100/80">
                {formatStarterCommandSummary(reviewSummary.starterCommands)}
              </div>
            </div>
            <button
              type="button"
              className="rounded-md border border-sky-500/40 px-2 py-1 text-xs font-medium text-sky-100"
              onClick={onOpenCommands}
            >
              Review commands
            </button>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium text-sky-100">Approval mode</div>
              <div className="text-xs text-sky-100/80">
                {formatConfirmationMode(reviewSummary.confirmationMode)}
              </div>
            </div>
            <button
              type="button"
              className="rounded-md border border-sky-500/40 px-2 py-1 text-xs font-medium text-sky-100"
              onClick={onOpenProfiles}
            >
              Review safety defaults
            </button>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium text-sky-100">Connection</div>
              <div className="text-xs text-sky-100/80">
                {formatConnectionSummary(reviewSummary.connection)}
              </div>
            </div>
            <button
              type="button"
              className="rounded-md border border-sky-500/40 px-2 py-1 text-xs font-medium text-sky-100"
              onClick={onOpenConnections}
            >
              Open connections
            </button>
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-100"
          onClick={primaryAction.onClick}
        >
          {primaryAction.label}
        </button>
        <button
          type="button"
          className="rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-100"
          onClick={onOpenTestLab}
        >
          Open Test Lab
        </button>
        <button
          type="button"
          className="rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-100"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
