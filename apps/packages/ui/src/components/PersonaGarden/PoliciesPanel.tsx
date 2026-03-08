import React from "react"
import { useTranslation } from "react-i18next"

type PoliciesPanelProps = {
  hasPendingPlan: boolean
}

export const PoliciesPanel: React.FC<PoliciesPanelProps> = ({
  hasPendingPlan
}) => {
  const { t } = useTranslation(["sidepanel", "common"])

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.policies.heading", {
          defaultValue: "Tool Policies"
        })}
      </div>
      <div className="mt-2 space-y-2 text-sm text-text">
        <p className="text-xs text-text-muted">
          {t("sidepanel:personaGarden.policies.description", {
            defaultValue:
              "Policy enforcement remains active through pending tool plans and live-session confirmations. This tab reserves the dedicated policy surface without changing the current approval contract."
          })}
        </p>
        <div className="text-xs text-text-muted">
          {hasPendingPlan
            ? t("sidepanel:personaGarden.policies.pendingPlan", {
                defaultValue: "A pending tool plan is available on the Live Session tab."
              })
            : t("sidepanel:personaGarden.policies.noPendingPlan", {
                defaultValue: "No pending tool plan right now."
              })}
        </div>
      </div>
    </div>
  )
}
