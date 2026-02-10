/**
 * PollingIndicator component
 * Shows when data is being auto-refreshed
 */

import React from "react"
import { useTranslation } from "react-i18next"

interface PollingIndicatorProps {
  isPolling: boolean
  className?: string
}

export const PollingIndicator: React.FC<PollingIndicatorProps> = ({
  isPolling,
  className = ""
}) => {
  const { t } = useTranslation(["evaluations", "common"])

  if (!isPolling) return null

  return (
    <span className={`flex items-center gap-1.5 text-primary text-xs ${className}`}>
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
      </span>
      {t("evaluations:pollingIndicator", {
        defaultValue: "Auto-refreshing"
      })}
    </span>
  )
}

export default PollingIndicator
