import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useConnectionUxState } from "@/hooks/useConnectionState"

type ConnectFeatureBannerProps = {
  title: React.ReactNode
  description?: React.ReactNode
  examples?: React.ReactNode[]
  showDiagnostics?: boolean
  className?: string
}

const ConnectFeatureBanner: React.FC<ConnectFeatureBannerProps> = ({
  title,
  description,
  examples,
  showDiagnostics = true,
  className
}) => {
  const { t } = useTranslation("settings")
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const { uxState } = useConnectionUxState()

  const primaryLabel = t("tldw.setupLink", "Set up server")
  const diagnosticsLabel = t(
    "healthSummary.diagnostics",
    "Health & diagnostics"
  )

  if (!isOnline) {
    if (uxState === "testing") {
      return null
    }

    if (uxState === "error_auth" || uxState === "configuring_auth") {
      return (
        <FeatureEmptyState
          title={t("tldw.connectBannerAuthTitle", "Add your credentials to continue")}
          description={t(
            "tldw.connectBannerAuthDescription",
            "Your server is reachable, but this feature needs valid credentials before it can load."
          )}
          primaryActionLabel={t("tldw.openSettings", "Open Settings")}
          onPrimaryAction={() => navigate("/settings/tldw")}
          className={className}
        />
      )
    }

    if (uxState === "unconfigured" || uxState === "configuring_url") {
      return (
        <FeatureEmptyState
          title={t("tldw.connectBannerSetupTitle", "Finish setup to continue")}
          description={t(
            "tldw.connectBannerSetupDescription",
            "Complete the tldw server setup flow, then return here to keep working."
          )}
          primaryActionLabel={t("tldw.finishSetup", "Finish Setup")}
          onPrimaryAction={() => navigate("/")}
          className={className}
        />
      )
    }

    if (uxState === "error_unreachable") {
      return (
        <FeatureEmptyState
          title={t("tldw.connectBannerUnreachableTitle", "Can't reach your tldw server right now")}
          description={t(
            "tldw.connectBannerUnreachableDescription",
            "Your server settings are saved, but the tldw server is not responding right now."
          )}
          primaryActionLabel={diagnosticsLabel}
          onPrimaryAction={() => navigate("/settings/health")}
          secondaryActionLabel={t("tldw.openSettings", "Open Settings")}
          onSecondaryAction={() => navigate("/settings/tldw")}
          className={className}
        />
      )
    }
  }

  return (
    <FeatureEmptyState
      title={title}
      description={description}
      examples={examples}
      primaryActionLabel={primaryLabel}
      onPrimaryAction={() => navigate("/settings/tldw")}
      secondaryActionLabel={showDiagnostics ? diagnosticsLabel : undefined}
      onSecondaryAction={
        showDiagnostics ? () => navigate("/settings/health") : undefined
      }
      className={className}
    />
  )
}

export default ConnectFeatureBanner
