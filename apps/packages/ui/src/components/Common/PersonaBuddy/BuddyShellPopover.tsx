import React from "react"

import type { PersonaBuddySummary } from "@/types/persona-buddy"

type BuddyShellPopoverProps = {
  buddySummary: PersonaBuddySummary
}

export const BuddyShellPopover: React.FC<BuddyShellPopoverProps> = ({
  buddySummary
}) => (
  <div
    data-testid="persona-buddy-popover"
    className="min-w-[220px] rounded-2xl border border-border bg-bg/95 p-3 shadow-xl backdrop-blur"
  >
    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">
      Persona Buddy
    </div>
    <div className="mt-2 text-sm font-semibold text-text">
      {buddySummary.persona_name}
    </div>
    {buddySummary.role_summary ? (
      <div className="mt-1 text-xs leading-5 text-text-muted">
        {buddySummary.role_summary}
      </div>
    ) : null}
  </div>
)

export default BuddyShellPopover
