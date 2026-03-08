import React from "react"
import { useTranslation } from "react-i18next"

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
  const { t } = useTranslation(["sidepanel", "common"])

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.profile.heading", {
          defaultValue: "Persona Profile"
        })}
      </div>
      <div className="mt-2 space-y-2 text-sm text-text">
        <div>
          <div className="font-medium">
            {selectedPersonaName ||
              selectedPersonaId ||
              t("sidepanel:personaGarden.profile.noneSelected", {
                defaultValue: "No persona selected"
              })}
          </div>
          <div className="text-xs text-text-muted">
            {selectedPersonaId ||
              t("sidepanel:personaGarden.profile.noneId", {
                defaultValue: "No persona id"
              })}
          </div>
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-text-muted">
          <span>
            {t("sidepanel:personaGarden.profile.catalogCount", {
              defaultValue: "Catalog personas: {{count}}",
              count: personaCount
            })}
          </span>
          <span>
            {connected
              ? t("sidepanel:personaGarden.profile.sessionConnected", {
                  defaultValue: "Session connected"
                })
              : t("sidepanel:personaGarden.profile.sessionDisconnected", {
                  defaultValue: "Session disconnected"
                })}
          </span>
          {sessionId ? (
            <span>
              {t("sidepanel:personaGarden.profile.activeSession", {
                defaultValue: "Active session: {{sessionId}}",
                sessionId: sessionId.slice(0, 8)
              })}
            </span>
          ) : null}
        </div>
        <p className="text-xs text-text-muted">
          {t("sidepanel:personaGarden.profile.description", {
            defaultValue:
              "Profile management remains additive in this pass. Live selection and session controls stay on the Live Session tab."
          })}
        </p>
      </div>
    </div>
  )
}
