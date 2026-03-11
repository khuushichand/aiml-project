import React from "react"
import { Empty } from "antd"
import { useTranslation } from "react-i18next"

import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { PageShell } from "@/components/Common/PageShell"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"

type SourcesAvailabilityGateProps = {
  children: React.ReactNode
  maxWidthClassName?: string
}

export const SourcesAvailabilityGate: React.FC<SourcesAvailabilityGateProps> = ({
  children,
  maxWidthClassName = "max-w-6xl"
}) => {
  const { t } = useTranslation(["sources"])
  const isOnline = useServerOnline()
  const { capabilities, loading } = useServerCapabilities()

  if (!isOnline) {
    return (
      <PageShell className="py-6" maxWidthClassName={maxWidthClassName}>
        <Empty
          description={t(
            "sources:offline",
            "Server is offline. Connect to manage ingestion sources."
          )}
        />
      </PageShell>
    )
  }

  if (!loading && capabilities && !capabilities.hasIngestionSources) {
    return (
      <PageShell className="py-6" maxWidthClassName={maxWidthClassName}>
        <FeatureEmptyState
          title={t("sources:title", "Sources")}
          description={t(
            "sources:states.unsupported",
            "This server does not advertise ingestion source support."
          )}
        />
      </PageShell>
    )
  }

  return <>{children}</>
}
