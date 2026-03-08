import React from "react"

type PoliciesPanelProps = {
  hasPendingPlan: boolean
}

export const PoliciesPanel: React.FC<PoliciesPanelProps> = ({
  hasPendingPlan
}) => {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        Tool Policies
      </div>
      <div className="mt-2 space-y-2 text-sm text-text">
        <p className="text-xs text-text-muted">
          Policy enforcement remains active through pending tool plans and live-session confirmations. This tab reserves the dedicated policy surface without changing the current approval contract.
        </p>
        <div className="text-xs text-text-muted">
          {hasPendingPlan ? "A pending tool plan is available on the Live Session tab." : "No pending tool plan right now."}
        </div>
      </div>
    </div>
  )
}
