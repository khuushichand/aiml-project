import React from "react"

import type { PersonaGardenTabKey } from "@/utils/persona-garden-route"

type PersonaSetupHandoffCardProps = {
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  onDismiss: () => void
  onOpenCommands: () => void
  onOpenTestLab: () => void
  onOpenLive: () => void
  onOpenProfiles: () => void
}

function getCompletionCopy(completionType: "dry_run" | "live_session"): string {
  return completionType === "live_session"
    ? "Completed with live session"
    : "Completed with dry run"
}

export const PersonaSetupHandoffCard: React.FC<PersonaSetupHandoffCardProps> = ({
  targetTab,
  completionType,
  onDismiss,
  onOpenCommands,
  onOpenTestLab,
  onOpenLive,
  onOpenProfiles
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
