import React from "react"

type ScopesPanelProps = {
  selectedPersonaName: string
}

export const ScopesPanel: React.FC<ScopesPanelProps> = ({
  selectedPersonaName
}) => {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        Scoped Access
      </div>
      <div className="mt-2 space-y-2 text-sm text-text">
        <div className="font-medium">
          {selectedPersonaName || "Selected persona"}
        </div>
        <p className="text-xs text-text-muted">
          Scope-aware behavior is still enforced through the current persona session workflow. Dedicated scope editing will attach here without moving the route-owned session logic.
        </p>
      </div>
    </div>
  )
}
