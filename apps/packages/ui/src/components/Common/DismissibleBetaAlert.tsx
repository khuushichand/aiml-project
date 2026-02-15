import React from "react"
import { Alert } from "antd"
import type { AlertProps } from "antd"

type DismissibleBetaAlertProps = {
  /** Unique key for localStorage persistence, e.g. "beta-dismissed:evaluations" */
  storageKey: string
  message: React.ReactNode
  description?: React.ReactNode
  className?: string
} & Pick<AlertProps, "type" | "showIcon" | "icon">

/**
 * A beta-notice Alert that can be permanently dismissed.
 * Dismissal state is stored in localStorage under the given storageKey.
 */
export const DismissibleBetaAlert: React.FC<DismissibleBetaAlertProps> = ({
  storageKey,
  message,
  description,
  className,
  type = "info",
  showIcon = true,
  icon
}) => {
  const [dismissed, setDismissed] = React.useState(() => {
    try {
      return localStorage.getItem(storageKey) === "1"
    } catch {
      return false
    }
  })

  if (dismissed) return null

  return (
    <Alert
      type={type}
      showIcon={showIcon}
      icon={icon}
      message={message}
      description={description}
      closable
      onClose={() => {
        setDismissed(true)
        try {
          localStorage.setItem(storageKey, "1")
        } catch {
          // localStorage may be unavailable
        }
      }}
      className={className}
    />
  )
}
