import React from "react"

import type { PersonaSetupState } from "@/hooks/usePersonaSetupWizard"

import type { PersonaSetupProgressItem } from "./personaSetupProgress"

type PersonaSetupStatusCardProps = {
  setup: PersonaSetupState | null
  progressItems: PersonaSetupProgressItem[]
  onStartSetup?: () => void
  onResumeSetup?: () => void
  onResetSetup?: () => void
  onRerunSetup?: () => void
}

function getCompletionLabel(lastTestType: PersonaSetupState["last_test_type"]): string {
  if (lastTestType === "dry_run") {
    return "Completed with dry run"
  }
  if (lastTestType === "live_session") {
    return "Completed with live session"
  }
  return "Setup completed"
}

export const PersonaSetupStatusCard: React.FC<PersonaSetupStatusCardProps> = ({
  setup,
  progressItems,
  onStartSetup,
  onResumeSetup,
  onResetSetup,
  onRerunSetup
}) => {
  const status = setup?.status ?? "not_started"
  const currentItem = progressItems.find((item) => item.status === "current") || null

  return (
    <div
      data-testid="persona-setup-status-card"
      className="rounded-lg border border-border bg-surface p-3"
    >
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        Assistant setup
      </div>
      {status === "completed" ? (
        <div className="mt-2 space-y-3">
          <div>
            <div className="text-sm font-medium text-text">Completed</div>
            <div className="text-xs text-text-muted">
              {getCompletionLabel(setup?.last_test_type ?? null)}
            </div>
          </div>
          {onRerunSetup ? (
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text"
              onClick={onRerunSetup}
            >
              Rerun setup
            </button>
          ) : null}
        </div>
      ) : status === "in_progress" ? (
        <div className="mt-2 space-y-3">
          <div>
            <div className="text-sm font-medium text-text">In progress</div>
            <div className="text-xs text-text-muted">
              Current step: {currentItem?.label || "Continue setup"}
            </div>
            {currentItem?.summary ? (
              <div className="mt-1 text-xs text-text-muted">{currentItem.summary}</div>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {onResumeSetup ? (
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text"
                onClick={onResumeSetup}
              >
                Resume setup
              </button>
            ) : null}
            {onResetSetup ? (
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text"
                onClick={onResetSetup}
              >
                Reset setup
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="mt-2 space-y-3">
          <div>
            <div className="text-sm font-medium text-text">Not started</div>
            <div className="text-xs text-text-muted">
              Start the guided assistant setup for this persona.
            </div>
          </div>
          {onStartSetup ? (
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text"
              onClick={onStartSetup}
            >
              Start setup
            </button>
          ) : null}
        </div>
      )}
    </div>
  )
}
