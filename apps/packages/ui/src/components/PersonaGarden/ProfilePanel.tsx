import React from "react"

type ProfilePanelProps = {
  selectedPersonaId: string
  selectedPersonaName: string
  personaCount: number
  connected: boolean
  sessionId: string | null
}

export const ProfilePanel: React.FC<ProfilePanelProps> = ({
  selectedPersonaId,
  selectedPersonaName,
  personaCount,
  connected,
  sessionId
}) => {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        Persona Profile
      </div>
      <div className="mt-2 space-y-2 text-sm text-text">
        <div>
          <div className="font-medium">{selectedPersonaName || selectedPersonaId || "No persona selected"}</div>
          <div className="text-xs text-text-muted">{selectedPersonaId || "No persona id"}</div>
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-text-muted">
          <span>{`Catalog personas: ${personaCount}`}</span>
          <span>{connected ? "Session connected" : "Session disconnected"}</span>
          {sessionId ? <span>{`Active session: ${sessionId.slice(0, 8)}`}</span> : null}
        </div>
        <p className="text-xs text-text-muted">
          Profile management remains additive in this pass. Live selection and session controls stay on the Live Session tab.
        </p>
      </div>
    </div>
  )
}
