import React from "react"
import { Tag } from "antd"
import { AlertTriangle, Ban, CheckCircle2, Circle, Clock3, LoaderCircle } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { RunStatus } from "@/types/watchlists"

interface StatusTagProps {
  status: RunStatus | string
  size?: "small" | "default"
}

type StatusIconToken = "pending" | "running" | "completed" | "failed" | "cancelled" | "unknown"

const STATUS_CONFIG: Record<string, {
  color: string
  labelKey: string
  fallbackLabel: string
  iconToken: StatusIconToken
}> = {
  pending: {
    color: "default",
    labelKey: "watchlists:runs.statusLabels.pending",
    fallbackLabel: "Pending",
    iconToken: "pending"
  },
  running: {
    color: "processing",
    labelKey: "watchlists:runs.statusLabels.running",
    fallbackLabel: "Running",
    iconToken: "running"
  },
  completed: {
    color: "success",
    labelKey: "watchlists:runs.statusLabels.completed",
    fallbackLabel: "Completed",
    iconToken: "completed"
  },
  failed: {
    color: "error",
    labelKey: "watchlists:runs.statusLabels.failed",
    fallbackLabel: "Failed",
    iconToken: "failed"
  },
  cancelled: {
    color: "warning",
    labelKey: "watchlists:runs.statusLabels.cancelled",
    fallbackLabel: "Cancelled",
    iconToken: "cancelled"
  }
}

const toTitleCase = (value: string): string =>
  value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())

const renderStatusIcon = (iconToken: StatusIconToken) => {
  if (iconToken === "pending") return <Clock3 className="h-3.5 w-3.5" aria-hidden />
  if (iconToken === "running") return <LoaderCircle className="h-3.5 w-3.5" aria-hidden />
  if (iconToken === "completed") return <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
  if (iconToken === "failed") return <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
  if (iconToken === "cancelled") return <Ban className="h-3.5 w-3.5" aria-hidden />
  return <Circle className="h-3.5 w-3.5" aria-hidden />
}

export const StatusTag: React.FC<StatusTagProps> = ({ status, size = "default" }) => {
  const { t } = useTranslation(["watchlists"])
  const normalizedStatus = String(status || "").trim().toLowerCase()
  const config = STATUS_CONFIG[normalizedStatus]
  const fallbackLabel = normalizedStatus
    ? toTitleCase(normalizedStatus)
    : t("watchlists:runs.statusLabels.unknown", "Unknown")
  const label = config
    ? t(config.labelKey, config.fallbackLabel)
    : fallbackLabel
  const ariaLabel = t("watchlists:runs.statusAria", "Run status: {{status}}", { status: label })
  const iconToken = config?.iconToken || "unknown"

  return (
    <Tag
      color={config?.color || "default"}
      className={size === "small" ? "text-xs" : ""}
      aria-label={ariaLabel}
      title={ariaLabel}
    >
      <span className="inline-flex items-center gap-1">
        <span data-testid={`watchlists-status-icon-${iconToken}`}>
          {renderStatusIcon(iconToken)}
        </span>
        <span>{label}</span>
      </span>
    </Tag>
  )
}
