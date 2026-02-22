import React from "react"

export interface StatusBadgeProps {
  variant: "demo" | "warning" | "error"
  children: React.ReactNode
}

const VARIANT_CLASSES: Record<StatusBadgeProps["variant"], string> = {
  demo:
    "bg-primary/10 text-primary",
  warning:
    "bg-warn/10 text-warn",
  error:
    "bg-danger/10 text-danger"
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  variant,
  children
}) => {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${VARIANT_CLASSES[variant]}`}
    >
      {children}
    </span>
  )
}

export default StatusBadge
