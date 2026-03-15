import React from "react"

import type { PersonaConfirmationMode } from "@/hooks/useResolvedPersonaVoiceDefaults"
import type { PersonaGardenTabKey } from "@/utils/persona-garden-route"

export type SetupReviewSummary = {
  starterCommands:
    | { mode: "added"; count: number }
    | { mode: "configured"; count: number }
    | { mode: "skipped" }
  confirmationMode: PersonaConfirmationMode | null
  connection:
    | { mode: "created"; name: string }
    | { mode: "available"; name: string }
    | { mode: "skipped" }
}

export type SetupHandoffRecommendedAction =
  | "add_command"
  | "add_connection"
  | "try_live"
  | "review_commands"

type PersonaSetupHandoffCardProps = {
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
  recommendedAction: SetupHandoffRecommendedAction
  compact?: boolean
  onDismiss: () => void
  onAddCommand: () => void
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
  if (summary.mode === "configured") {
    return `${summary.count} command${summary.count === 1 ? "" : "s"} available`
  }
  return "Skipped starter commands"
}

function formatConnectionSummary(summary: SetupReviewSummary["connection"]): string {
  if (summary.mode === "created") {
    return `Connection added: ${summary.name}`
  }
  if (summary.mode === "available") {
    return `Connection available: ${summary.name}`
  }
  return "No external connection yet"
}

function getRecommendedActionTitle(action: SetupHandoffRecommendedAction): string {
  if (action === "add_command") return "Add your first command"
  if (action === "add_connection") return "Add a connection"
  if (action === "try_live") return "Try your first live turn"
  return "Review starter commands"
}

function getRecommendedActionDescription(action: SetupHandoffRecommendedAction): string {
  if (action === "add_command") {
    return "Give your assistant one command it can reliably handle after setup."
  }
  if (action === "add_connection") {
    return "Link one external tool so your assistant can take action beyond local prompts."
  }
  if (action === "try_live") {
    return "Dry run worked. Confirm the same flow through a real live voice turn next."
  }
  return "Your assistant is already responding live. Tighten the starter pack before you branch out."
}

function getRecommendedActionButtonLabel(action: SetupHandoffRecommendedAction): string {
  if (action === "add_command") return "Open Commands"
  if (action === "add_connection") return "Open Connections"
  if (action === "try_live") return "Open Live Session"
  return "Review Commands"
}

export const PersonaSetupHandoffCard: React.FC<PersonaSetupHandoffCardProps> = ({
  completionType,
  reviewSummary,
  recommendedAction,
  compact = false,
  onDismiss,
  onAddCommand,
  onOpenCommands,
  onOpenTestLab,
  onOpenLive,
  onOpenProfiles,
  onOpenConnections
}) => {
  const primaryAction =
    recommendedAction === "add_command"
      ? {
          label: getRecommendedActionButtonLabel(recommendedAction),
          onClick: onAddCommand
        }
      : recommendedAction === "review_commands"
        ? {
            label: getRecommendedActionButtonLabel(recommendedAction),
            onClick: onOpenCommands
          }
        : recommendedAction === "add_connection"
        ? {
            label: getRecommendedActionButtonLabel(recommendedAction),
            onClick: onOpenConnections
          }
        : {
            label: getRecommendedActionButtonLabel(recommendedAction),
            onClick: onOpenLive
          }

  if (compact) {
    return (
      <div
        data-testid="persona-setup-handoff-card"
        className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-3 text-sm text-sky-100"
      >
        <div className="font-medium">Setup complete</div>
        <div className="mt-1 text-xs text-sky-100/80">{getCompletionCopy(completionType)}</div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="text-sm text-sky-100">{getRecommendedActionTitle(recommendedAction)}</div>
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
            onClick={onDismiss}
          >
            Dismiss
          </button>
        </div>
      </div>
    )
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
          Recommended next step
        </div>
        <div className="mt-2 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-sky-100">
              {getRecommendedActionTitle(recommendedAction)}
            </div>
            <div className="text-xs text-sky-100/80">
              {getRecommendedActionDescription(recommendedAction)}
            </div>
          </div>
          <button
            type="button"
            className="rounded-md border border-sky-500/40 px-2 py-1 text-xs font-medium text-sky-100"
            onClick={primaryAction.onClick}
          >
            {primaryAction.label}
          </button>
        </div>
      </div>
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
