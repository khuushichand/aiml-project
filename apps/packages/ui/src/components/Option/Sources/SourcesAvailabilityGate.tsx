import React from "react"
import { useTranslation } from "react-i18next"

import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { PageShell } from "@/components/Common/PageShell"
import WorkspaceConnectionGate from "@/components/Common/WorkspaceConnectionGate"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import type { ServerCapabilities } from "@/services/tldw/server-capabilities"

type SourcesAvailabilityGateProps = {
  children: React.ReactNode
  capabilityState?: {
    capabilities: ServerCapabilities | null
    loading: boolean
  }
  maxWidthClassName?: string
}

export const SourcesAvailabilityGate: React.FC<SourcesAvailabilityGateProps> = ({
  children,
  capabilityState,
  maxWidthClassName = "max-w-6xl"
}) => {
  const { t } = useTranslation(["sources"])
  const defaultCapabilityState = useServerCapabilities()
  const { capabilities, loading } = capabilityState ?? defaultCapabilityState

  return (
    <WorkspaceConnectionGate
      featureName={t("sources:title", "Sources")}
      setupDescription={t(
        "sources:setupRequired",
        "Sources depends on your connected tldw server to manage folders, archive snapshots, and sync rules."
      )}
      maxWidthClassName={maxWidthClassName}
    >
      {!loading && capabilities && !capabilities.hasIngestionSources ? (
        <PageShell className="py-6" maxWidthClassName={maxWidthClassName}>
          <FeatureEmptyState
            title={t("sources:title", "Sources")}
            description={t(
              "sources:states.unsupported",
              "This server does not advertise ingestion source support."
            )}
          />
        </PageShell>
      ) : (
        <>{children}</>
      )}
    </WorkspaceConnectionGate>
  )
}
