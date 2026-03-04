import React from "react"
import { useTranslation } from "react-i18next"
import type { ConnectionUxState } from "@/types/connection"

export interface ConnectionStatusIndicatorProps {
  isConnectionReady: boolean
  uxState: ConnectionUxState
  onOpenSettings: () => void
}

const ConnectionStatusIndicatorBase: React.FC<
  ConnectionStatusIndicatorProps
> = ({ isConnectionReady, uxState, onOpenSettings }) => {
  const { t } = useTranslation(["sidepanel"])

  if (isConnectionReady) {
    return null
  }

  const isConnecting = uxState === "testing"
  const textColorClass = isConnecting
    ? "text-warn"
    : "text-danger"
  const dotPingClass = isConnecting ? "bg-warn" : "bg-danger"
  const dotSolidClass = isConnecting ? "bg-warn" : "bg-danger"

  return (
    <div className={`flex items-center gap-2 px-2 py-2 text-xs ${textColorClass}`}>
      {/* Pulsing dot indicator */}
      <span className="relative flex h-2 w-2">
        <span
          className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${dotPingClass}`}
        />
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${dotSolidClass}`}
        />
      </span>

      {/* Status text */}
      <span>
        {isConnecting
          ? t("sidepanel:composer.connectingStatus", "Connecting to server...")
          : t("sidepanel:composer.disconnectedStatus", "Not connected")}
      </span>

      {/* Settings link when disconnected */}
      {!isConnecting && (
        <button
          type="button"
          onClick={onOpenSettings}
          className="ml-auto text-[11px] font-medium text-danger underline hover:text-danger"
          title={t("sidepanel:composer.openSettings", "Open Settings")}
        >
          {t("sidepanel:composer.openSettings", "Open Settings")}
        </button>
      )}
    </div>
  )
}

export const ConnectionStatusIndicator = React.memo(ConnectionStatusIndicatorBase)
ConnectionStatusIndicator.displayName = "ConnectionStatusIndicator"

export default ConnectionStatusIndicator
